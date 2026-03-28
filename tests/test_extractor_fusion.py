from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from src.resume_segmentation.services.document_geometry import (
    BlockNode,
    DocumentGeometry,
    LineNode,
    PageGeometry,
    WordNode,
)
from src.resume_segmentation.services.document_text_extractor import DocumentTextExtractor
from src.resume_segmentation.services.resume_processor import ResumeProcessor


class _DummyExtractor:
    def __init__(self, geometry: DocumentGeometry) -> None:
        self._geometry = geometry

    def extract(self, _path: str) -> DocumentGeometry:
        return self._geometry


def _make_line(
    text: str,
    *,
    x0: float,
    x1: float,
    top: float,
    bottom: float,
    column: int,
    font_size: float,
    is_bold: bool = False,
) -> LineNode:
    return LineNode(
        text=text,
        page=0,
        x0=x0,
        x1=x1,
        top=top,
        bottom=bottom,
        column=column,
        font_size=font_size,
        is_bold=is_bold,
        words=[WordNode(text=text, page=0, x0=x0, x1=x1, top=top, bottom=bottom)],
    )


class ExtractorFusionTests(unittest.TestCase):
    def test_text_extractor_selects_best_source_and_merges_urls(self) -> None:
        extractor = DocumentTextExtractor()

        with (
            patch.object(
                extractor,
                "_extract_with_pdfplumber",
                return_value=(
                    ["Dev Agarwal", "Experience", "Acme Corp"],
                    ["https://linkedin.com/in/dev"],
                ),
            ),
            patch.object(
                extractor,
                "_extract_with_docling",
                return_value=(
                    [
                        "General Information",
                        "Dev Agarwal",
                        "Software Engineer",
                        "Work Experience",
                        "Acme Corp",
                        "2022 - Present",
                        "Education",
                        "Bachelor of Technology",
                        "Technical Expertise",
                        "Python, FastAPI",
                    ],
                    ["https://portfolio.dev"],
                ),
            ),
        ):
            result = extractor.extract_with_diagnostics("/tmp/mock.pdf")

        self.assertEqual(result.best_source, "docling")
        self.assertEqual(
            result.urls,
["https://linkedin.com/in/dev", "https://portfolio.dev"],
        )
        self.assertEqual(len(result.candidates), 2)
        self.assertIn("Technical Expertise", result.lines)

    def test_geometry_fusion_prefers_layout_rich_pdfplumber_and_keeps_docling_skills(self) -> None:
        pdf_lines = [
            _make_line("Experience", x0=40, x1=180, top=20, bottom=32, column=0, font_size=14, is_bold=True),
            _make_line("Software Engineer", x0=40, x1=180, top=36, bottom=48, column=0, font_size=11),
            _make_line("Acme Corp", x0=40, x1=180, top=52, bottom=64, column=0, font_size=11),
            _make_line("2022 - Present", x0=40, x1=180, top=68, bottom=80, column=0, font_size=11),
            _make_line("Education", x0=40, x1=180, top=100, bottom=112, column=0, font_size=14, is_bold=True),
            _make_line("Bachelor of Technology", x0=40, x1=240, top=116, bottom=128, column=0, font_size=11),
            _make_line("Skills", x0=330, x1=420, top=20, bottom=32, column=1, font_size=14, is_bold=True),
            _make_line("Python, FastAPI", x0=330, x1=470, top=36, bottom=48, column=1, font_size=11),
        ]
        pdf_geometry = DocumentGeometry(
            pages=[
                PageGeometry(
                    page=0,
                    width=600,
                    height=800,
                    layout="two_column",
                    col_gap=250,
                    sidebar_column=1,
                    lines=pdf_lines,
                    blocks=[
                        BlockNode(page=0, column=0, lines=pdf_lines[:6]),
                        BlockNode(page=0, column=1, lines=pdf_lines[6:]),
                    ],
                )
            ],
            urls=["https://linkedin.com/in/dev"],
            source_engine="pdfplumber",
        )

        docling_lines = [
            _make_line("Projects", x0=40, x1=180, top=20, bottom=32, column=-1, font_size=14, is_bold=True),
            _make_line("Resume Parser", x0=40, x1=220, top=36, bottom=48, column=-1, font_size=11),
            _make_line("Built a deterministic parser", x0=40, x1=320, top=52, bottom=64, column=-1, font_size=11),
            _make_line("Portfolio", x0=40, x1=140, top=84, bottom=96, column=-1, font_size=14, is_bold=True),
        ]
        docling_geometry = DocumentGeometry(
            pages=[
                PageGeometry(
                    page=0,
                    width=600,
                    height=800,
                    layout="single_column",
                    col_gap=None,
                    lines=docling_lines,
                    blocks=[BlockNode(page=0, column=-1, lines=docling_lines)],
                )
            ],
            urls=["https://portfolio.dev"],
            table_skills=["Python", "PyMuPDF"],
            source_engine="docling",
        )

        processor = ResumeProcessor(output_dir=Path("/tmp"))
        processor.__dict__["_docling_extractor"] = _DummyExtractor(docling_geometry)
        processor.__dict__["_geometry_extractor"] = _DummyExtractor(pdf_geometry)

        merged = processor._extract_geometry("/tmp/mock.pdf")

        self.assertEqual(merged.source_engine, "pdfplumber")
        self.assertEqual(merged.urls, ["https://linkedin.com/in/dev", "https://portfolio.dev"])
        self.assertEqual(merged.table_skills, ["Python", "PyMuPDF"])
        self.assertEqual(merged.pages[0].layout, "two_column")


if __name__ == "__main__":
    unittest.main()
