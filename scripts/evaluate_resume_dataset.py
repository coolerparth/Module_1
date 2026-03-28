from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from resume_segmentation.services.pipeline import ARIEPipeline
from resume_segmentation.utils.resume_dataset_schema import validate_resume_dataset
from resume_segmentation.services.skills_normalizer import canonicalize_skills


def normalize(value: str | None) -> str:
    if not value:
        return ""
    text = value.lower()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9+.#/%&\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(value: str | None) -> set[str]:
    normalized = normalize(value)
    return {token for token in normalized.split() if token}


def text_similarity(a: str | None, b: str | None) -> float:
    norm_a = normalize(a)
    norm_b = normalize(b)
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0
    toks_a = tokenize(a)
    toks_b = tokenize(b)
    if not toks_a or not toks_b:
        return 0.0
    overlap = len(toks_a & toks_b)
    return round((2 * overlap) / (len(toks_a) + len(toks_b)), 3)


def flatten_skills(raw: dict | list | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    values: list[str] = []
    if isinstance(raw, dict):
        for item in raw.values():
            if isinstance(item, list):
                values.extend(str(v).strip() for v in item if str(v).strip())
            elif item:
                values.append(str(item).strip())
    return values


def normalize_truth_entries(raw: object, primary_key: str) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        entries: list[dict] = []
        for item in raw:
            if isinstance(item, dict):
                entries.append(item)
            elif isinstance(item, str) and item.strip():
                entries.append({primary_key: item.strip()})
        return entries
    return []


def score_personal_info(truth: dict, pred: dict) -> tuple[float, dict[str, bool]]:
    fields = [field for field in ("name", "email", "phone", "location") if truth.get(field)]
    if not fields:
        return 1.0, {}
    detail = {
        field: normalize(truth.get(field)) == normalize(pred.get(field))
        for field in fields
    }
    score = round(sum(1 for matched in detail.values() if matched) / len(fields), 3)
    return score, detail


def _canon_skill_set(raw_list: list[str]) -> set[str]:
    """Canonicalize + normalize skills for fair comparison."""
    try:
        canonical = canonicalize_skills(raw_list)
    except Exception:
        canonical = raw_list
    result: set[str] = set()
    for item in canonical:
        n = normalize(item)
        if n:
            result.add(n)
    # Also add the original normalized form as fallback
    for item in raw_list:
        n = normalize(item)
        if n:
            result.add(n)
    return result


def score_skills(truth_values: list[str], pred_values: list[str]) -> tuple[float, dict[str, object]]:
    truth = _canon_skill_set(truth_values)
    pred = _canon_skill_set(pred_values)
    if not truth and not pred:
        return 1.0, {"truth_count": 0, "pred_count": 0, "matches": 0, "precision": 1.0, "recall": 1.0}
    matches = len(truth & pred)
    precision = matches / len(pred) if pred else 0.0
    recall = matches / len(truth) if truth else 0.0
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return round(f1, 3), {
        "truth_count": len(truth),
        "pred_count": len(pred),
        "matches": matches,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
    }


def best_match_score(truth_items: list[dict], pred_items: list[dict], truth_keys: tuple[str, ...], pred_keys: tuple[str, ...]) -> tuple[float, dict[str, object]]:
    if not truth_items and not pred_items:
        return 1.0, {"truth_count": 0, "pred_count": 0, "matched": 0}
    if not truth_items:
        return 0.0, {"truth_count": 0, "pred_count": len(pred_items), "matched": 0}

    used: set[int] = set()
    scores: list[float] = []
    matched = 0

    for truth in truth_items:
        best_score = 0.0
        best_index = None
        for index, pred in enumerate(pred_items):
            if index in used:
                continue
            field_scores: list[float] = []
            for t_key, p_key in zip(truth_keys, pred_keys):
                field_scores.append(text_similarity(truth.get(t_key), pred.get(p_key)))
            score = sum(field_scores) / len(field_scores) if field_scores else 0.0
            if score > best_score:
                best_score = score
                best_index = index
        if best_index is not None:
            used.add(best_index)
        if best_score >= 0.75:
            matched += 1
        scores.append(best_score)

    return round(sum(scores) / len(scores), 3), {
        "truth_count": len(truth_items),
        "pred_count": len(pred_items),
        "matched": matched,
    }


def _normalize_experience_truth_entries(raw: object) -> list[dict]:
    entries = normalize_truth_entries(raw, "title")
    normalized: list[dict] = []
    for entry in entries:
        normalized.append({
            "title": entry.get("title"),
            "company": entry.get("company") or entry.get("organization"),
            "start": entry.get("start"),
            "end": entry.get("end"),
        })
    return normalized


def map_truth_item(item: dict) -> dict:
    if "personal_info" in item or "skills" in item:
        personal = item.get("personal_info") or {}
        return {
            "personal_info": {
                "name": personal.get("name"),
                "email": personal.get("email"),
                "phone": personal.get("phone"),
                "location": personal.get("location"),
            },
            "skills": flatten_skills(item.get("skills")),
            "education": normalize_truth_entries(item.get("education"), "institution"),
            "experience": _normalize_experience_truth_entries(item.get("experience")),
            "projects": normalize_truth_entries(item.get("projects"), "name"),
        }

    contact = item.get("contact") or {}
    return {
        "personal_info": {
            "name": item.get("name"),
            "email": contact.get("email"),
            "phone": contact.get("phone"),
            "location": contact.get("location"),
        },
        "skills": flatten_skills(item.get("technical_skills")),
        "education": normalize_truth_entries(item.get("education"), "institution"),
        "experience": _normalize_experience_truth_entries(item.get("experience")),
        "projects": normalize_truth_entries(item.get("projects"), "name"),
    }


def bucket_failures(parsed: dict, scores: dict[str, float], truth: dict, pred_profile: dict) -> list[str]:
    buckets: list[str] = []
    name = pred_profile.get("personal_info", {}).get("name") or ""
    if name and any(token in name.lower() for token in ("email:", "phone:", "linkedin")):
        buckets.append("name_noise")
    if scores["personal_info"] < 1.0:
        buckets.append("contact_info")
    if scores["skills"] < 0.75:
        buckets.append("skills_recall")
    if scores["education"] < 0.75:
        buckets.append("education_matching")
    if scores["experience"] < 0.75:
        buckets.append("experience_matching")
    if scores["projects"] < 0.75:
        buckets.append("projects_matching")
    if truth["experience"] and not pred_profile.get("experience"):
        buckets.append("missing_experience_section")
    if truth["education"] and not pred_profile.get("education"):
        buckets.append("missing_education_section")
    return buckets


def evaluate_item(pipe: ARIEPipeline, base_dir: Path, item: dict) -> dict:
    pdf_path = base_dir / item["file"]
    result = pipe.extract(pdf_path)
    pred_profile = result.profile.model_dump() if result.profile else {}
    truth = map_truth_item(item)

    personal_score, personal_detail = score_personal_info(
        truth["personal_info"], pred_profile.get("personal_info", {})
    )
    skills_score, skills_detail = score_skills(
        truth["skills"], pred_profile.get("skills", [])
    )
    education_score, education_detail = best_match_score(
        truth["education"], pred_profile.get("education", []), ("institution", "degree"), ("institution", "degree")
    )
    experience_score, experience_detail = best_match_score(
        truth["experience"], pred_profile.get("experience", []), ("title", "company"), ("title", "company")
    )
    projects_score, projects_detail = best_match_score(
        truth["projects"], pred_profile.get("projects", []), ("name",), ("name",)
    )

    section_scores = {
        "personal_info": personal_score,
        "skills": skills_score,
        "education": education_score,
        "experience": experience_score,
        "projects": projects_score,
    }
    overall = round(sum(section_scores.values()) / len(section_scores), 3)
    buckets = bucket_failures(item, section_scores, truth, pred_profile)

    return {
        "file": item["file"],
        "success": result.success,
        "error": result.error,
        "extractor_report": result.enrichment.extractor_report,
        "scores": section_scores | {"overall": overall},
        "details": {
            "personal_info": personal_detail,
            "skills": skills_detail,
            "education": education_detail,
            "experience": experience_detail,
            "projects": projects_detail,
        },
        "pred_summary": {
            "name": pred_profile.get("personal_info", {}).get("name"),
            "skills": len(pred_profile.get("skills", [])),
            "education": len(pred_profile.get("education", [])),
            "experience": len(pred_profile.get("experience", [])),
            "projects": len(pred_profile.get("projects", [])),
        },
        "failure_buckets": buckets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate ARIEPipeline against Resume_(PDF)files/resume_dataset.json")
    parser.add_argument("dataset_dir", type=Path, help="Directory containing PDFs and resume_dataset.json")
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "output" / "resume_dataset_eval.json",
        help="Where to write the evaluation report JSON.",
    )
    args = parser.parse_args()

    dataset_path = args.dataset_dir / "resume_dataset.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    schema_summary = validate_resume_dataset(dataset, dataset_dir=args.dataset_dir)
    if not schema_summary.is_valid:
        print(json.dumps({
            "dataset_dir": str(args.dataset_dir),
            **schema_summary.to_dict(),
        }, indent=2, ensure_ascii=False))
        raise SystemExit(1)
    pipe = ARIEPipeline()

    results = [evaluate_item(pipe, args.dataset_dir, item) for item in dataset]
    bucket_counts = Counter(bucket for item in results for bucket in item["failure_buckets"])

    averages = {}
    for key in ("personal_info", "skills", "education", "experience", "projects", "overall"):
        values = [item["scores"][key] for item in results]
        averages[key] = round(sum(values) / len(values), 3) if values else 0.0

    report = {
        "dataset_dir": str(args.dataset_dir),
        "total_files": len(results),
        "schema_validation": schema_summary.to_dict(),
        "averages": averages,
        "failure_buckets": dict(bucket_counts),
        "results": results,
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(args.report)
    print(json.dumps({"averages": averages, "failure_buckets": dict(bucket_counts)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
