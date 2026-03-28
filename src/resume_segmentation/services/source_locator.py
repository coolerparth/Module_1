from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..models.resume import ResumeProfile
from .document_geometry import BlockNode, DocumentGeometry, LineNode


@dataclass
class SourceLocation:
    field: str
    page: int | None
    line_text: str | None
    block_text: str | None
    line_index: int | None
    match_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "page": self.page,
            "line_text": self.line_text,
            "block_text": self.block_text,
            "line_index": self.line_index,
            "match_score": self.match_score,
        }


@dataclass
class SourceLocationReport:
    fields: dict[str, SourceLocation] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {name: item.to_dict() for name, item in self.fields.items()}


class SourceLocator:
    def locate(self, profile: ResumeProfile, geometry: DocumentGeometry | None) -> SourceLocationReport:
        if not geometry:
            return SourceLocationReport()

        report = SourceLocationReport()
        candidates = self._field_candidates(profile)
        for field_name, candidate_text in candidates.items():
            report.fields[field_name] = self._find_best_location(field_name, candidate_text, geometry)
        return report

    def _field_candidates(self, profile: ResumeProfile) -> dict[str, str]:
        candidates: dict[str, str] = {}
        info = profile.personal_info
        if info.name:
            candidates["personal_info.name"] = info.name
        if info.email:
            candidates["personal_info.email"] = info.email
        if info.phone:
            candidates["personal_info.phone"] = info.phone
        if info.location:
            candidates["personal_info.location"] = info.location

        if profile.experience:
            first = profile.experience[0]
            if first.company:
                candidates["experience[0].company"] = first.company
            if first.title:
                candidates["experience[0].title"] = first.title

        if profile.education:
            first = profile.education[0]
            if first.institution:
                candidates["education[0].institution"] = first.institution

        if profile.projects:
            first = profile.projects[0]
            if first.name:
                candidates["projects[0].name"] = first.name

        if profile.skills:
            candidates["skills[0]"] = profile.skills[0]

        return candidates

    def _find_best_location(
        self,
        field_name: str,
        candidate_text: str,
        geometry: DocumentGeometry,
    ) -> SourceLocation:
        best_line: LineNode | None = None
        best_block: BlockNode | None = None
        best_score = 0.0
        best_index: int | None = None

        flattened: list[tuple[int, LineNode, BlockNode]] = []
        running_index = 0
        for page in geometry.pages:
            for block in page.blocks:
                for line in block.lines:
                    flattened.append((running_index, line, block))
                    running_index += 1

        for line_index, line, block in flattened:
            score = self._similarity(candidate_text, line.text)
            if score > best_score:
                best_score = score
                best_line = line
                best_block = block
                best_index = line_index

        return SourceLocation(
            field=field_name,
            page=best_line.page if best_line else None,
            line_text=best_line.text if best_line else None,
            block_text=best_block.text if best_block else None,
            line_index=best_index,
            match_score=round(best_score, 3),
        )

    def _similarity(self, left: str, right: str) -> float:
        left_norm = self._normalize(left)
        right_norm = self._normalize(right)
        if not left_norm or not right_norm:
            return 0.0
        if left_norm == right_norm:
            return 1.0
        if left_norm in right_norm:
            return round(len(left_norm) / len(right_norm), 3)
        left_tokens = set(left_norm.split())
        right_tokens = set(right_norm.split())
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = len(left_tokens & right_tokens)
        return round((2 * overlap) / (len(left_tokens) + len(right_tokens)), 3)

    def _normalize(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9+.#/%&\-\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
