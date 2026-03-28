from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from resume_segmentation.utils.resume_dataset_normalizer import normalize_resume_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize resume_dataset.json link fields for benchmarking.")
    parser.add_argument("dataset_dir", type=Path, help="Directory containing resume_dataset.json")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Rewrite resume_dataset.json in place with normalized values.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional JSON report path for the normalization summary.",
    )
    args = parser.parse_args()

    dataset_path = args.dataset_dir / "resume_dataset.json"
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    result = normalize_resume_dataset(data)

    report = {
        "dataset_dir": str(args.dataset_dir),
        "change_count": len(result.changes),
        "changes": [change.to_dict() for change in result.changes],
        "write_applied": bool(args.write),
    }

    if args.write:
        dataset_path.write_text(json.dumps(result.data, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
