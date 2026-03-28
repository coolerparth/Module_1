from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ARCHETYPES = [
    ("sample_001", "single_column_fresher"),
    ("sample_002", "two_column_fresher"),
    ("sample_003", "single_column_midlevel"),
    ("sample_004", "two_column_senior"),
    ("sample_005", "academic_research"),
    ("sample_006", "design_heavy_sidebar"),
    ("sample_007", "table_heavy_skills"),
    ("sample_008", "project_heavy_engineering"),
    ("sample_009", "internship_resume"),
    ("sample_010", "multi_page_executive"),
    ("sample_011", "single_column_backend"),
    ("sample_012", "single_column_data_science"),
    ("sample_013", "single_column_frontend"),
    ("sample_014", "single_column_devops"),
    ("sample_015", "single_column_embedded"),
    ("sample_016", "two_column_backend"),
    ("sample_017", "two_column_data_science"),
    ("sample_018", "two_column_frontend"),
    ("sample_019", "two_column_design_sidebar"),
    ("sample_020", "two_column_table_heavy"),
    ("sample_021", "academic_publications"),
    ("sample_022", "research_multpage"),
    ("sample_023", "ocr_scanned_resume"),
    ("sample_024", "messy_export_resume"),
    ("sample_025", "executive_multpage"),
]


def build_metadata(sample_id: str, archetype: str) -> dict:
    categories = archetype.split("_")
    return {
        "label_status": "pending",
        "archetype": archetype,
        "categories": sorted(set(categories + ["english_only", "benchmark_scaffold"])),
        "notes": [
            "Replace with real sample-specific notes after manual review.",
            "Set label_status to labeled once the truth file is verified.",
        ],
        "annotation_status": "todo",
    }


def build_truth_template(sample_id: str, archetype: str) -> dict:
    return {
        "_meta": {
            "sample_id": sample_id,
            "archetype": archetype,
            "status": "template",
            "instructions": [
                "Fill only evidence-backed fields from the actual resume.",
                "Keep strings exact where possible.",
                "Leave optional fields null instead of guessing.",
            ],
        },
        "personal_info": {
            "name": None,
            "email": None,
            "phone": None,
            "location": None,
        },
        "links": [],
        "summary": None,
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
        "languages": [],
        "awards": [],
        "interests": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create scaffold files for a multi-resume benchmark pack.")
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "benchmark" / "templates" / "metadata",
        help="Directory for metadata scaffold files.",
    )
    parser.add_argument(
        "--truth-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "benchmark" / "templates" / "ground_truth",
        help="Directory for truth scaffold files.",
    )
    args = parser.parse_args()

    args.metadata_dir.mkdir(parents=True, exist_ok=True)
    args.truth_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, str]] = []
    for sample_id, archetype in DEFAULT_ARCHETYPES:
        metadata_path = args.metadata_dir / f"{sample_id}.json"
        truth_path = args.truth_dir / f"{sample_id}.truth.json"

        metadata_path.write_text(
            json.dumps(build_metadata(sample_id, archetype), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        truth_path.write_text(
            json.dumps(build_truth_template(sample_id, archetype), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        manifest.append(
            {
                "sample_id": sample_id,
                "archetype": archetype,
                "metadata": str(metadata_path.relative_to(PROJECT_ROOT)),
                "truth": str(truth_path.relative_to(PROJECT_ROOT)),
            }
        )

    manifest_path = args.metadata_dir.parent / "scaffold_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
