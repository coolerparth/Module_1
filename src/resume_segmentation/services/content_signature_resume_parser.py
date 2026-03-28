from __future__ import annotations

from ..models.resume import ResumeProfile
from .document_geometry import DocumentGeometry, GeometryExtractor
from .entry_signatures import best_section
from .section_catalog import match_section_heading
from .text_resume_parser import TextResumeParser


class ContentSignatureResumeParser:

    def __init__(self):
        self.geometry_extractor = GeometryExtractor()
        self.text_parser = TextResumeParser()

    def parse(self, pdf_path: str) -> ResumeProfile:
        geometry = self.geometry_extractor.extract(pdf_path)
        return self.parse_geometry(geometry)

    def parse_geometry(self, geometry: DocumentGeometry) -> ResumeProfile:
        sections = self._build_sections(geometry)
        return self.text_parser.parse_sections(sections, geometry.urls)

    def score(self, profile: ResumeProfile) -> int:
        return self.text_parser.score(profile)

    def _build_sections(self, geometry: DocumentGeometry) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {"header": []}
        current_section = "header"
        explicit_heading_seen = False

        for page in geometry.pages:
            header_band = page.height * 0.18
            for block_index, block in enumerate(page.blocks):
                lines = [line.text.strip() for line in block.lines if line.text.strip()]
                if not lines:
                    continue

                heading = match_section_heading(lines[0])
                if heading:
                    explicit_heading_seen = True
                    current_section = heading
                    sections.setdefault(current_section, [])
                    if len(lines) > 1:
                        sections[current_section].extend(lines[1:])
                    continue

                is_header_zone = (
                    page.page == 0
                    and block.lines[0].top <= header_band
                )
                if not explicit_heading_seen and is_header_zone and block_index <= 2:
                    sections["header"].extend(lines)
                    continue

                classified_section, confidence, _ = best_section(lines)
                if classified_section and confidence >= 0.48:
                    if current_section == "header" or confidence >= 0.60:
                        current_section = classified_section
                        sections.setdefault(current_section, [])

                sections.setdefault(current_section, []).extend(lines)

        return sections
