import unittest

from resume_segmentation.models.resume import EducationEntry
from resume_segmentation.services.profile_constraint_solver import ProfileConstraintSolver
from resume_segmentation.services.text_resume_parser import TextResumeParser


class DatasetRegressionTests(unittest.TestCase):
    def test_summary_spillover_keeps_contact_info(self):
        parser = TextResumeParser()
        sections = {
            "header": [
                "VAISHNAVI",
                "KHANDELWAL",
                "Aspiring Software Developer | IoT &",
                "Web Dev Enthusiast",
            ],
            "summary": [
                "vaishnavikhandelwal1781@gmail.com",
                "Full-stack and IoT enthusiast with experience in real-time systems.",
                "Phone-8273902558",
                "GitHub-https://github.com/anditisyou/",
            ],
            "education": [],
            "skills": [],
        }
        profile = parser.parse_sections(sections, ["https://github.com/anditisyou/"])
        self.assertEqual(profile.personal_info.name, "Vaishnavi Khandelwal")
        self.assertEqual(profile.personal_info.email, "vaishnavikhandelwal1781@gmail.com")
        self.assertEqual(profile.personal_info.phone, "+91 82739 02558")

    def test_name_label_noise_is_removed(self):
        parser = TextResumeParser()
        profile = parser.parse_sections(
            {
                "header": ["Arzoo Email:", "arzoodhoundiyal31@gmail.com"],
                "summary": [],
                "education": [],
                "skills": [],
            },
            [],
        )
        self.assertEqual(profile.personal_info.name, "Arzoo")

    def test_infers_education_from_header_block(self):
        parser = TextResumeParser()
        profile = parser.parse_sections(
            {
                "header": [
                    "Vivek Prajapati",
                    "Computer Science & Engineering",
                    "B.Tech",
                    "Graphic Era Hill University, Dehradun",
                ],
                "projects": [],
                "skills": [],
                "summary": [],
            },
            [],
        )
        self.assertEqual(len(profile.education), 1)
        self.assertEqual(profile.education[0].degree, "B.Tech")
        self.assertEqual(profile.education[0].institution, "Graphic Era Hill University, Dehradun")

    def test_solver_repairs_swapped_education_and_project_numbering(self):
        solver = ProfileConstraintSolver()
        education = solver._repair_education([
            EducationEntry(
                institution="2023 - Present",
                degree="Graphic Era Deemed to be University, Dehradun",
                field_of_study="Computer Science & Engineering",
                gpa="9.54/10",
            )
        ])
        self.assertEqual(education[0].institution, "Graphic Era Deemed to be University, Dehradun")
        cleaned_project = solver._clean_project(type('P', (), {
            'name': '2. Real-Time Facial Emotion Detection System',
            'description': None,
            'date_range': None,
            'technologies': [],
            'url': None,
        })())
        self.assertEqual(cleaned_project.name, "Real-Time Facial Emotion Detection System")


if __name__ == "__main__":
    unittest.main()
