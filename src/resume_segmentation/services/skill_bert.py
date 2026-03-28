from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional


_skill_pipe = None

_SKILL_MODEL_NAMES = [
    "jjzha/jobbert-base-cased",
    "algiraldohe/lm-ner-linkedin-skills-recognition",
    "davanstrien/bert-base-uncased-finetuned-skills-ner",
]


def _load_skill_model():
    global _skill_pipe
    if _skill_pipe is not None:
        return _skill_pipe
    try:
        from transformers import pipeline
        for model_name in _SKILL_MODEL_NAMES:
            try:
                _skill_pipe = pipeline(
                    "token-classification",
                    model=model_name,
                    aggregation_strategy="simple",
                    device=-1,
                )
                return _skill_pipe
            except Exception:
                continue
    except Exception:
        pass
    return None


@lru_cache(maxsize=512)
def extract_skills_from_text_bert(text: str) -> tuple[str, ...]:
    pipe = _load_skill_model()
    if pipe is None:
        return ()

    try:
        entities = pipe(text[:512])
    except Exception:
        return ()

    skills: list[str] = []
    seen: set[str] = set()

    for ent in entities:
        label = ent.get("entity_group", "")
        if label not in ("SKILL", "B-SKILL", "I-SKILL", "TECHNOLOGY"):
            continue
        raw = ent.get("word", "").strip()
        if not raw or len(raw) < 2:
            continue
        raw = re.sub(r"^##", "", raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        key = raw.lower()
        if key not in seen and len(raw) >= 2:
            seen.add(key)
            skills.append(raw)

    return tuple(skills)


def enhance_skills_with_bert(parsed_skills: list[str], full_text: str) -> list[str]:
    bert_skills = extract_skills_from_text_bert(full_text)
    if not bert_skills:
        return parsed_skills

    combined: dict[str, str] = {s.lower(): s for s in parsed_skills}
    for skill in bert_skills:
        key = skill.lower()
        if key not in combined:
            combined[key] = skill

    return list(combined.values())


def skill_model_available() -> bool:
    return _load_skill_model() is not None
