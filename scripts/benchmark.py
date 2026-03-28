from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from resume_segmentation.services.resume_processor import ResumeProcessor
from resume_segmentation.services.profile_consensus import ProfileConsensusEngine
from resume_segmentation.settings import settings


def summarize_profile(profile: dict, confidence: float) -> dict:
    return {
        "confidence": round(confidence, 3),
        "has_name": bool(profile.get("personal_info", {}).get("name")),
        "has_email": bool(profile.get("personal_info", {}).get("email")),
        "has_phone": bool(profile.get("personal_info", {}).get("phone")),
        "links": len(profile.get("links", [])),
        "education_entries": len(profile.get("education", [])),
        "experience_entries": len(profile.get("experience", [])),
        "project_entries": len(profile.get("projects", [])),
        "skills": len(profile.get("skills", [])),
        "awards": len(profile.get("awards", [])),
        "interests": len(profile.get("interests", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic resume parser on a directory of PDFs.")
    parser.add_argument("input_dir", type=Path, help="Directory containing PDF resumes.")
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "output" / "benchmark_report.json",
        help="Path to write the benchmark report JSON.",
    )
    args = parser.parse_args()

    pdf_files = sorted([path for path in args.input_dir.rglob("*.pdf") if path.is_file()] + [path for path in args.input_dir.rglob("*.docx") if path.is_file()])
    processor = ResumeProcessor(output_dir=settings.output_dir)
    consensus = ProfileConsensusEngine()

    report: dict[str, list[dict] | dict] = {
        "input_dir": str(args.input_dir),
        "total_files": len(pdf_files),
        "results": [],
    }

    for pdf_file in pdf_files:
        try:
            parsed, _, evidence = processor.process_with_diagnostics(pdf_file)
            profile = parsed.model_dump()
            confidence = consensus.evaluate("final", parsed, evidence).global_score
            report["results"].append({
                "file": str(pdf_file),
                "status": "ok",
                "summary": summarize_profile(profile, confidence),
                "sections": sorted(evidence.present_sections),
            })
        except Exception as exc:
            report["results"].append({
                "file": str(pdf_file),
                "status": "error",
                "error": str(exc),
            })

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=4, ensure_ascii=False), encoding="utf-8")
    print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

