import unittest

from resume_segmentation.utils.resume_dataset_normalizer import normalize_resume_dataset


class ResumeDatasetNormalizerTests(unittest.TestCase):
    def test_adds_scheme_to_known_domains(self):
        dataset = [{
            "file": "resume.pdf",
            "personal_info": {
                "name": "A",
                "email": "a@example.com",
                "phone": "",
                "location": "",
                "links": [
                    {"label": "LinkedIn", "url": "linkedin.com/in/devagarwal2468"},
                    {"label": "GitHub", "url": "github.com/devagarwal2468"},
                ],
            },
            "education": [],
            "experience": [],
            "projects": [],
            "skills": [],
            "certifications": [],
        }]
        result = normalize_resume_dataset(dataset)
        links = result.data[0]["personal_info"]["links"]
        self.assertEqual(links[0]["url"], "https://linkedin.com/in/devagarwal2468")
        self.assertEqual(links[1]["url"], "https://github.com/devagarwal2468")

    def test_expands_safe_bare_slugs(self):
        dataset = [{
            "file": "resume.pdf",
            "personal_info": {
                "name": "A",
                "email": "a@example.com",
                "phone": "",
                "location": "",
                "links": [
                    {"label": "LinkedIn", "url": "dev-goyal-369019283"},
                    {"label": "GitHub", "url": "NandiniAggarwal14"},
                ],
            },
            "education": [],
            "experience": [],
            "projects": [],
            "skills": [],
            "certifications": [],
        }]
        result = normalize_resume_dataset(dataset)
        links = result.data[0]["personal_info"]["links"]
        self.assertEqual(links[0]["url"], "https://www.linkedin.com/in/dev-goyal-369019283/")
        self.assertEqual(links[1]["url"], "https://github.com/NandiniAggarwal14")

    def test_clears_placeholders_without_guessing(self):
        dataset = [{
            "file": "resume.pdf",
            "personal_info": {
                "name": "A",
                "email": "a@example.com",
                "phone": "",
                "location": "",
                "links": [
                    {"label": "LinkedIn", "url": "LinkedIn (link present)"},
                    {"label": "GitHub", "url": "Arzoo"},
                ],
            },
            "education": [],
            "experience": [],
            "projects": [],
            "skills": [],
            "certifications": [],
        }]
        result = normalize_resume_dataset(dataset)
        links = result.data[0]["personal_info"]["links"]
        self.assertEqual(links[0]["url"], "")
        self.assertEqual(links[1]["url"], "Arzoo")
