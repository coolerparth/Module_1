import unittest
from pathlib import Path

from resume_segmentation.utils.resume_dataset_schema import validate_resume_dataset


class ResumeDatasetSchemaTests(unittest.TestCase):
    def test_accepts_new_dataset_shape(self):
        dataset = [
            {
                "file": "resume.pdf",
                "personal_info": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "+91 9999999999",
                    "location": "Dehradun",
                    "links": [{"label": "GitHub", "url": "https://github.com/john"}],
                },
                "education": [
                    {
                        "institution": "Graphic Era University",
                        "degree": "B.Tech",
                        "field_of_study": "Computer Science",
                        "start": "2023",
                        "end": "Present",
                        "gpa": "8.5/10",
                    }
                ],
                "experience": [
                    {
                        "company": "Acme",
                        "title": "Intern",
                        "start": "May 2025",
                        "end": "Jul 2025",
                        "location": "Remote",
                        "bullets": ["Built APIs"],
                    }
                ],
                "projects": [
                    {
                        "name": "Project A",
                        "description": "Built a parser",
                        "technologies": ["Python", "FastAPI"],
                        "url": "https://github.com/john/project-a",
                    }
                ],
                "skills": ["Python", "FastAPI"],
                "certifications": ["AWS Cloud Practitioner"],
            }
        ]
        summary = validate_resume_dataset(dataset)
        self.assertTrue(summary.is_valid)
        self.assertEqual(summary.error_count, 0)

    def test_rejects_missing_required_keys(self):
        dataset = [{"file": "resume.pdf", "personal_info": {}}]
        summary = validate_resume_dataset(dataset)
        self.assertFalse(summary.is_valid)
        self.assertGreater(summary.error_count, 0)

    def test_warns_on_non_normalized_link(self):
        dataset = [
            {
                "file": "resume.pdf",
                "personal_info": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "+91 9999999999",
                    "location": "Dehradun",
                    "links": [{"label": "LinkedIn", "url": "john-doe"}],
                },
                "education": [],
                "experience": [],
                "projects": [],
                "skills": [],
                "certifications": [],
            }
        ]
        summary = validate_resume_dataset(dataset, dataset_dir=Path('.'))
        self.assertTrue(any(issue.level == 'warning' for issue in summary.issues))
