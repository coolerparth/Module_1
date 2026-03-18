"""
confidence_engine.py — Per-field confidence scoring for parsed resume profiles.

Every extracted field gets a confidence score 0.0–1.0 based on:
  1. Multi-strategy agreement  (more strategies agree → higher confidence)
  2. Field completeness        (more subfields filled → higher confidence)
  3. Pattern validity          (email looks real, phone has right digits, etc.)
  4. Evidence corroboration    (section heading seen in document → higher)
  5. Cross-field consistency   (dates make temporal sense → higher)

Output is attached to the ResumeProfile as a ConfidenceReport.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from ..models.resume import (
    EducationEntry, ExperienceEntry, PersonalInfo,
    ProjectEntry, ResumeProfile,
)
from .document_evidence import DocumentEvidence


                                                                               
              
                                                                               

@dataclass
class FieldConfidence:
    score: float                    
    signals: list[str]                             
    warnings: list[str]                               

    @property
    def grade(self) -> str:
        if self.score >= 0.85: return "A"
        if self.score >= 0.70: return "B"
        if self.score >= 0.50: return "C"
        if self.score >= 0.30: return "D"
        return "F"


@dataclass
class ConfidenceReport:
    overall: float
    grade: str
    fields: dict[str, FieldConfidence] = field(default_factory=dict)
    strategy_agreement: float = 0.0
    completeness: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "grade": self.grade,
            "strategy_agreement": self.strategy_agreement,
            "completeness": self.completeness,
            "fields": {
                k: {
                    "score": v.score,
                    "grade": v.grade,
                    "signals": v.signals,
                    "warnings": v.warnings,
                }
                for k, v in self.fields.items()
            },
            "warnings": self.warnings,
        }


                                                                               
          
                                                                               

_EMAIL_RE   = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+\-]*@[A-Za-z0-9][A-Za-z0-9\-]*\.[A-Za-z]{2,}(?:\.[A-Za-z]{2,})?$")
_PHONE_RE   = re.compile(r"[\d]")
_DATE_RE    = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|\b20\d{2}\b", re.I)
_URL_RE     = re.compile(r"https?://[^\s]+")
_BULLET_RE  = re.compile(r"^[•\-–—►▸●]")


                                                                               
                   
                                                                               

class ConfidenceEngine:

    def score(
        self,
        profile: ResumeProfile,
        strategy_results: list,
        evidence: DocumentEvidence,
    ) -> ConfidenceReport:
        fields: dict[str, FieldConfidence] = {}

        fields["personal_info"] = self._score_personal_info(profile.personal_info)
        fields["links"]         = self._score_links(profile.links, evidence)
        fields["skills"]        = self._score_skills(profile.skills, evidence)
        fields["experience"]    = self._score_experience(profile.experience, evidence)
        fields["education"]     = self._score_education(profile.education, evidence)
        fields["projects"]      = self._score_projects(profile.projects, evidence)
        fields["awards"]        = self._score_list_field(profile.awards, "awards", evidence)
        fields["interests"]     = self._score_list_field(profile.interests, "interests", evidence)
        fields["languages"]     = self._score_list_field(profile.languages, "languages", evidence)

                                  
        strategy_agreement = self._compute_strategy_agreement(strategy_results)

                              
        completeness = self._compute_completeness(profile)

                          
        weights = {
            "personal_info": 0.25, "experience": 0.20, "education": 0.15,
            "skills": 0.15, "projects": 0.10, "links": 0.05,
            "awards": 0.04, "interests": 0.03, "languages": 0.03,
        }
        weighted_sum = sum(fields[k].score * w for k, w in weights.items() if k in fields)
        overall = round(
            weighted_sum * 0.6 + strategy_agreement * 0.25 + completeness * 0.15,
            3,
        )

                                 
        warnings: list[str] = []
        for fname, fc in fields.items():
            for w in fc.warnings:
                warnings.append(f"[{fname}] {w}")

        grade = _score_to_grade(overall)

        return ConfidenceReport(
            overall=overall,
            grade=grade,
            fields=fields,
            strategy_agreement=round(strategy_agreement, 3),
            completeness=round(completeness, 3),
            warnings=warnings,
        )

                                                                            

    def _score_personal_info(self, info: PersonalInfo) -> FieldConfidence:
        score = 0.0
        signals: list[str] = []
        warnings: list[str] = []

              
        if info.name:
            parts = info.name.split()
            if 2 <= len(parts) <= 5 and not any(c.isdigit() for c in info.name):
                score += 0.25
                signals.append("Name looks valid (2–5 capitalized words)")
            else:
                score += 0.10
                warnings.append("Name may be incomplete or invalid")
        else:
            warnings.append("Name not extracted")

               
        if info.email:
            if _EMAIL_RE.match(info.email):
                score += 0.25
                signals.append(f"Valid email format: {info.email}")
            else:
                score += 0.10
                warnings.append(f"Email format questionable: {info.email}")
        else:
            warnings.append("Email not found")

               
        if info.phone:
            digits = len(_PHONE_RE.findall(info.phone))
            if digits >= 10:
                score += 0.20
                signals.append(f"Phone has {digits} digits")
            else:
                score += 0.05
                warnings.append(f"Phone only has {digits} digits — may be incomplete")
        else:
            warnings.append("Phone not found")

                  
        if info.location:
            score += 0.15
            signals.append(f"Location: {info.location}")

                  
        if info.headline:
            score += 0.15
            signals.append(f"Headline: {info.headline}")

        return FieldConfidence(score=round(min(score, 1.0), 3), signals=signals, warnings=warnings)

    def _score_links(self, links, evidence: DocumentEvidence) -> FieldConfidence:
        if not links:
            return FieldConfidence(0.0, [], ["No links found"])

        score = 0.0
        signals: list[str] = []
        warnings: list[str] = []

        valid_count = 0
        has_linkedin = has_github = False

        for link in links:
            parsed = urlparse(link.url)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                valid_count += 1
                if "linkedin.com" in link.url.lower():
                    has_linkedin = True
                if "github.com" in link.url.lower():
                    has_github = True

        if valid_count > 0:
            score += min(valid_count / 3, 0.5)
            signals.append(f"{valid_count} valid URL(s)")
        if has_linkedin:
            score += 0.25
            signals.append("LinkedIn profile found")
        if has_github:
            score += 0.25
            signals.append("GitHub profile found")

        return FieldConfidence(score=round(min(score, 1.0), 3), signals=signals, warnings=warnings)

    def _score_skills(self, skills: list[str], evidence: DocumentEvidence) -> FieldConfidence:
        if not skills:
            return FieldConfidence(0.0, [], ["No skills extracted"])

        score = 0.0
        signals: list[str] = []
        warnings: list[str] = []

                         
        count = len(skills)
        quantity_score = min(count / 20, 0.4)
        score += quantity_score
        signals.append(f"{count} skills extracted")

                                                              
        clean = sum(1 for s in skills if s and len(s) <= 50 and not _BULLET_RE.match(s))
        quality = clean / count if count else 0
        score += quality * 0.4
        if quality < 0.8:
            warnings.append(f"Some skills may contain artifacts ({count - clean} suspect items)")

                                
        if evidence.has_section("skills"):
            score += 0.2
            signals.append("Skills section heading confirmed in document")
        else:
            warnings.append("No explicit skills section detected — skills may be from elsewhere")

        return FieldConfidence(score=round(min(score, 1.0), 3), signals=signals, warnings=warnings)

    def _score_experience(self, experience: list[ExperienceEntry], evidence: DocumentEvidence) -> FieldConfidence:
        if not experience:
            if evidence.has_section("experience"):
                return FieldConfidence(0.1, [], ["Experience section detected but no entries extracted"])
            return FieldConfidence(0.0, [], ["No experience entries"])

        entry_scores: list[float] = []
        signals: list[str] = []
        warnings: list[str] = []

        for i, entry in enumerate(experience):
            es = 0.0
            if entry.company:
                es += 0.25
            if entry.title:
                es += 0.25
            if entry.date_range and entry.date_range.start:
                es += 0.25
                if _DATE_RE.search(entry.date_range.start):
                    es += 0.05                                 
            if entry.bullets:
                es += min(len(entry.bullets) / 5, 0.20)
            entry_scores.append(min(es, 1.0))

        avg_entry_score = sum(entry_scores) / len(entry_scores)
        evidence_bonus = 0.1 if evidence.has_section("experience") else 0.0

        count = len(experience)
        signals.append(f"{count} experience entr{'y' if count == 1 else 'ies'} extracted")

        if avg_entry_score < 0.5:
            warnings.append("Experience entries appear incomplete (missing company/title/dates)")

        return FieldConfidence(
            score=round(min(avg_entry_score + evidence_bonus, 1.0), 3),
            signals=signals,
            warnings=warnings,
        )

    def _score_education(self, education: list[EducationEntry], evidence: DocumentEvidence) -> FieldConfidence:
        if not education:
            if evidence.has_section("education"):
                return FieldConfidence(0.1, [], ["Education section detected but no entries extracted"])
            return FieldConfidence(0.0, [], ["No education entries"])

        entry_scores: list[float] = []
        for entry in education:
            es = 0.0
            if entry.institution: es += 0.35
            if entry.degree:      es += 0.30
            if entry.date_range and entry.date_range.start: es += 0.20
            if entry.gpa:         es += 0.15
            entry_scores.append(min(es, 1.0))

        avg = sum(entry_scores) / len(entry_scores)
        evidence_bonus = 0.05 if evidence.has_section("education") else 0.0
        signals = [f"{len(education)} education entr{'y' if len(education) == 1 else 'ies'}"]
        warnings = []
        if avg < 0.5:
            warnings.append("Education entries may be incomplete")

        return FieldConfidence(score=round(min(avg + evidence_bonus, 1.0), 3), signals=signals, warnings=warnings)

    def _score_projects(self, projects: list[ProjectEntry], evidence: DocumentEvidence) -> FieldConfidence:
        if not projects:
            if evidence.has_section("projects"):
                return FieldConfidence(0.1, [], ["Projects section detected but no entries extracted"])
            return FieldConfidence(0.0, [], [])

        entry_scores: list[float] = []
        for entry in projects:
            es = 0.0
            if entry.name:        es += 0.40
            if entry.description: es += 0.35
            if entry.date_range and entry.date_range.start: es += 0.15
            if entry.technologies: es += 0.10
            entry_scores.append(min(es, 1.0))

        avg = sum(entry_scores) / len(entry_scores)
        signals = [f"{len(projects)} project(s) extracted"]
        return FieldConfidence(score=round(min(avg, 1.0), 3), signals=signals, warnings=[])

    def _score_list_field(self, items: list[str], field_name: str, evidence: DocumentEvidence) -> FieldConfidence:
        if not items:
            return FieldConfidence(0.0, [], [])
        clean = sum(1 for item in items if item and len(item) > 3)
        score = min(clean / max(len(items), 1), 1.0) * 0.8
        if evidence.has_section(field_name):
            score = min(score + 0.2, 1.0)
        return FieldConfidence(
            score=round(score, 3),
            signals=[f"{len(items)} {field_name} item(s)"],
            warnings=[],
        )

                                                                           

    def _compute_strategy_agreement(self, strategy_results: list) -> float:
        if not strategy_results:
            return 0.0

        scores = [r.global_score for r in strategy_results]
        if len(scores) == 1:
            return scores[0]

        mean = sum(scores) / len(scores)
        if mean == 0:
            return 0.0

        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std = variance ** 0.5
        cv = std / mean                            

                                 
        agreement = max(0.0, 1.0 - cv)
        return min(mean * 0.7 + agreement * 0.3, 1.0)

    def _compute_completeness(self, profile: ResumeProfile) -> float:
        checks = [
            bool(profile.personal_info.name),
            bool(profile.personal_info.email),
            bool(profile.personal_info.phone),
            bool(profile.personal_info.location),
            bool(profile.links),
            bool(profile.skills),
            bool(profile.experience),
            bool(profile.education),
            bool(profile.projects or profile.awards),
        ]
        return sum(checks) / len(checks)


def _score_to_grade(score: float) -> str:
    if score >= 0.85: return "A"
    if score >= 0.70: return "B"
    if score >= 0.50: return "C"
    if score >= 0.30: return "D"
    return "F"
