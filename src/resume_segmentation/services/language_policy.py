from __future__ import annotations

import re
from dataclasses import dataclass

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_CJK_RE = re.compile(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./&-]*")

_ENGLISH_STOPWORDS = frozenset({
    "a", "an", "and", "at", "built", "by", "developed", "education", "engineer",
    "experience", "for", "from", "in", "intern", "of", "on", "project", "projects",
    "resume", "role", "skills", "software", "summary", "technical", "the", "to",
    "university", "using", "with", "work",
})


@dataclass(frozen=True)
class LanguageDecision:
    language: str
    confidence: float
    supported: bool
    reason: str | None = None


def detect_resume_language(lines: list[str]) -> LanguageDecision:
    text = " ".join((line or "").strip() for line in lines if line and line.strip())
    if not text:
        return LanguageDecision(
            language="Unknown",
            confidence=0.0,
            supported=False,
            reason="No extractable text found for language detection.",
        )

    non_latin_matches = (
        len(_DEVANAGARI_RE.findall(text))
        + len(_ARABIC_RE.findall(text))
        + len(_CYRILLIC_RE.findall(text))
        + len(_CJK_RE.findall(text))
    )
    alpha_chars = sum(1 for ch in text if ch.isalpha())
    latin_chars = sum(1 for ch in text if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    latin_ratio = (latin_chars / alpha_chars) if alpha_chars else 0.0
    non_latin_ratio = (non_latin_matches / alpha_chars) if alpha_chars else 0.0

    words = [match.group(0).lower() for match in _LATIN_WORD_RE.finditer(text)]
    token_sample = words[:250]
    lexical_hits = sum(1 for word in token_sample if word in _ENGLISH_STOPWORDS)
    lexical_ratio = (lexical_hits / len(token_sample)) if token_sample else 0.0

    confidence = round(min(1.0, latin_ratio * 0.75 + min(lexical_ratio * 5.0, 0.25)), 3)

    if non_latin_matches >= 8 and non_latin_ratio >= 0.05:
        return LanguageDecision(
            language="Non-English",
            confidence=round(max(non_latin_ratio, 0.85), 3),
            supported=False,
            reason="Detected substantial non-Latin script content; only English resumes are supported.",
        )

    if latin_ratio >= 0.92 and (lexical_hits >= 4 or len(token_sample) <= 25):
        return LanguageDecision(language="English", confidence=max(confidence, 0.9), supported=True)

    if latin_ratio >= 0.97:
        return LanguageDecision(language="English", confidence=max(confidence, 0.88), supported=True)

    return LanguageDecision(
        language="Uncertain",
        confidence=confidence,
        supported=False,
        reason="Resume does not look confidently English-only; only English resumes are supported.",
    )
