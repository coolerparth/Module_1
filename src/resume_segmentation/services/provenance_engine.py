from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models.resume import ResumeProfile
from .document_evidence import DocumentEvidence


@dataclass
class FieldProvenance:
    field: str
    source_strategy: str
    source_score: float
    strategies_with_data: int
    evidence_section_present: bool
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "source_strategy": self.source_strategy,
            "source_score": self.source_score,
            "strategies_with_data": self.strategies_with_data,
            "evidence_section_present": self.evidence_section_present,
            "note": self.note,
        }


@dataclass
class ProvenanceReport:
    fields: dict[str, FieldProvenance] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {name: item.to_dict() for name, item in self.fields.items()}


class ProvenanceEngine:
    _FIELD_TO_SECTION = {
        "personal_info": "header",
        "links": "header",
        "skills": "skills",
        "experience": "experience",
        "education": "education",
        "projects": "projects",
        "awards": "awards",
        "interests": "interests",
        "languages": "languages",
        "summary": "summary",
    }

    def build(
        self,
        profile: ResumeProfile,
        strategy_results: list,
        evidence: DocumentEvidence | None,
    ) -> ProvenanceReport:
        fields: dict[str, FieldProvenance] = {}
        for field_name in (
            "personal_info",
            "links",
            "summary",
            "skills",
            "experience",
            "education",
            "projects",
            "awards",
            "interests",
            "languages",
        ):
            fields[field_name] = self._build_field_provenance(field_name, profile, strategy_results, evidence)
        return ProvenanceReport(fields=fields)

    def _build_field_provenance(
        self,
        field_name: str,
        profile: ResumeProfile,
        strategy_results: list,
        evidence: DocumentEvidence | None,
    ) -> FieldProvenance:
        best_strategy = "unknown"
        best_score = 0.0
        with_data = 0

        for result in strategy_results:
            score = float(getattr(result, "field_scores", {}).get(field_name, 0.0))
            candidate_profile = getattr(result, "profile", None)
            if candidate_profile is not None and self._has_field_data(candidate_profile, field_name):
                with_data += 1
            if score >= best_score:
                best_score = score
                best_strategy = getattr(result, "strategy", "unknown")

        section_name = self._FIELD_TO_SECTION[field_name]
        evidence_section_present = bool(evidence and evidence.has_section(section_name))
        note = None
        if not self._has_field_data(profile, field_name):
            note = "Final profile has no data for this field."
        elif with_data <= 1:
            note = "Only one strategy produced usable data for this field."
        elif not evidence_section_present and field_name not in {"personal_info", "links"}:
            note = "Field extracted without an explicit matching section heading."

        return FieldProvenance(
            field=field_name,
            source_strategy=best_strategy,
            source_score=round(best_score, 3),
            strategies_with_data=with_data,
            evidence_section_present=evidence_section_present,
            note=note,
        )

    def _has_field_data(self, profile: ResumeProfile, field_name: str) -> bool:
        value = getattr(profile, field_name, None)
        if field_name == "personal_info":
            return bool(value and any([value.name, value.email, value.phone, value.location, value.headline]))
        if isinstance(value, list):
            return bool(value)
        return bool(value)
