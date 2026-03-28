from __future__ import annotations

import unittest

from src.resume_segmentation.models.resume import (
    DateRange,
    EducationEntry,
    ExperienceEntry,
    PersonalInfo,
    ProjectEntry,
    ResumeProfile,
)
from src.resume_segmentation.services.resume_validation import ResumeValidator


class ResumeValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ResumeValidator()

    def test_validation_summary_and_ats_present(self) -> None:
        profile = ResumeProfile(
            personal_info=PersonalInfo(
                name="Arjun Kumar",
                email="arjun@gmail.com",
                phone="+91 9876543210",
                location="Delhi, India",
            ),
            links=[],
            skills=["Python", "FastAPI", "Docker"],
            experience=[
                ExperienceEntry(
                    company="Acme Corp",
                    title="Software Engineer",
                    date_range=DateRange(start="Jan 2023", end="Dec 2024"),
                    bullets=["Built APIs that reduced response time by 40%."],
                )
            ],
            education=[
                EducationEntry(
                    institution="IIT Delhi",
                    degree="B.Tech",
                    date_range=DateRange(start="2019", end="2023"),
                    gpa="8.7/10",
                )
            ],
            projects=[
                ProjectEntry(
                    name="Resume Parser",
                    description="Built a parser using Python and FastAPI.",
                    date_range=DateRange(start="2024", end="2024"),
                    technologies=["Python", "FastAPI"],
                )
            ],
        )

        report = self.validator.validate(profile).to_dict()

        self.assertIn("summary", report)
        self.assertIn("ats", report)
        self.assertGreater(report["summary"]["total_checks"], 0)
        self.assertGreaterEqual(report["ats"]["ats_score"], 70)
        self.assertIn("contact", report["ats"]["breakdown"])

    def test_noisy_skill_is_flagged_grey(self) -> None:
        profile = ResumeProfile(
            personal_info=PersonalInfo(name="Dev Agarwal", email="dev@gmail.com", phone="+91 9876543210"),
            skills=["Python", "Engineered", "MongoDB"],
        )

        report = self.validator.validate(profile).to_dict()
        grey_paths = set(report["grey_area"].keys())
        self.assertIn("skills[1]", grey_paths)


if __name__ == "__main__":
    unittest.main()
