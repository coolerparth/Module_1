from __future__ import annotations

import unittest

from src.resume_segmentation.services.projects_parser import ProjectsParser


class ProjectsParserTests(unittest.TestCase):
    def test_parses_boundaries_urls_and_technologies(self) -> None:
        parser = ProjectsParser()
        projects = parser.parse(
            [
                "AI Trip Planner 2024 – 2025",
                "– DevlopinganAI-poweredtravelplanningappusingLangChain, Streamlit, cuttingplanningtimeby40%.",
                "Dashboard | github.com/acme/dashboard | Python, React",
                "– CreateapipelineusingPythonandReact.",
            ]
        )

        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0].name, "AI Trip Planner")
        self.assertIn("LangChain", projects[0].technologies)
        self.assertIn("Streamlit", projects[0].technologies)
        self.assertIn("Developing an AI", projects[0].description or "")

        self.assertEqual(projects[1].name, "Dashboard")
        self.assertEqual(projects[1].url, "https://github.com/acme/dashboard")
        self.assertEqual(projects[1].technologies, ["Python", "React"])

    def test_cleans_crushed_project_descriptions(self) -> None:
        parser = ProjectsParser()
        projects = parser.parse(
            [
                "AI Trip Planner | 2024 - 2025",
                "- DevlopinganAI-poweredtravelplanningappusingLangChain, Streamlit, cuttingplanningtimeby40%.",
                "AI & NLP Recruitment Insights Dashboard | 2025",
                "- CreateapipelineusingPython(Pandas) on 30k applicant recordsforNLProlesinIndiausingPython.",
            ]
        )

        self.assertEqual(len(projects), 2)
        self.assertIn("travel planning app using LangChain", projects[0].description or "")
        self.assertIn("planning time by 40%", projects[0].description or "")
        self.assertIn("records for NLP roles in India using Python", projects[1].description or "")
        self.assertIn("30k", projects[1].description or "")


if __name__ == "__main__":
    unittest.main()
