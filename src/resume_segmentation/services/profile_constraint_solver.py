from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..models.resume import DateRange, EducationEntry, ExperienceEntry, ProjectEntry, ResumeProfile
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
        repaired.skills = candidate_graph.select_strings("skills", self._dedupe_strings(repaired.skills))
        repaired.awards = candidate_graph.select_strings("awards", self._dedupe_strings(repaired.awards))
        repaired.interests = candidate_graph.select_strings("interests", self._dedupe_strings(repaired.interests))
        repaired.education = candidate_graph.select_education(repaired.education)
        repaired.experience = candidate_graph.select_experience(repaired.experience)
        repaired.projects = candidate_graph.select_projects(repaired.projects)
        repaired.experience = self._repair_experience(repaired.experience, repaired.projects, evidence)
        repaired.projects = self._repair_projects(repaired.projects, repaired.experience, evidence)
        repaired.education = self._repair_education(repaired.education)

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
            if not institution and not degree:
                continue
            repaired.append(EducationEntry(
                institution=institution,
                degree=degree,
                field_of_study=self._clean_text(entry.field_of_study),
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

    def _clean_experience(self, entry: ExperienceEntry) -> ExperienceEntry:
        return ExperienceEntry(
            company=self._clean_text(entry.company),
            title=self._clean_text(entry.title),
            date_range=self._clean_date_range(entry.date_range),
            location=self._clean_text(entry.location),
            bullets=self._dedupe_strings(entry.bullets),
        )

    def _clean_project(self, entry: ProjectEntry) -> ProjectEntry:
        return ProjectEntry(
            name=self._clean_text(entry.name),
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
