from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CorpusSignal:
    pages: int
    extracted_chars: int
    extracted_words: int
    nonempty_pages: int
    best_parser_score: float | None = None
    parser_error: str | None = None
    layouts: tuple[str, ...] = field(default_factory=tuple)

    @property
    def nonempty_page_ratio(self) -> float:
        if self.pages <= 0:
            return 0.0
        return self.nonempty_pages / self.pages

    @property
    def words_per_page(self) -> float:
        if self.pages <= 0:
            return 0.0
        return self.extracted_words / self.pages


def infer_quality_tags(signal: CorpusSignal) -> list[str]:
    tags: set[str] = set(signal.layouts)

    tags.add("single_page" if signal.pages <= 1 else "multi_page")

    if signal.nonempty_page_ratio >= 0.8 and signal.extracted_words >= 250:
        tags.add("digital_text")

    if signal.nonempty_pages == 0 or signal.extracted_words < 80:
        tags.update({"likely_scanned", "poor_quality"})
    elif signal.extracted_words < 250:
        tags.add("low_text_density")

    if signal.words_per_page < 160:
        tags.add("sparse_text")

    if signal.extracted_chars < 1500:
        tags.add("short_text")

    if signal.parser_error:
        tags.update({"parser_rejected", "poor_quality"})
    elif signal.best_parser_score is not None:
        if signal.best_parser_score >= 0.85:
            tags.add("high_parser_confidence")
        elif signal.best_parser_score >= 0.65:
            tags.add("medium_parser_confidence")
        else:
            tags.update({"low_parser_confidence", "poor_quality"})

    return sorted(tags)


def infer_truth_status(truth_file_exists: bool, label_status: str | None) -> str:
    normalized = (label_status or "").strip().lower()
    if truth_file_exists and normalized == "labeled":
        return "labeled"
    if truth_file_exists:
        return "template_only"
    return "missing"


