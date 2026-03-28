from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .document_geometry import DocumentGeometry
from .section_catalog import match_section_heading


@dataclass
class InputQualityReport:
    accepted: bool
    reason: str | None
    text_line_count: int
    page_count: int
    scanned_likelihood: float
    image_only_likelihood: float
    malformed_text_likelihood: float
    detected_sections: list[str] = field(default_factory=list)
    section_signal_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "text_line_count": self.text_line_count,
            "page_count": self.page_count,
            "scanned_likelihood": self.scanned_likelihood,
            "image_only_likelihood": self.image_only_likelihood,
            "malformed_text_likelihood": self.malformed_text_likelihood,
            "detected_sections": self.detected_sections,
            "section_signal_score": self.section_signal_score,
        }


class InputQualityAnalyzer:
    _CORE_SECTIONS = frozenset({"header", "summary", "skills", "experience", "education", "projects"})

    def analyze(self, geometry: DocumentGeometry | None, text_lines: list[str]) -> InputQualityReport:
        page_count = len(geometry.pages) if geometry else 0
        normalized_lines = [line.strip() for line in text_lines if line.strip()]
        text_line_count = len(normalized_lines)
        avg_lines_per_page = (text_line_count / page_count) if page_count else float(text_line_count)

        short_lines = sum(1 for line in normalized_lines if 0 < len(line) <= 2)
        noisy_lines = sum(1 for line in normalized_lines if self._looks_malformed(line))
        detected_sections = self._detect_sections(normalized_lines)
        core_count = len(set(detected_sections) & self._CORE_SECTIONS)
        section_signal_score = round(min(core_count / 4.0, 1.0), 3) if text_line_count else 0.0

        image_only_likelihood = 1.0 if page_count and text_line_count == 0 else 0.0
        scanned_likelihood = 0.0
        if page_count:
            if avg_lines_per_page < 4:
                scanned_likelihood += 0.55
            if text_line_count <= page_count * 2:
                scanned_likelihood += 0.25
            if short_lines >= max(4, page_count * 2):
                scanned_likelihood += 0.15
            if text_line_count >= 12 and core_count <= 1:
                scanned_likelihood += 0.05
        scanned_likelihood = round(min(scanned_likelihood, 1.0), 3)

        malformed_text_likelihood = 0.0
        if text_line_count:
            malformed_text_likelihood = noisy_lines / text_line_count
            if text_line_count >= 18 and core_count <= 1:
                malformed_text_likelihood += 0.12
            if text_line_count >= 18 and not ({"experience", "education", "skills"} & set(detected_sections)):
                malformed_text_likelihood += 0.1
            malformed_text_likelihood = round(min(malformed_text_likelihood, 1.0), 3)

        accepted = True
        reason = None
        if image_only_likelihood >= 1.0:
            accepted = False
            reason = "Image-only or non-extractable PDF detected. OCR support is required."
        elif scanned_likelihood >= 0.8:
            accepted = False
            reason = "Scanned or low-text PDF detected. This parser currently supports text-extractable English resumes best."
        elif malformed_text_likelihood >= 0.55 and text_line_count < 20:
            accepted = False
            reason = "Malformed export detected. Extracted text is too noisy for reliable parsing."
        elif malformed_text_likelihood >= 0.6 and section_signal_score <= 0.25:
            accepted = False
            reason = "Low-structure or malformed export detected. Core resume sections could not be recovered reliably."

        return InputQualityReport(
            accepted=accepted,
            reason=reason,
            text_line_count=text_line_count,
            page_count=page_count,
            scanned_likelihood=scanned_likelihood,
            image_only_likelihood=image_only_likelihood,
            malformed_text_likelihood=malformed_text_likelihood,
            detected_sections=detected_sections,
            section_signal_score=section_signal_score,
        )

    def _looks_malformed(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if len(stripped) >= 30 and " " not in stripped:
            return True
        alpha = sum(ch.isalpha() for ch in stripped)
        weird = sum(not (ch.isalnum() or ch.isspace() or ch in ".,:/&()-+%#@") for ch in stripped)
        if alpha and weird / max(len(stripped), 1) > 0.12:
            return True
        return False

    def _detect_sections(self, lines: list[str]) -> list[str]:
        detected: list[str] = []
        seen: set[str] = set()
        for line in lines:
            key = match_section_heading(line)
            if key and key not in seen:
                seen.add(key)
                detected.append(key)
        if lines and "header" not in seen:
            detected.insert(0, "header")
        return detected
