from __future__ import annotations

import unittest

from src.resume_segmentation.models.resume import PersonalInfo, ProjectEntry, ResumeProfile
from src.resume_segmentation.services.resume_validation import ResumeValidator
from src.resume_segmentation.services.validation_repair import ValidationDrivenRepairer


class ValidationRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ResumeValidator()
        self.repairer = ValidationDrivenRepairer()

    def test_repair_removes_noisy_skills_and_infers_project_tech(self) -> None:
        profile = ResumeProfile(
            personal_info=PersonalInfo(
                name="Dev Agarwal",
                email="dev@gmail.com",
                phone="+91 9876543210",
            ),
            skills=["Python", "React", "Machine Learning (ML)", "GitHub", "GLS", "Engineered", "Mridang"],
            interests=["Playing the flute, mridang, and badminton"],
            projects=[
                ProjectEntry(
                    name="Dashboard",
                    description="CreateapipelineusingPythonandReact. github.com/acme/dashboard",
                    technologies=[],
                )
            ],
        )

        initial_report = self.validator.validate(profile)
        repaired = self.repairer.repair(profile, initial_report)

        self.assertEqual(repaired.skills, ["Python", "React", "Machine Learning"])
        self.assertEqual(repaired.projects[0].technologies, ["Python", "React"])
        self.assertEqual(repaired.projects[0].url, "https://github.com/acme/dashboard")
        self.assertIn("Create a pipeline", repaired.projects[0].description)


if __name__ == "__main__":
    unittest.main()
