from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from resume_segmentation.utils.resume_dataset_schema import validate_resume_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate resume_dataset.json against the project benchmark schema.")
    parser.add_argument("dataset_dir", type=Path, help="Directory containing resume_dataset.json and PDFs")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write a validation report JSON.",
    )
    args = parser.parse_args()

    dataset_path = args.dataset_dir / "resume_dataset.json"
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    summary = validate_resume_dataset(data, dataset_dir=args.dataset_dir)

    report = {
        "dataset_dir": str(args.dataset_dir),
        **summary.to_dict(),
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if summary.is_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
