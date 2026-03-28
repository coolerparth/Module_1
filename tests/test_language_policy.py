from __future__ import annotations

import unittest

from src.resume_segmentation.services.language_policy import detect_resume_language


class LanguagePolicyTests(unittest.TestCase):
    def test_accepts_english_resume_text(self) -> None:
        decision = detect_resume_language(
            [
                "Dev Agarwal",
                "Experience",
                "Built backend services using Python and FastAPI.",
                "Education",
                "Bachelor of Technology in Computer Science",
            ]
        )

        self.assertTrue(decision.supported)
        self.assertEqual(decision.language, "English")
        self.assertGreaterEqual(decision.confidence, 0.88)

    def test_rejects_non_latin_resume_text(self) -> None:
        decision = detect_resume_language(
            [
                "अनुभव",
                "सॉफ्टवेयर इंजीनियर",
                "पायथन और मशीन लर्निंग प्रोजेक्ट्स",
            ]
        )

        self.assertFalse(decision.supported)
        self.assertEqual(decision.language, "Non-English")


if __name__ == "__main__":
    unittest.main()
