from __future__ import annotations

from ..models.resume import ResumeProfile
from .document_geometry import DocumentGeometry, GeometryExtractor
from .text_resume_parser import TextResumeParser


class GeometryResumeParser:
    def __init__(self):
        self.geometry_extractor = GeometryExtractor()
        self.text_parser = TextResumeParser()

    def parse(self, pdf_path: str) -> ResumeProfile:
        geometry = self.geometry_extractor.extract(pdf_path)
        return self.parse_geometry(geometry)

    def parse_geometry(self, geometry: DocumentGeometry) -> ResumeProfile:
        return self.text_parser.parse(geometry.ordered_lines(), geometry.urls)

    def score(self, profile: ResumeProfile) -> int:
        return self.text_parser.score(profile)
