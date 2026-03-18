from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from ..models.resume import LinkItem, PersonalInfo, ResumeProfile
from .document_evidence import DocumentEvidence
from .section_catalog import match_section_heading

_BULLET_RE = re.compile(r"^[•\-–]")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9_.+\-]+@[A-Za-z0-9\-]+\.[A-Za-z0-9.\-]{2,}$")
_PHONE_DIGIT_RE = re.compile(r"\d")


@dataclass
class StrategyResult:
    strategy: str
    profile: ResumeProfile
    field_scores: dict[str, float]
    global_score: float


class ProfileConsensusEngine:
    FIELD_WEIGHTS = {
        "personal_info": 2.0,
        "links": 1.0,
        "skills": 1.0,
        "experience": 2.0,
        "education": 2.0,
        "projects": 1.5,
        "awards": 0.8,
        "interests": 0.5,
        "languages": 0.3,
        "summary": 0.2,
    }
    OPTIONAL_SECTION_FIELDS = {
        "experience": "experience",
        "education": "education",
        "projects": "projects",
        "skills": "skills",
        "awards": "awards",
        "interests": "interests",
    }

    def evaluate(
        self,
        strategy: str,
        profile: ResumeProfile,
        evidence: DocumentEvidence | None = None,
    ) -> StrategyResult:
        field_scores = {
            "personal_info": self._score_personal_info(profile.personal_info),
            "links": self._score_links(profile.links),
            "skills": self._score_skills(profile.skills),
            "experience": self._score_experience(profile),
            "education": self._score_education(profile),
            "projects": self._score_projects(profile),
            "awards": self._score_awards(profile.awards),
            "interests": self._score_interests(profile.interests),
            "languages": self._score_languages(profile.languages),
            "summary": 1.0 if profile.summary else 0.0,
        }

        active_weights = dict(self.FIELD_WEIGHTS)
        self._apply_evidence_weights(profile, field_scores, active_weights, evidence)

        weighted_sum = sum(field_scores[name] * weight for name, weight in active_weights.items())
        max_weight = sum(active_weights.values())
        global_score = weighted_sum / max_weight if max_weight else 0.0
        return StrategyResult(strategy=strategy, profile=profile, field_scores=field_scores, global_score=global_score)

    def merge(self, results: list[StrategyResult]) -> ResumeProfile:
        ranked = sorted(results, key=lambda result: result.global_score, reverse=True)
        if not ranked:
            raise RuntimeError("No strategy results were produced.")

        personal_source = max(ranked, key=lambda item: item.field_scores["personal_info"])
        links_source = max(ranked, key=lambda item: item.field_scores["links"])
        skills_source = max(ranked, key=lambda item: item.field_scores["skills"])
        experience_source = max(ranked, key=lambda item: item.field_scores["experience"])
        education_source = max(ranked, key=lambda item: item.field_scores["education"])
        projects_source = max(ranked, key=lambda item: item.field_scores["projects"])
        awards_source = max(ranked, key=lambda item: item.field_scores["awards"])
        interests_source = max(ranked, key=lambda item: item.field_scores["interests"])
        languages_source = max(ranked, key=lambda item: item.field_scores["languages"])
        summary_source = max(ranked, key=lambda item: item.field_scores["summary"])

        merged_personal_info = self._merge_personal_info([item.profile.personal_info for item in ranked])
        merged_links = self._merge_links([links_source.profile.links, personal_source.profile.links])

        return ResumeProfile(
            personal_info=merged_personal_info if self._score_personal_info(merged_personal_info) >= 0.25 else personal_source.profile.personal_info,
            links=merged_links,
            summary=summary_source.profile.summary,
            skills=skills_source.profile.skills,
            experience=experience_source.profile.experience,
            education=education_source.profile.education,
            projects=projects_source.profile.projects,
            certifications=ranked[0].profile.certifications,
            languages=languages_source.profile.languages,
            awards=awards_source.profile.awards,
            interests=interests_source.profile.interests,
        )

    def _merge_personal_info(self, infos: list[PersonalInfo]) -> PersonalInfo:
        return PersonalInfo(
            name=self._first_valid(
                (info.name for info in infos),
                lambda value: self._looks_like_name(value) or self._looks_like_header_identity(value),
            ),
            email=self._first_valid((info.email for info in infos), self._looks_like_email),
            phone=self._first_valid((info.phone for info in infos), self._looks_like_phone),
            location=self._first_valid((info.location for info in infos), lambda value: bool(value and "," in value)),
            headline=self._first_valid((info.headline for info in infos), lambda value: bool(value and len(value) >= 4)),
        )

    def _merge_links(self, link_groups: list[list[LinkItem]]) -> list[LinkItem]:
        merged: list[LinkItem] = []
        seen: set[str] = set()
        for group in link_groups:
            for item in group:
                normalized = item.url.rstrip("/").lower()
                if normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(item)
        return merged

    def _score_personal_info(self, info: PersonalInfo) -> float:
        score = 0.0
        if self._looks_like_name(info.name):
            score += 0.3
        elif self._looks_like_header_identity(info.name):
            score += 0.15
        if self._looks_like_email(info.email):
            score += 0.3
        if self._looks_like_phone(info.phone):
            score += 0.2
        if info.location and "," in info.location:
            score += 0.2
        return min(score, 1.0)

    def _score_links(self, links: list[LinkItem]) -> float:
        valid = 0
        for link in links:
            parsed = urlparse(link.url)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                valid += 1
        return min(valid / 2, 1.0)

    def _score_skills(self, skills: list[str]) -> float:
        if not skills:
            return 0.0
        clean = sum(1 for skill in skills if skill and len(skill) <= 40 and not _BULLET_RE.match(skill))
        quantity = min(len(skills), 24) / 24
        quality = clean / len(skills)
        return round(quantity * quality, 3)

    def _score_experience(self, profile: ResumeProfile) -> float:
        if not profile.experience:
            return 0.0
        entry_scores: list[float] = []
        for entry in profile.experience:
            score = 0.0
            if entry.company and not self._looks_like_sentence(entry.company):
                score += 0.3
            if entry.title:
                score += 0.25
            if entry.date_range and entry.date_range.start:
                score += 0.2
            if entry.bullets:
                score += 0.25
            entry_scores.append(min(score, 1.0))
        return sum(entry_scores) / len(entry_scores)

    def _score_education(self, profile: ResumeProfile) -> float:
        if not profile.education:
            return 0.0
        entry_scores: list[float] = []
        for entry in profile.education:
            score = 0.0
            if entry.institution:
                score += 0.35
            if entry.degree:
                score += 0.25
            if entry.date_range and entry.date_range.start:
                score += 0.2
            if entry.gpa:
                score += 0.2
            entry_scores.append(min(score, 1.0))
        return sum(entry_scores) / len(entry_scores)

    def _score_projects(self, profile: ResumeProfile) -> float:
        if not profile.projects:
            return 0.0
        entry_scores: list[float] = []
        for entry in profile.projects:
            score = 0.0
            if entry.name and not self._looks_like_sentence(entry.name):
                score += 0.45
            if entry.description:
                score += 0.4
            if entry.date_range and entry.date_range.start:
                score += 0.1
            if entry.technologies or entry.url:
                score += 0.05
            entry_scores.append(min(score, 1.0))
        return sum(entry_scores) / len(entry_scores)

    def _score_awards(self, awards: list[str]) -> float:
        if not awards:
            return 0.0
        clean = sum(1 for item in awards if item and len(item) > 8)
        return min(clean / 4, 1.0)

    def _score_languages(self, languages: list[str]) -> float:
        if not languages:
            return 0.0
        return min(len(languages) / 4, 1.0)

    def _score_interests(self, interests: list[str]) -> float:
        if not interests:
            return 0.0
        clean = sum(1 for item in interests if item and len(item) > 3)
        return min(clean / 3, 1.0)

    def _apply_evidence_weights(
        self,
        profile: ResumeProfile,
        field_scores: dict[str, float],
        active_weights: dict[str, float],
        evidence: DocumentEvidence | None,
    ) -> None:
        if not evidence:
            return

        for field_name, section_name in self.OPTIONAL_SECTION_FIELDS.items():
            if evidence.has_section(section_name):
                continue

            if self._field_has_data(profile, field_name):
                field_scores[field_name] = min(field_scores[field_name], 0.25)
                active_weights[field_name] *= 0.35
                continue

            active_weights[field_name] = 0.0

    def _looks_like_name(self, value: str | None) -> bool:
        if not value:
            return False
        parts = value.split()
        if not 2 <= len(parts) <= 5:
            return False
        return not any(char.isdigit() for char in value)

    def _looks_like_header_identity(self, value: str | None) -> bool:
        if not value:
            return False
        parts = value.split()
        if not 2 <= len(parts) <= 6:
            return False
        if any(char.isdigit() for char in value):
            return False
        if match_section_heading(value):
            return False
        return not any(char in value for char in "@|/\\#:+=")

    def _looks_like_email(self, value: str | None) -> bool:
        return bool(value and _EMAIL_RE.match(value))

    def _looks_like_phone(self, value: str | None) -> bool:
        if not value:
            return False
        return len(_PHONE_DIGIT_RE.findall(value)) >= 10

    def _looks_like_sentence(self, value: str) -> bool:
        return len(value.split()) > 10 or value.endswith(".")

    def _field_has_data(self, profile: ResumeProfile, field_name: str) -> bool:
        value = getattr(profile, field_name)
        if value is None:
            return False
        if isinstance(value, list):
            return bool(value)
        return bool(value)

    def _first_valid(self, values, validator):
        for value in values:
            if validator(value):
                return value
        return None
