from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.resume_segmentation.services.pipeline import ARIEPipeline
from scripts.evaluate import evaluate_profile


class ExtractionRegressionTests(unittest.TestCase):
    def test_adev_resume_against_ground_truth(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        pdf_path = project_root / "ADev_Resume.pdf"
        truth_path = project_root / "data" / "ground_truth" / "ADev_Resume.truth.json"

        if not pdf_path.exists() or not truth_path.exists():
            self.skipTest("Benchmark fixture is not present in this workspace copy.")

        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        result = ARIEPipeline().extract(pdf_path)

        self.assertTrue(result.success, msg=result.error)

        profile = result.profile.model_dump()
        evaluation = evaluate_profile(truth, profile)

        self.assertGreaterEqual(evaluation["overall_score"], 0.80)
        self.assertGreaterEqual(evaluation["personal_info"]["score"], 1.0)
        self.assertGreaterEqual(evaluation["links"]["score"], 1.0)
        self.assertGreaterEqual(evaluation["experience"]["score"], 0.95)
        self.assertGreaterEqual(evaluation["education"]["score"], 0.95)
        self.assertGreaterEqual(evaluation["skills"]["score"], 0.60)

        predicted_project_names = {item["name"] for item in profile["projects"]}
        expected_project_names = {item["name"] for item in truth["projects"]}
        self.assertGreaterEqual(
            len(predicted_project_names & expected_project_names),
            7,
        )


if __name__ == "__main__":
    unittest.main()
