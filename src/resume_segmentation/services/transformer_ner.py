from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TransformerNERResult:
    name: Optional[str] = None
    name_confidence: float = 0.0
    organizations: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    education_orgs: list[str] = field(default_factory=list)
    job_titles: list[str] = field(default_factory=list)
    source_model: str = "none"


_jobbert_pipe = None
_spacy_trf_pipe = None
_spacy_lg_pipe = None


def _load_jobbert():
    global _jobbert_pipe
    if _jobbert_pipe is not None:
        return _jobbert_pipe
    try:
        from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
        model_name = "jjzha/jobbert-base-cased"
        tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
        model = AutoModelForTokenClassification.from_pretrained(model_name, local_files_only=True)
        _jobbert_pipe = pipeline(
            "token-classification",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy="simple",
            device=-1,
        )
        return _jobbert_pipe
    except Exception:
        return None


def _load_spacy_trf():
    global _spacy_trf_pipe
    if _spacy_trf_pipe is not None:
        return _spacy_trf_pipe
    try:
        import spacy
        _spacy_trf_pipe = spacy.load("en_core_web_trf")
        return _spacy_trf_pipe
    except Exception:
        return None


def _load_spacy_lg():
    global _spacy_lg_pipe
    if _spacy_lg_pipe is not None:
        return _spacy_lg_pipe
    try:
        import spacy
        _spacy_lg_pipe = spacy.load("en_core_web_lg")
        return _spacy_lg_pipe
    except Exception:
        try:
            import spacy
            _spacy_lg_pipe = spacy.load("en_core_web_sm")
            return _spacy_lg_pipe
        except Exception:
            return None


_ORG_NOISE = frozenset({
    "github", "linkedin", "twitter", "gmail", "yahoo", "hotmail",
    "google drive", "notion", "slack",
})

_TITLE_WORDS = frozenset({
    "engineer", "developer", "analyst", "manager", "architect",
    "scientist", "researcher", "intern", "consultant", "lead",
    "senior", "junior", "associate", "principal", "staff",
    "director", "head", "vp", "cto", "ceo", "sde", "mle", "sre",
})


def _clean_entity(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().strip(".,;:")


def _is_job_title(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in _TITLE_WORDS)


def extract_with_jobbert(text: str) -> TransformerNERResult:
    result = TransformerNERResult(source_model="jobbert")
    pipe = _load_jobbert()
    if pipe is None:
        return result

    try:
        entities = pipe(text[:512])
    except Exception:
        return result

    persons: list[tuple[str, float]] = []
    orgs: list[str] = []
    locs: list[str] = []
    skills: list[str] = []
    edu_orgs: list[str] = []
    seen: set[str] = set()

    for ent in entities:
        label = ent.get("entity_group", "")
        raw = _clean_entity(ent.get("word", ""))
        score = float(ent.get("score", 0.0))
        if not raw or len(raw) < 2:
            continue
        key = raw.lower()

        if label in ("PER", "B-PER", "I-PER"):
            if score >= 0.7 and 2 <= len(raw.split()) <= 4:
                persons.append((raw, score))

        elif label in ("ORG", "B-ORG", "I-ORG"):
            if key not in _ORG_NOISE and key not in seen:
                seen.add(key)
                orgs.append(raw)

        elif label in ("LOC", "B-LOC", "I-LOC", "GPE"):
            if key not in seen:
                seen.add(key)
                locs.append(raw)

        elif label in ("SKILL", "B-SKILL", "I-SKILL"):
            if key not in seen and len(raw) >= 2:
                seen.add(key)
                skills.append(raw)

        elif label in ("EDU", "B-EDU", "I-EDU"):
            if key not in seen:
                seen.add(key)
                edu_orgs.append(raw)

    if persons:
        best = max(persons, key=lambda x: x[1])
        result.name = best[0]
        result.name_confidence = best[1]

    result.organizations = orgs
    result.locations = locs
    result.skills = skills
    result.education_orgs = edu_orgs
    return result


def extract_with_spacy_trf(text: str) -> TransformerNERResult:
    result = TransformerNERResult(source_model="spacy_trf")
    nlp = _load_spacy_trf() or _load_spacy_lg()
    if nlp is None:
        return result

    try:
        doc = nlp(text[:1000])
    except Exception:
        return result

    persons: list[tuple[str, int]] = []
    orgs: list[str] = []
    locs: list[str] = []
    seen: set[str] = set()

    for ent in doc.ents:
        raw = _clean_entity(ent.text)
        key = raw.lower()

        if ent.label_ == "PERSON":
            words = raw.split()
            if 2 <= len(words) <= 4 and not any(c.isdigit() for c in raw):
                persons.append((raw, ent.start_char))

        elif ent.label_ == "ORG":
            if key not in _ORG_NOISE and key not in seen and len(raw) >= 2:
                seen.add(key)
                orgs.append(raw)

        elif ent.label_ in ("GPE", "LOC"):
            if key not in seen and len(raw) >= 2:
                seen.add(key)
                locs.append(raw)

    if persons:
        first = min(persons, key=lambda x: x[1])
        result.name = first[0]
        result.name_confidence = 0.85 if first[1] < 200 else 0.70

    result.organizations = orgs
    result.locations = locs
    return result


def extract_ner_best(text: str) -> TransformerNERResult:
    jobbert = extract_with_jobbert(text)

    if jobbert.source_model == "jobbert" and (
        jobbert.name or jobbert.organizations or jobbert.skills
    ):
        spacy_result = extract_with_spacy_trf(text)

        if not jobbert.name and spacy_result.name:
            jobbert.name = spacy_result.name
            jobbert.name_confidence = spacy_result.name_confidence

        if not jobbert.locations and spacy_result.locations:
            jobbert.locations = spacy_result.locations

        seen_orgs = {o.lower() for o in jobbert.organizations}
        for org in spacy_result.organizations:
            if org.lower() not in seen_orgs:
                jobbert.organizations.append(org)

        return jobbert

    spacy_result = extract_with_spacy_trf(text)
    return spacy_result


def jobbert_available() -> bool:
    return _load_jobbert() is not None


def spacy_trf_available() -> bool:
    return _load_spacy_trf() is not None


def best_model_available() -> str:
    if jobbert_available():
        return "jobbert"
    if spacy_trf_available():
        return "spacy_trf"
    try:
        import spacy
        spacy.load("en_core_web_sm")
        return "spacy_sm"
    except Exception:
        return "regex_only"
