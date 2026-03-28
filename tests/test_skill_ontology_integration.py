from __future__ import annotations

import unittest

from src.resume_segmentation.services.skills_normalizer import SkillCategory, normalize_skills_list


class SkillOntologyIntegrationTests(unittest.TestCase):
    def test_external_aliases_cover_safe_legacy_patterns(self) -> None:
        normalized = normalize_skills_list(
            [
                'dotnet',
                'aws cloudformation',
                'docker compose',
                'fitz',
                'bit bucket',
                'apache airflow',
                'google kubernetes engine',
            ]
        )
        canonicals = [item.canonical for item in normalized]

        self.assertIn('.NET', canonicals)
        self.assertIn('AWS', canonicals)
        self.assertIn('Docker', canonicals)
        self.assertIn('PyMuPDF', canonicals)
        self.assertIn('Bitbucket', canonicals)
        self.assertIn('Airflow', canonicals)
        self.assertIn('GCP', canonicals)

        normalized_map = {item.canonical: item for item in normalized}
        self.assertEqual(normalized_map['.NET'].category, SkillCategory.BACKEND)
        self.assertEqual(normalized_map['Bitbucket'].category, SkillCategory.TOOLS)
        self.assertEqual(normalized_map['PyMuPDF'].category, SkillCategory.TOOLS)


if __name__ == '__main__':
    unittest.main()
