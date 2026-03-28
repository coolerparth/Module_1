from __future__ import annotations

import unittest

from src.resume_segmentation.services.document_geometry import DocumentGeometry, PageGeometry
from src.resume_segmentation.services.input_quality import InputQualityAnalyzer
from src.resume_segmentation.services.section_catalog import match_section_heading
from src.resume_segmentation.services.text_resume_parser import TextResumeParser


class OntologyAndParserIntegrationTests(unittest.TestCase):
    def test_heading_ontology_picks_up_migrated_aliases(self) -> None:
        self.assertEqual(match_section_heading("General Information"), "header")
        self.assertEqual(match_section_heading("Professional References"), "references")
        self.assertEqual(match_section_heading("Technical Expertise"), "skills")

    def test_input_quality_uses_section_signals(self) -> None:
        geometry = DocumentGeometry(
            pages=[PageGeometry(page=0, width=600, height=800, layout="single_column", col_gap=None)]
        )
        lines = [
            "General Information",
            "Dev Agarwal",
            "Work Experience",
            "Software Engineer | Acme",
            "Education",
            "Bachelor of Technology in Computer Science",
            "Technical Expertise",
            "Python, FastAPI, PostgreSQL",
        ]
        report = InputQualityAnalyzer().analyze(geometry, lines)
        self.assertTrue(report.accepted)
        self.assertIn("experience", report.detected_sections)
        self.assertIn("education", report.detected_sections)
        self.assertGreaterEqual(report.section_signal_score, 0.75)

    def test_degree_ontology_supports_bachelor_of_technology(self) -> None:
        parser = TextResumeParser()
        profile = parser.parse_sections(
            {
                "header": ["Dev Agarwal"],
                "education": [
                    "Bachelor of Technology in Computer Science",
                    "ABC Institute of Technology",
                    "2021 - 2025",
                ],
            },
            [],
        )
        self.assertEqual(len(profile.education), 1)
        self.assertIn("Bachelor of Technology", profile.education[0].degree or "")

    def test_experience_bundler_splits_header_only_entries(self) -> None:
        parser = TextResumeParser()
        profile = parser.parse_sections(
            {
                "header": ["Dev Agarwal"],
                "experience": [
                    "Software Engineer",
                    "Acme Corp",
                    "Jan 2022 - Present",
                    "Data Analyst",
                    "Beta LLC",
                    "Jan 2020 - Dec 2021",
                ],
            },
            [],
        )
        self.assertEqual(len(profile.experience), 2)
        self.assertEqual(profile.experience[0].title, "Software Engineer")
        self.assertEqual(profile.experience[0].company, "Acme Corp")
        self.assertEqual(profile.experience[1].title, "Data Analyst")
        self.assertEqual(profile.experience[1].company, "Beta LLC")


if __name__ == "__main__":
    unittest.main()
