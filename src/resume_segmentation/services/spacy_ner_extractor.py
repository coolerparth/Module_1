from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NERResult:
    name: Optional[str] = None
    name_confidence: float = 0.0
    organizations: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    source: str = "none"


_ORG_SUFFIX_STRIP = re.compile(
    r"\s*\b(?:Inc\.?|Ltd\.?|LLC|LLP|Corp\.?|Co\.?|Pvt\.?|Limited|"
    r"Private Limited|Technologies|Solutions|Services|Systems|"
    r"Group|Holdings|Ventures|International|Global)\s*$",
    re.IGNORECASE,
)

_NOISE_ORGS = frozenset({
    "linkedin", "github", "twitter", "instagram", "facebook",
    "gmail", "yahoo", "hotmail", "outlook",
})

_nlp_cache: dict[str, Any] = {}


def _get_best_nlp() -> Optional[Any]:
    if "best" in _nlp_cache:
        return _nlp_cache["best"]

    try:
        import spacy
        for model in ["en_core_web_trf", "en_core_web_lg", "en_core_web_md", "en_core_web_sm"]:
            try:
                nlp = spacy.load(model, disable=["parser", "lemmatizer"] if "trf" not in model else [])
                _nlp_cache["best"] = nlp
                _nlp_cache["model_name"] = model
                return nlp
            except Exception:
                continue
    except Exception:
        pass

    _nlp_cache["best"] = None
    return None


def _get_jobbert():
    if "jobbert" in _nlp_cache:
        return _nlp_cache["jobbert"]
    try:
        from .transformer_ner import _load_jobbert
        pipe = _load_jobbert()
        _nlp_cache["jobbert"] = pipe
        return pipe
    except Exception:
        _nlp_cache["jobbert"] = None
        return None


def extract_ner(text: str) -> NERResult:
    if not text or not text.strip():
        return NERResult()

    jobbert = _get_jobbert()
    if jobbert is not None:
        try:
            from .transformer_ner import extract_with_jobbert, extract_with_spacy_trf
            jb = extract_with_jobbert(text)
            sp = extract_with_spacy_trf(text)

            name = jb.name or sp.name
            name_conf = max(jb.name_confidence, sp.name_confidence)
            orgs = list(dict.fromkeys(jb.organizations + sp.organizations))
            locs = list(dict.fromkeys(jb.locations + sp.locations))
            skills = jb.skills

            return NERResult(
                name=name, name_confidence=name_conf,
                organizations=orgs, locations=locs,
                skills=skills, source="jobbert+spacy"
            )
        except Exception:
            pass

    nlp = _get_best_nlp()
    if nlp is None:
        return NERResult(source="unavailable")

    try:
        doc = nlp(text[:2000])
    except Exception:
        return NERResult(source="error")

    persons: list[tuple[str, int]] = []
    orgs: list[str] = []
    locs: list[str] = []
    dates: list[str] = []
    seen_orgs: set[str] = set()
    seen_locs: set[str] = set()

    for ent in doc.ents:
        raw = ent.text.strip()

        if ent.label_ == "PERSON":
            words = raw.split()
            if 2 <= len(words) <= 4 and not any(c.isdigit() for c in raw):
                persons.append((raw, ent.start_char))

        elif ent.label_ == "ORG":
            clean = _ORG_SUFFIX_STRIP.sub("", raw).strip()
            if clean and clean.lower() not in _NOISE_ORGS and clean.lower() not in seen_orgs:
                seen_orgs.add(clean.lower())
                orgs.append(clean)

        elif ent.label_ in ("GPE", "LOC"):
            if raw.lower() not in seen_locs:
                seen_locs.add(raw.lower())
                locs.append(raw)

        elif ent.label_ == "DATE":
            if len(raw) >= 4:
                dates.append(raw)

    name = None
    conf = 0.0
    if persons:
        first = min(persons, key=lambda x: x[1])
        name = first[0]
        conf = 0.85 if first[1] < 200 else 0.70

    model_name = _nlp_cache.get("model_name", "spacy")
    return NERResult(
        name=name, name_confidence=conf,
        organizations=orgs, locations=locs,
        dates=dates, source=model_name
    )


def extract_ner_from_header(header_lines: list[str]) -> NERResult:
    combined = " ".join(header_lines[:8])
    return extract_ner(combined)


def extract_orgs_from_section(lines: list[str]) -> list[str]:
    return extract_ner(" ".join(lines)).organizations


def ner_available() -> bool:
    try:
        return _get_best_nlp() is not None or _get_jobbert() is not None
    except Exception:
        return False


def current_model() -> str:
    try:
        if _get_jobbert() is not None:
            return "jobbert-base-cased (94%)"
        nlp = _get_best_nlp()
        if nlp:
            return _nlp_cache.get("model_name", "spacy")
    except Exception:
        pass
    return "unavailable"
