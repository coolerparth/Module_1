from __future__ import annotations

import re

from ..models.resume import ResumeProfile
from .document_geometry import DocumentGeometry, GeometryExtractor, LineNode
from .section_catalog import match_section_heading
from .text_resume_parser import TextResumeParser


class SectionGraphResumeParser:
    def __init__(self):
        self.geometry_extractor = GeometryExtractor()
        self.text_parser = TextResumeParser()

    def parse(self, pdf_path: str) -> ResumeProfile:
        geometry = self.geometry_extractor.extract(pdf_path)
        return self.parse_geometry(geometry)

    def parse_geometry(self, geometry: DocumentGeometry) -> ResumeProfile:
        sections = self._build_sections(geometry.pages)
        return self.text_parser.parse_sections(sections, geometry.urls)

    def score(self, profile: ResumeProfile) -> int:
        return self.text_parser.score(profile)

    def _build_sections(self, pages) -> dict[str, list[str]]:
        flattened: list[tuple[LineNode, float]] = []

        for page in pages:
            page_font_sizes = [line.font_size for line in page.lines if line.font_size is not None]
            median_font = self._median(page_font_sizes) if page_font_sizes else 10.0
            for line in page.lines:
                flattened.append((line, median_font))

        sections: dict[str, list[str]] = {"header": []}
        headings: list[tuple[int, str]] = []

        for index, (line, median_font) in enumerate(flattened):
            detected = self._detect_section(line, median_font)
            if detected:
                headings.append((index, detected))

        if not headings:
            sections["header"] = [line.text.strip() for line, _ in flattened if line.text.strip()]
            return sections

        first_heading_index = headings[0][0]
        sections["header"] = [
            line.text.strip()
            for line, _ in flattened[:first_heading_index]
            if line.text.strip()
        ]

        for position, (heading_index, section_name) in enumerate(headings):
            next_heading_index = headings[position + 1][0] if position + 1 < len(headings) else len(flattened)
            body_lines = [
                line.text.strip()
                for line, _ in flattened[heading_index + 1:next_heading_index]
                if line.text.strip()
            ]
            sections.setdefault(section_name, []).extend(body_lines)

        return sections

    def _detect_section(self, line: LineNode, median_font: float) -> str | None:
        detected = match_section_heading(line.text)
        if not detected:
            return None

        normalized = self._normalize(line.text)
        if line.font_size and line.font_size >= median_font * 1.05:
            return detected
        if len(normalized.split()) <= 4:
            return detected
        return None

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9&+\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _median(self, values: list[float]) -> float:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2
