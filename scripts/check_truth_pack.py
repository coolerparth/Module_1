from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_TOP_LEVEL_KEYS = {
    "personal_info",
    "links",
    "summary",
    "skills",
    "experience",
    "education",
    "projects",
    "certifications",
    "languages",
    "awards",
    "interests",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark metadata/truth scaffolds.")
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("data/benchmark/templates/metadata"),
    )
    parser.add_argument(
        "--truth-dir",
        type=Path,
        default=Path("data/benchmark/templates/ground_truth"),
    )
    args = parser.parse_args()

    metadata_files = sorted(args.metadata_dir.glob("*.json"))
    truth_files = sorted(args.truth_dir.glob("*.truth.json"))

    errors: list[str] = []
    truth_stems = {path.stem.replace(".truth", "") for path in truth_files}
    metadata_stems = {path.stem for path in metadata_files}

    missing_truth = sorted(metadata_stems - truth_stems)
    missing_metadata = sorted(truth_stems - metadata_stems)

    for stem in missing_truth:
        errors.append(f"missing truth file for {stem}")
    for stem in missing_metadata:
        errors.append(f"missing metadata file for {stem}")

    for path in metadata_files:
        payload = load_json(path)
        for key in ("label_status", "archetype", "categories", "annotation_status"):
            if key not in payload:
                errors.append(f"{path}: missing metadata key '{key}'")

    for path in truth_files:
        payload = load_json(path)
        missing = REQUIRED_TOP_LEVEL_KEYS - set(payload.keys())
        for key in sorted(missing):
            errors.append(f"{path}: missing truth key '{key}'")

    if errors:
        for error in errors:
            print(error)
        return 1

    print(
        json.dumps(
            {
                "metadata_files": len(metadata_files),
                "truth_files": len(truth_files),
                "status": "ok",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
