from __future__ import annotations

import unittest

from src.resume_segmentation.models.resume import PersonalInfo, ResumeProfile
from src.resume_segmentation.services.document_evidence import DocumentEvidence, HeadingEvidence
from src.resume_segmentation.services.document_geometry import (
    BlockNode,
    DocumentGeometry,
    LineNode,
    PageGeometry,
    WordNode,
)
from src.resume_segmentation.services.layout_engine import LayoutEngine
from src.resume_segmentation.services.profile_consensus import StrategyResult
from src.resume_segmentation.services.provenance_engine import ProvenanceEngine


class LayoutAndProvenanceTests(unittest.TestCase):
    def test_smart_ordered_lines_prefers_main_column_before_sidebar(self) -> None:
        main_line = LineNode(
            text="Experience",
            page=0,
            x0=220,
            x1=420,
            top=40,
            bottom=52,
            column=1,
            font_size=12,
            words=[WordNode(text="Experience", page=0, x0=220, x1=420, top=40, bottom=52)],
        )
        sidebar_line = LineNode(
            text="Skills",
            page=0,
            x0=20,
            x1=110,
            top=50,
            bottom=62,
            column=0,
            font_size=11,
            words=[WordNode(text="Skills", page=0, x0=20, x1=110, top=50, bottom=62)],
        )
        geometry = DocumentGeometry(
            pages=[
                PageGeometry(
                    page=0,
                    width=600,
                    height=800,
                    layout="two_column",
                    col_gap=180,
                    sidebar_column=0,
                    lines=[main_line, sidebar_line],
                    blocks=[
                        BlockNode(page=0, column=1, lines=[main_line]),
                        BlockNode(page=0, column=0, lines=[sidebar_line]),
                    ],
                )
            ]
        )

        self.assertEqual(geometry.smart_ordered_lines(), ["Experience", "Skills"])

    def test_layout_engine_summarizes_two_column_page(self) -> None:
        line_left = LineNode(
            text="Experience",
            page=0,
            x0=20,
            x1=120,
            top=10,
            bottom=20,
            column=0,
            font_size=14,
            is_bold=True,
            words=[WordNode(text="Experience", page=0, x0=20, x1=120, top=10, bottom=20)],
        )
        line_right = LineNode(
            text="Skills",
            page=0,
            x0=350,
            x1=420,
            top=10,
            bottom=20,
            column=1,
            font_size=14,
            is_bold=True,
            words=[WordNode(text="Skills", page=0, x0=350, x1=420, top=10, bottom=20)],
        )
        geometry = DocumentGeometry(
            pages=[
                PageGeometry(
                    page=0,
                    width=600,
                    height=800,
                    layout="two_column",
                    col_gap=300,
                    lines=[line_left, line_right],
                    blocks=[BlockNode(page=0, column=0, lines=[line_left]), BlockNode(page=0, column=1, lines=[line_right])],
                )
            ]
        )
        evidence = DocumentEvidence(
            present_sections={"experience", "skills"},
            headings=[
                HeadingEvidence(section="experience", text="Experience", page=0, score=0.9),
                HeadingEvidence(section="skills", text="Skills", page=0, score=0.9),
            ],
            layouts=["two_column"],
        )

        report = LayoutEngine().analyze(geometry, evidence)

        self.assertEqual(report.overall_layout, "two_column")
        self.assertEqual(report.page_count, 1)
        self.assertEqual(report.page_summaries[0].heading_count, 2)

    def test_provenance_engine_records_best_strategy(self) -> None:
        profile = ResumeProfile(
            personal_info=PersonalInfo(name="Dev Agarwal", email="dev@gmail.com", phone="+91 9876543210"),
            skills=["Python", "React"],
        )
        strategy_a = StrategyResult(
            strategy="text_lines",
            profile=profile,
            field_scores={"personal_info": 0.9, "links": 0.0, "summary": 0.0, "skills": 0.7, "experience": 0.0, "education": 0.0, "projects": 0.0, "awards": 0.0, "interests": 0.0, "languages": 0.0},
            global_score=0.5,
        )
        strategy_b = StrategyResult(
            strategy="ordered_geometry",
            profile=profile,
            field_scores={"personal_info": 0.8, "links": 0.0, "summary": 0.0, "skills": 0.95, "experience": 0.0, "education": 0.0, "projects": 0.0, "awards": 0.0, "interests": 0.0, "languages": 0.0},
            global_score=0.55,
        )
        evidence = DocumentEvidence(present_sections={"skills"}, headings=[], layouts=["single_column"])

        report = ProvenanceEngine().build(profile, [strategy_a, strategy_b], evidence)

        self.assertEqual(report.fields["skills"].source_strategy, "ordered_geometry")
        self.assertEqual(report.fields["skills"].strategies_with_data, 2)
        self.assertTrue(report.fields["skills"].evidence_section_present)


if __name__ == "__main__":
    unittest.main()
