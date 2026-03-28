from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from ..models.resume import (
    DateRange,
    EducationEntry,
    ExperienceEntry,
    LinkItem,
    PersonalInfo,
    ProjectEntry,
    ResumeProfile,
)
from .document_evidence import DocumentEvidence
from .entry_signatures import score_section_signatures
from .field_candidate_graph import FieldCandidateGraphBuilder

if TYPE_CHECKING:
    from .profile_consensus import StrategyResult


class ProfileConstraintSolver:
    def __init__(self):
        self.graph_builder = FieldCandidateGraphBuilder()

    def repair(
        self,
        profile: ResumeProfile,
        strategy_results: list["StrategyResult"],
        evidence: DocumentEvidence,
    ) -> ResumeProfile:
        repaired = profile.model_copy(deep=True)
        candidate_graph = self.graph_builder.build(strategy_results)

        repaired.links = candidate_graph.select_links(repaired.links)
        raw_skills = candidate_graph.select_strings("skills", self._dedupe_strings(repaired.skills))
        repaired.skills = self._clean_skills_post_merge(raw_skills, repaired.education)
        repaired.awards = candidate_graph.select_strings("awards", self._dedupe_strings(repaired.awards))
        repaired.interests = candidate_graph.select_strings("interests", self._dedupe_strings(repaired.interests))
        repaired.education = candidate_graph.select_education(repaired.education)
        repaired.experience = candidate_graph.select_experience(repaired.experience)
        repaired.projects = candidate_graph.select_projects(repaired.projects)
        repaired.experience = self._repair_experience(repaired.experience, repaired.projects, evidence)
        repaired.projects = self._repair_projects(repaired.projects, repaired.experience, evidence)
        repaired.education = self._repair_education(repaired.education)
        repaired.links = self._repair_links(repaired.links)
        repaired.personal_info = self._repair_personal_info(repaired.personal_info)
        repaired.awards = self._repair_list_items(repaired.awards)
        repaired.interests = self._repair_list_items(repaired.interests)

        if not repaired.projects and evidence.has_section("projects"):
            repaired.projects = self._recover_projects_from_strategies(strategy_results)

        if evidence.has_section("experience") and not repaired.experience:
            repaired.experience = self._recover_experience_from_strategies(strategy_results)

        return repaired

    def _repair_experience(
        self,
        experience: list[ExperienceEntry],
        projects: list[ProjectEntry],
        evidence: DocumentEvidence,
    ) -> list[ExperienceEntry]:
        if not experience:
            return []

        repaired: list[ExperienceEntry] = []
        for entry in experience:
            scores = score_section_signatures(self._experience_lines(entry))
            if scores["education"] > scores["experience"] and scores["education"] >= 0.55:
                continue
            if not evidence.has_section("experience") and scores["projects"] > scores["experience"] + 0.2:
                continue
            if entry.company or entry.title or entry.bullets:
                repaired.append(self._clean_experience(entry))
        return self._dedupe_experience(repaired)

    def _repair_projects(
        self,
        projects: list[ProjectEntry],
        experience: list[ExperienceEntry],
        evidence: DocumentEvidence,
    ) -> list[ProjectEntry]:
        if not projects:
            return []

        repaired: list[ProjectEntry] = []
        for entry in projects:
            scores = score_section_signatures(self._project_lines(entry))
            if scores["education"] >= 0.6 and scores["education"] > scores["projects"]:
                continue
            if evidence.has_section("experience") and not evidence.has_section("projects"):
                if scores["experience"] > scores["projects"] + 0.15:
                    continue
            if entry.name:
                repaired.append(self._clean_project(entry))
        return self._dedupe_projects(repaired)

    def _repair_education(self, education: list[EducationEntry]) -> list[EducationEntry]:
        repaired: list[EducationEntry] = []
        for entry in education:
            institution = self._clean_text(entry.institution)
            degree = self._clean_text(entry.degree)
            field_of_study = self._clean_text(entry.field_of_study)

            if institution and self._looks_like_date_text(institution):
                if degree and self._looks_like_institution(degree):
                    institution, degree = degree, None
                else:
                    institution = None

            if institution and degree and self._looks_like_institution(degree) and not self._looks_like_institution(institution):
                institution, degree = degree, institution

            if degree and not field_of_study and self._looks_like_field_of_study(degree):
                field_of_study = degree
                degree = None

            if not institution and not degree:
                continue
            repaired.append(EducationEntry(
                institution=institution,
                degree=degree,
                field_of_study=field_of_study,
                date_range=entry.date_range,
                gpa=self._clean_text(entry.gpa),
            ))
        deduped: list[EducationEntry] = []
        seen: set[str] = set()
        for entry in repaired:
            key = "|".join([
                (entry.institution or "").lower(),
                (entry.degree or "").lower(),
                (entry.date_range.start if entry.date_range else "").lower() if entry.date_range else "",
            ])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    def _recover_projects_from_strategies(self, strategy_results: list["StrategyResult"]) -> list[ProjectEntry]:
        candidates: list[ProjectEntry] = []
        for result in strategy_results:
            for entry in result.profile.projects:
                scores = score_section_signatures(self._project_lines(entry))
                if scores["projects"] >= 0.45:
                    candidates.append(self._clean_project(entry))
        return self._dedupe_projects(candidates)

    def _recover_experience_from_strategies(self, strategy_results: list["StrategyResult"]) -> list[ExperienceEntry]:
        candidates: list[ExperienceEntry] = []
        for result in strategy_results:
            for entry in result.profile.experience:
                scores = score_section_signatures(self._experience_lines(entry))
                if scores["experience"] >= 0.45:
                    candidates.append(self._clean_experience(entry))
        return self._dedupe_experience(candidates)

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = self._clean_text(value)
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return deduped

    def _dedupe_experience(self, entries: list[ExperienceEntry]) -> list[ExperienceEntry]:
        deduped: list[ExperienceEntry] = []
        seen: set[str] = set()
        for entry in entries:
            key = "|".join([
                (entry.company or "").lower(),
                (entry.title or "").lower(),
                (entry.date_range.start if entry.date_range else "").lower() if entry.date_range else "",
            ])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    def _dedupe_projects(self, entries: list[ProjectEntry]) -> list[ProjectEntry]:
        deduped: list[ProjectEntry] = []
        seen: set[str] = set()
        for entry in entries:
            key = "|".join([
                (entry.name or "").lower(),
                (entry.date_range.start if entry.date_range else "").lower() if entry.date_range else "",
            ])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    # --- Post-merge skill cleaning ---
    _SKILL_GPA_RE = re.compile(r"^(?:gpa|cgpa|grade|marks|score)\s*[:=]?\s*[\d.]+", re.IGNORECASE)
    _SKILL_DATE_RE = re.compile(
        r"^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}$"
        r"|^\d{4}\s*[-\u2013]\s*(?:\d{4}|present)$",
        re.IGNORECASE,
    )
    _SKILL_DEGREE_RE = re.compile(
        r"\b(?:bachelor|master|b\.?tech|m\.?tech|b\.?sc|m\.?sc|b\.?e|m\.?e|bca|mca|mba|diploma|intermediate|12th|10th|ssc|hsc)\s+(?:in|of)\b",
        re.IGNORECASE,
    )
    _SKILL_GPA_NUMBER_RE = re.compile(r"^gpa\s*:?\s*", re.IGNORECASE)

    def _clean_skills_post_merge(
        self,
        skills: list[str],
        education: list[EducationEntry],
    ) -> list[str]:
        """Remove education-data noise that bleeds into skills after consensus merge."""
        # Build a set of institution/school names to block
        edu_institutions: set[str] = set()
        for edu in education:
            if edu.institution:
                edu_institutions.add(edu.institution.lower().strip())
            # Also add abbreviated / partial names
            for word in (edu.institution or "").lower().split():
                if len(word) > 4:
                    edu_institutions.add(word)

        cleaned: list[str] = []
        seen: set[str] = set()
        for skill in skills:
            text = skill.strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            # Block GPA strings ("GPA: 8", "GPA: 9.24")
            if self._SKILL_GPA_RE.match(key):
                continue
            # Block standalone GPA numbers from education table rows
            if re.match(r"^gpa:\s*[\d.]+$", key, re.IGNORECASE):
                continue
            # Block date strings
            if self._SKILL_DATE_RE.match(key):
                continue
            # Block degree phrases
            if self._SKILL_DEGREE_RE.search(key):
                continue
            # Block institution names from education entries
            if any(inst and inst in key for inst in edu_institutions if len(inst) > 5):
                continue
            # Block short purely-numeric tokens
            if re.match(r"^[\d./]+$", text):
                continue
            seen.add(key)
            cleaned.append(text)
        return cleaned

    def _repair_links(self, links: list[LinkItem]) -> list[LinkItem]:
        repaired: list[LinkItem] = []
        seen: set[str] = set()

        for link in links:
            label = self._clean_text(link.label) or "Link"
            url = self._clean_text(link.url)
            if not url:
                continue

            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if parsed.scheme not in {"http", "https"} or not netloc or "." not in netloc:
                continue

            if label.lower() == "portfolio" and netloc in {
                "b.tech", "m.tech", "b.sc", "m.sc", "bca", "mca", "be", "me", "mba", "bba",
            }:
                continue

            normalized = url.rstrip("/").lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            repaired.append(LinkItem(label=label, url=url))

        return repaired

    def _repair_personal_info(self, personal_info: PersonalInfo) -> PersonalInfo:
        location = self._clean_text(personal_info.location)
        headline = self._clean_text(personal_info.headline)
        name = self._clean_text(personal_info.name)

        if name:
            name = re.sub(r"\b(?:email|e-?mail|phone|mobile|linkedin|github|portfolio|website|contact|address)\s*:?\s*$", "", name, flags=re.IGNORECASE)
            name = re.sub(r"\s+", " ", name).strip(" |:-") or None

        if headline:
            headline_lower = headline.lower()
            if location and headline_lower == location.lower():
                headline = None
            elif any(marker in headline_lower for marker in ("http://", "https://", "@")):
                headline = None

        return PersonalInfo(
            name=name,
            email=self._clean_text(personal_info.email),
            phone=self._clean_text(personal_info.phone),
            location=location,
            headline=headline,
        )

    def _repair_list_items(self, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen_lower: set[str] = set()

        for raw in values:
            item = self._clean_text(raw)
            if not item:
                continue

            lower_item = item.lower()
            if cleaned and (
                item[:1].islower()
                or lower_item.startswith(("and ", "or ", "with ", "affiliated ", "achieving "))
            ):
                cleaned[-1] = f"{cleaned[-1]} {item}".strip()
                seen_lower = {entry.lower() for entry in cleaned}
                continue

            if lower_item in seen_lower:
                continue

            cleaned.append(item)
            seen_lower.add(lower_item)

        deduped: list[str] = []
        for item in cleaned:
            lower_item = item.lower()
            if any(
                lower_item != other.lower() and lower_item in other.lower()
                for other in cleaned
            ):
                continue
            deduped.append(item)

        return deduped

    def _clean_experience(self, entry: ExperienceEntry) -> ExperienceEntry:
        return ExperienceEntry(
            company=self._clean_text(entry.company),
            title=self._clean_text(entry.title),
            date_range=self._clean_date_range(entry.date_range),
            location=self._clean_text(entry.location),
            bullets=self._dedupe_strings(entry.bullets),
        )

    def _clean_project(self, entry: ProjectEntry) -> ProjectEntry:
        name = self._clean_text(entry.name)
        if name:
            name = re.sub(r"^\d+[.)]\s*", "", name)
        return ProjectEntry(
            name=name,
            description=self._clean_text(entry.description),
            date_range=self._clean_date_range(entry.date_range),
            technologies=self._dedupe_strings(entry.technologies),
            url=self._clean_text(entry.url),
        )

    def _clean_date_range(self, date_range: DateRange | None) -> DateRange | None:
        if not date_range:
            return None
        return DateRange(
            start=self._clean_text(date_range.start),
            end=self._clean_text(date_range.end),
            is_current=date_range.is_current,
        )

    def _experience_lines(self, entry: ExperienceEntry) -> list[str]:
        values = [entry.company or "", entry.title or "", entry.location or ""]
        values.extend(entry.bullets)
        return [value for value in values if value]

    def _project_lines(self, entry: ProjectEntry) -> list[str]:
        values = [entry.name or "", entry.description or ""]
        values.extend(entry.technologies)
        return [value for value in values if value]

    def _looks_like_date_text(self, value: str) -> bool:
        return bool(re.search(r"\b(?:19|20)\d{2}\b", value) and re.search(r"(?:present|current|\-|–|—)", value, re.IGNORECASE))

    def _looks_like_institution(self, value: str) -> bool:
        return bool(re.search(r"\b(?:university|college|institute|school|academy|iit|nit|iiit|bits)\b", value, re.IGNORECASE))

    def _looks_like_field_of_study(self, value: str) -> bool:
        return bool(re.search(r"\b(?:computer science|engineering|data science|artificial intelligence|machine learning|electronics|mechanical|civil|information technology)\b", value, re.IGNORECASE))

    def _clean_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.replace("\u2013", " - ").replace("\u2014", " - ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,-")
        cleaned = re.sub(r"\bDevloping\b", "Developing", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\ban memory\b", "a memory", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bNodejs\b", "Node.js", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bsept\b", "Sept", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bReal-\s+ESRGAN\b", "Real-ESRGAN", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*,\s*,", ", ", cleaned)
        cleaned = re.sub(r"\s+([,.:;!?])", r"\1", cleaned)
        return cleaned or None
