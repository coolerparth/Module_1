from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from resume_segmentation.services.resume_processor import DependencyError, ResumeProcessor
from resume_segmentation.settings import settings
from resume_segmentation.utils import infer_truth_status

_EXCLUDED_INPUT_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
    "NLP_NER_ON_RESUME-application",
    "Resume Validation",
}


def iter_resume_files(input_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.pdf", "*.docx"):
        for path in input_dir.rglob(pattern):
            if not path.is_file():
                continue
            if any(part in _EXCLUDED_INPUT_DIRS for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def infer_tags(summary: dict, sections: list[str], layouts: list[str], has_truth: bool) -> list[str]:
    tags: set[str] = set()

    for layout in layouts:
        tags.add(layout)

    if has_truth:
        tags.add("labeled")
    else:
        tags.add("unlabeled")

    if summary.get("experience_entries", 0) > 0:
        tags.add("with_experience")
    else:
        tags.add("no_experience")

    if summary.get("project_entries", 0) >= 4:
        tags.add("project_heavy")

    if summary.get("education_entries", 0) >= 2:
        tags.add("multi_education")

    if "skills" in sections:
        tags.add("skills_section")
    if "projects" in sections:
        tags.add("projects_section")
    if "experience" in sections:
        tags.add("experience_section")
    if "awards" in sections:
        tags.add("awards_section")
    if "interests" in sections:
        tags.add("interests_section")

    return sorted(tags)


def load_metadata(metadata_dir: Path, sample_id: str) -> dict:
    metadata_path = metadata_dir / f"{sample_id}.json"
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def summarize_profile(profile: dict) -> dict:
    return {
        "experience_entries": len(profile.get("experience", [])),
        "education_entries": len(profile.get("education", [])),
        "project_entries": len(profile.get("projects", [])),
        "skills": len(profile.get("skills", [])),
        "awards": len(profile.get("awards", [])),
        "interests": len(profile.get("interests", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a benchmark manifest for a directory of resume PDFs.")
    parser.add_argument("input_dir", type=Path, help="Directory containing PDF resumes.")
    parser.add_argument(
        "--truth-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "ground_truth",
        help="Directory containing ground-truth files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "output" / "benchmark_manifest.json",
        help="Where to write the generated manifest JSON.",
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "benchmark" / "metadata",
        help="Directory containing benchmark metadata JSON files.",
    )
    args = parser.parse_args()

    processor = ResumeProcessor(output_dir=settings.output_dir)
    pdf_files = iter_resume_files(args.input_dir)

    manifest: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(args.input_dir),
        "truth_dir": str(args.truth_dir),
        "total_files": len(pdf_files),
        "items": [],
    }

    for pdf_file in pdf_files:
        truth_file = args.truth_dir / f"{pdf_file.stem}.truth.json"
        metadata = load_metadata(args.metadata_dir, pdf_file.stem)
        truth_status = infer_truth_status(truth_file.exists(), metadata.get("label_status"))

        parse_status = "ok"
        parser_error = None
        results = []
        evidence_sections: list[str] = []
        evidence_layouts: list[str] = []
        profile_dict: dict = {
            "experience": [],
            "education": [],
            "projects": [],
            "skills": [],
            "awards": [],
            "interests": [],
        }
        average_strategy_score = None

        try:
            profile, results, evidence = processor.process_with_diagnostics(pdf_file)
            profile_dict = profile.model_dump()
            evidence_sections = sorted(evidence.present_sections)
            evidence_layouts = evidence.layouts
            average_strategy_score = round(sum(result.global_score for result in results) / len(results), 3)
        except DependencyError as exc:
            parse_status = "rejected"
            parser_error = str(exc)
        except Exception as exc:                                                     
            parse_status = "error"
            parser_error = str(exc)

        summary = summarize_profile(profile_dict)
        inferred_tags = infer_tags(summary, evidence_sections, evidence_layouts, truth_status == "labeled")
        combined_tags = set(inferred_tags) | set(metadata.get("categories", []))
        if parse_status != "ok":
            combined_tags.update({"parser_rejected", "poor_quality"})

        manifest["items"].append({
            "file": str(pdf_file),
            "truth_file": str(truth_file),
            "has_truth": truth_status == "labeled",
            "has_truth_file": truth_file.exists(),
            "truth_status": truth_status,
            "metadata_categories": metadata.get("categories", []),
            "parse_status": parse_status,
            "parser_error": parser_error,
            "sections": evidence_sections,
            "layouts": evidence_layouts,
            "summary": summary,
            "strategy_count": len(results),
            "average_strategy_score": average_strategy_score,
            "tags": sorted(combined_tags),
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=4, ensure_ascii=False), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

