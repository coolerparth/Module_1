from __future__ import annotations

import unittest

from src.resume_segmentation.models.resume import PersonalInfo, ResumeProfile
from src.resume_segmentation.services.document_geometry import BlockNode, DocumentGeometry, LineNode, PageGeometry, WordNode
from src.resume_segmentation.services.input_quality import InputQualityAnalyzer
from src.resume_segmentation.services.source_locator import SourceLocator


class InputQualityAndSourceLocatorTests(unittest.TestCase):
    def test_rejects_image_only_like_input(self) -> None:
        geometry = DocumentGeometry(pages=[PageGeometry(page=0, width=600, height=800, layout="single_column", col_gap=None)])
        report = InputQualityAnalyzer().analyze(geometry, [])
        self.assertFalse(report.accepted)
        self.assertIn("Image-only", report.reason or "")

    def test_source_locator_finds_matching_page_line(self) -> None:
        line = LineNode(
            text="Dev Agarwal",
            page=0,
            x0=10,
            x1=100,
            top=10,
            bottom=20,
            column=-1,
            font_size=14,
            words=[WordNode(text="Dev", page=0, x0=10, x1=30, top=10, bottom=20), WordNode(text="Agarwal", page=0, x0=35, x1=80, top=10, bottom=20)],
        )
        geometry = DocumentGeometry(
            pages=[
                PageGeometry(
                    page=0,
                    width=600,
                    height=800,
                    layout="single_column",
                    col_gap=None,
                    lines=[line],
                    blocks=[BlockNode(page=0, column=-1, lines=[line])],
                )
            ]
        )
        profile = ResumeProfile(personal_info=PersonalInfo(name="Dev Agarwal"))
        report = SourceLocator().locate(profile, geometry)
        self.assertEqual(report.fields["personal_info.name"].page, 0)
        self.assertGreaterEqual(report.fields["personal_info.name"].match_score, 0.9)


if __name__ == "__main__":
    unittest.main()
