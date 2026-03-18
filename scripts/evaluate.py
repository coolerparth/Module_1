from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from resume_segmentation.services.resume_processor import DependencyError, ResumeProcessor
from resume_segmentation.settings import settings


def normalize(value: str | None) -> str:
    if not value:
        return ""
    text = value.lower()
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"[^a-z0-9+.#/%&\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_string_list(values: list[str]) -> set[str]:
    return {normalize(value) for value in values if normalize(value)}


def score_ratio(matches: int, total: int) -> float:
    return round(matches / total, 3) if total else 1.0


def tokenize(value: str | None) -> set[str]:
    normalized = normalize(value)
    return {token for token in normalized.split() if token}


def text_similarity(truth_value: str | None, pred_value: str | None) -> float:
    truth_norm = normalize(truth_value)
    pred_norm = normalize(pred_value)
    if not truth_norm and not pred_norm:
        return 1.0
    if not truth_norm or not pred_norm:
        return 0.0
    if truth_norm == pred_norm:
        return 1.0

    truth_tokens = tokenize(truth_value)
    pred_tokens = tokenize(pred_value)
    if not truth_tokens or not pred_tokens:
        return 0.0

    overlap = len(truth_tokens & pred_tokens)
    return round((2 * overlap) / (len(truth_tokens) + len(pred_tokens)), 3)


def score_personal_info(truth: dict, pred: dict) -> tuple[float, dict]:
    fields = ["name", "email", "phone", "location"]
    matches = sum(1 for field in fields if normalize(truth.get(field)) == normalize(pred.get(field)))
    return score_ratio(matches, len(fields)), {
        field: normalize(truth.get(field)) == normalize(pred.get(field))
        for field in fields
    }


def score_links(truth: list[dict], pred: list[dict]) -> tuple[float, dict]:
    truth_set = {normalize(item.get("url")) for item in truth if item.get("url")}
    pred_set = {normalize(item.get("url")) for item in pred if item.get("url")}
    matches = len(truth_set & pred_set)
    total = max(len(truth_set), 1)
    return score_ratio(matches, total), {
        "expected": sorted(truth_set),
        "predicted": sorted(pred_set),
        "matches": matches,
    }


def score_string_field(truth: list[str], pred: list[str], *, fuzzy: bool = False) -> tuple[float, dict]:
    if fuzzy:
        truth_values = [value for value in truth if normalize(value)]
        pred_values = [value for value in pred if normalize(value)]
        if not truth_values:
            return 1.0, {"expected_count": 0, "predicted_count": len(pred_values), "matches": 0}

        used_indices: set[int] = set()
        total_score = 0.0
        strong_matches = 0
        for truth_value in truth_values:
            best_score = 0.0
            best_index = None
            for index, pred_value in enumerate(pred_values):
                if index in used_indices:
                    continue
                similarity = text_similarity(truth_value, pred_value)
                if similarity > best_score:
                    best_score = similarity
                    best_index = index
            if best_index is not None:
                used_indices.add(best_index)
            if best_score >= 0.8:
                strong_matches += 1
            total_score += best_score

        return round(total_score / len(truth_values), 3), {
            "expected_count": len(truth_values),
            "predicted_count": len(pred_values),
            "matches": strong_matches,
        }

    truth_set = normalize_string_list(truth)
    pred_set = normalize_string_list(pred)
    matches = len(truth_set & pred_set)
    total = max(len(truth_set), 1)
    return score_ratio(matches, total), {
        "expected_count": len(truth_set),
        "predicted_count": len(pred_set),
        "matches": matches,
    }


def score_structured_entries(truth: list[dict], pred: list[dict], key_fields: list[str], match_fields: list[str]) -> tuple[float, dict]:
    truth_map = {entry_key(item, key_fields): item for item in truth if entry_key(item, key_fields)}
    pred_map = {entry_key(item, key_fields): item for item in pred if entry_key(item, key_fields)}

    if not truth_map:
        return 1.0, {"expected_count": 0, "predicted_count": len(pred_map), "matches": 0}

    entry_scores: list[float] = []
    matched_entries = 0
    for key, truth_entry in truth_map.items():
        pred_entry = pred_map.get(key)
        if not pred_entry:
            entry_scores.append(0.0)
            continue

        matched_entries += 1
        field_scores = [text_similarity(get_nested(truth_entry, field), get_nested(pred_entry, field)) for field in match_fields]
        entry_scores.append(sum(field_scores) / len(match_fields))

    overall = round(sum(entry_scores) / len(truth_map), 3)
    return overall, {
        "expected_count": len(truth_map),
        "predicted_count": len(pred_map),
        "matched_entries": matched_entries,
    }


def entry_key(entry: dict, key_fields: list[str]) -> str:
    parts = [normalize(get_nested(entry, field)) for field in key_fields]
    parts = [part for part in parts if part]
    return "|".join(parts)


def get_nested(entry: dict, field: str) -> str | None:
    current = entry
    for part in field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def evaluate_profile(truth: dict, pred: dict) -> dict:
    results: dict[str, dict | float] = {}

    personal_score, personal_detail = score_personal_info(truth.get("personal_info", {}), pred.get("personal_info", {}))
    results["personal_info"] = {"score": personal_score, "detail": personal_detail}

    links_score, links_detail = score_links(truth.get("links", []), pred.get("links", []))
    results["links"] = {"score": links_score, "detail": links_detail}

    skills_score, skills_detail = score_string_field(truth.get("skills", []), pred.get("skills", []))
    results["skills"] = {"score": skills_score, "detail": skills_detail}

    awards_score, awards_detail = score_string_field(truth.get("awards", []), pred.get("awards", []), fuzzy=True)
    results["awards"] = {"score": awards_score, "detail": awards_detail}

    interests_score, interests_detail = score_string_field(truth.get("interests", []), pred.get("interests", []), fuzzy=True)
    results["interests"] = {"score": interests_score, "detail": interests_detail}

    education_score, education_detail = score_structured_entries(
        truth.get("education", []),
        pred.get("education", []),
        key_fields=["institution"],
        match_fields=["institution", "degree", "field_of_study", "date_range.start", "date_range.end", "gpa"],
    )
    results["education"] = {"score": education_score, "detail": education_detail}

    experience_score, experience_detail = score_structured_entries(
        truth.get("experience", []),
        pred.get("experience", []),
        key_fields=["company", "title"],
        match_fields=["company", "title", "date_range.start", "date_range.end"],
    )
    results["experience"] = {"score": experience_score, "detail": experience_detail}

    projects_score, projects_detail = score_structured_entries(
        truth.get("projects", []),
        pred.get("projects", []),
        key_fields=["name"],
        match_fields=["name", "description", "date_range.start", "date_range.end"],
    )
    results["projects"] = {"score": projects_score, "detail": projects_detail}

    section_scores = [value["score"] for value in results.values() if isinstance(value, dict) and "score" in value]
    results["overall_score"] = round(sum(section_scores) / len(section_scores), 3) if section_scores else 0.0
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate parser outputs against hand-labeled ground truth JSON files.")
    parser.add_argument("input_dir", type=Path, help="Directory containing PDFs.")
    parser.add_argument("truth_dir", type=Path, help="Directory containing ground-truth JSON files named <resume>.truth.json.")
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "output" / "ground_truth_evaluation.json",
        help="Where to write the evaluation report.",
    )
    args = parser.parse_args()

    processor = ResumeProcessor(output_dir=settings.output_dir)
    pdf_files = sorted(path for path in args.input_dir.rglob("*.pdf") if path.is_file())

    report: dict[str, object] = {
        "input_dir": str(args.input_dir),
        "truth_dir": str(args.truth_dir),
        "results": [],
    }

    overall_scores: list[float] = []

    for pdf_file in pdf_files:
        truth_file = args.truth_dir / f"{pdf_file.stem}.truth.json"
        if not truth_file.exists():
            report["results"].append({
                "file": str(pdf_file),
                "status": "missing_truth",
                "truth_file": str(truth_file),
            })
            continue

        truth = json.loads(truth_file.read_text(encoding="utf-8"))
        try:
            parsed = processor.process(pdf_file).model_dump()
            evaluation = evaluate_profile(truth, parsed)
            overall_scores.append(evaluation["overall_score"])
            report["results"].append({
                "file": str(pdf_file),
                "status": "ok",
                "truth_file": str(truth_file),
                "evaluation": evaluation,
            })
        except DependencyError as exc:
            report["results"].append({
                "file": str(pdf_file),
                "status": "parser_rejected",
                "truth_file": str(truth_file),
                "error": str(exc),
            })
        except Exception as exc:  # pragma: no cover - keep evaluation resilient
            report["results"].append({
                "file": str(pdf_file),
                "status": "error",
                "truth_file": str(truth_file),
                "error": str(exc),
            })

    report["average_overall_score"] = round(sum(overall_scores) / len(overall_scores), 3) if overall_scores else 0.0
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=4, ensure_ascii=False), encoding="utf-8")
    print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
