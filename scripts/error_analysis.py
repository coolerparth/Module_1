from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_failures(evaluation: dict) -> list[str]:
    failures: list[str] = []

    if evaluation.get("personal_info", {}).get("score", 1.0) < 1.0:
        failures.append("contact_info")
    if evaluation.get("experience", {}).get("score", 1.0) < 0.9:
        failures.append("experience_boundaries")
    if evaluation.get("education", {}).get("score", 1.0) < 0.9:
        failures.append("education_entries")
    if evaluation.get("projects", {}).get("score", 1.0) < 0.85:
        failures.append("project_descriptions_or_dates")
    if evaluation.get("skills", {}).get("score", 1.0) < 0.85:
        failures.append("skills_aliasing")
    return failures


def enrich_with_metadata(item: dict, metadata_dir: Path) -> dict:
    file_name = Path(item["file"]).stem
    metadata_path = metadata_dir / f"{file_name}.json"
    metadata = load_json(metadata_path) if metadata_path.exists() else {}
    item["metadata"] = metadata
    return item


def main() -> int:
    parser = argparse.ArgumentParser(description="Bucket parser failures from an evaluation report.")
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "output" / "ground_truth_evaluation.json",
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "benchmark" / "metadata",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "output" / "failure_analysis.json",
    )
    args = parser.parse_args()

    report = load_json(args.report)
    buckets: Counter[str] = Counter()
    by_bucket: dict[str, list[dict]] = defaultdict(list)

    for raw_item in report.get("results", []):
        item = enrich_with_metadata(dict(raw_item), args.metadata_dir)
        if item.get("status") != "ok":
            buckets["parser_failure"] += 1
            by_bucket["parser_failure"].append(item)
            continue

        evaluation = item.get("evaluation", {})
        failures = classify_failures(evaluation)
        categories = set(item.get("metadata", {}).get("categories", []))
        if "two_column" in categories or "sidebar" in categories or "design" in categories:
            if evaluation.get("experience", {}).get("score", 1.0) < 0.95 or evaluation.get("projects", {}).get("score", 1.0) < 0.9:
                failures.append("layout_or_sidebar_ordering")
        if "ocr" in categories or "scanned" in categories:
            failures.append("ocr_or_scanned_input")

        if not failures and evaluation.get("overall_score", 1.0) >= 0.95:
            failures.append("passes_threshold")

        for bucket in sorted(set(failures)):
            buckets[bucket] += 1
            by_bucket[bucket].append(
                {
                    "file": item["file"],
                    "overall_score": evaluation.get("overall_score"),
                    "categories": item.get("metadata", {}).get("categories", []),
                }
            )

    output = {
        "report": str(args.report),
        "bucket_counts": dict(buckets),
        "buckets": by_bucket,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
