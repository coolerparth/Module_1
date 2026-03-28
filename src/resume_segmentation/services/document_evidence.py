from __future__ import annotations

from dataclasses import dataclass, field

from .document_geometry import DocumentGeometry
from .section_catalog import match_section_heading


@dataclass
class HeadingEvidence:
    section: str
    text: str
    page: int
    score: float


@dataclass
class DocumentEvidence:
    present_sections: set[str] = field(default_factory=set)
    headings: list[HeadingEvidence] = field(default_factory=list)
    layouts: list[str] = field(default_factory=list)

    def has_section(self, section: str) -> bool:
        return section in self.present_sections


class DocumentEvidenceBuilder:

    def build(
        self,
        geometry: DocumentGeometry | None = None,
        text_lines: list[str] | None = None,
    ) -> DocumentEvidence:
        evidence = DocumentEvidence()

        if geometry:
            evidence.layouts = [page.layout for page in geometry.pages]
            for page in geometry.pages:
                font_sizes = [
                    line.font_size
                    for line in page.lines
                    if line.font_size is not None
                ]
                median_font = self._median(font_sizes) if font_sizes else 10.0
                for line in page.lines:
                    section, score = self._detect_geometry_heading(
                        line.text, line.font_size, line.is_bold, median_font
                    )
                    if not section:
                        continue
                    evidence.present_sections.add(section)
                    evidence.headings.append(HeadingEvidence(
                        section=section,
                        text=line.text.strip(),
                        page=line.page,
                        score=score,
                    ))

        if text_lines:
            for line in text_lines:
                section = match_section_heading(line)
                if section:
                    evidence.present_sections.add(section)

        return evidence

    def _detect_geometry_heading(
        self,
        text: str,
        font_size: float | None,
        is_bold: bool,
        median_font: float,
    ) -> tuple[str | None, float]:
        section = match_section_heading(text)
        if not section:
            return None, 0.0

        score = 0.45
        if font_size and font_size >= median_font * 1.05:
            score += 0.30
        if is_bold:
            score += 0.15
        if len(text.split()) <= 4:
            score += 0.10
        return section, min(score, 1.0)

    def _median(self, values: list[float]) -> float:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2.0
