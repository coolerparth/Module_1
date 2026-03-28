from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from ..models.resume import ResumeProfile
from .date_extractor import has_date
from .document_geometry import DocumentGeometry, LineNode, PageGeometry
from .entry_signatures import best_section
from .section_catalog import match_section_heading
from .text_resume_parser import TextResumeParser


class State(Enum):
    HEADER = auto()
    SECTION_BODY = auto()


@dataclass
class ClassifiedLine:
    text: str
    page: int
    font_size: Optional[float]
    column: int
    is_bold: bool
    is_heading: bool
    section_key: Optional[str]
    heading_confidence: float


def _classify_line(
    line: LineNode,
    page_median_font: float,
    font_scale_threshold: float = 1.05,
) -> ClassifiedLine:
    text = line.text.strip()
    section_key = match_section_heading(text)

    font_boosted = (
        line.font_size is not None
        and line.font_size >= page_median_font * font_scale_threshold
    )

    all_caps = text.isupper() and 2 <= len(text.split()) <= 6
    is_bold = line.is_bold
    word_count = len(text.split())
    is_short = word_count <= 5

    if section_key:
        confidence = 0.40
        if font_boosted:
            confidence += 0.30
        if is_bold:
            confidence += 0.20
        if is_short:
            confidence += 0.10
        if all_caps:
            confidence += 0.10
        return ClassifiedLine(
            text=text,
            page=line.page,
            font_size=line.font_size,
            column=line.column,
            is_bold=is_bold,
            is_heading=True,
            section_key=section_key,
            heading_confidence=min(confidence, 1.0),
        )

    if (font_boosted or is_bold or all_caps) and is_short and word_count >= 1:
        if not has_date(text):
            return ClassifiedLine(
                text=text,
                page=line.page,
                font_size=line.font_size,
                column=line.column,
                is_bold=is_bold,
                is_heading=False,
                section_key=None,
                heading_confidence=0.0,
            )

    return ClassifiedLine(
        text=text,
        page=line.page,
        font_size=line.font_size,
        column=line.column,
        is_bold=is_bold,
        is_heading=False,
        section_key=None,
        heading_confidence=0.0,
    )


@dataclass
class SectionAccumulator:
    sections: dict[str, list[str]] = field(default_factory=lambda: {"header": []})
    current: str = "header"
    first_heading_seen: bool = False

    def set_section(self, key: str) -> None:
        self.current = key
        self.sections.setdefault(key, [])
        self.first_heading_seen = True

    def add_line(self, text: str) -> None:
        if not text:
            return
        self.sections.setdefault(self.current, []).append(text)

    def get(self) -> dict[str, list[str]]:
        return self.sections


def _page_median_font(page: PageGeometry) -> float:
    sizes = [line.font_size for line in page.lines if line.font_size is not None]
    if not sizes:
        return 10.0
    ordered = sorted(sizes)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _content_signature_reclassify(
    accumulator: SectionAccumulator,
    min_confidence: float = 0.52,
) -> dict[str, list[str]]:
    sections = dict(accumulator.get())
    for key in list(sections.keys()):
        if key == "header":
            continue
        lines = sections[key]
        if not lines or len(lines) >= 4:
            continue
        classified, conf, _ = best_section(lines)
        if classified and classified != key and conf >= min_confidence:
            sections.setdefault(classified, []).extend(lines)
            sections[key] = []
    return sections


class DeterministicStateMachine:

    def __init__(
        self,
        heading_confidence_threshold: float = 0.38,
        font_scale_threshold: float = 1.05,
    ):
        self.heading_confidence_threshold = heading_confidence_threshold
        self.font_scale_threshold = font_scale_threshold
        self._text_parser = TextResumeParser()

    def parse(
        self,
        geometry: DocumentGeometry,
        text_lines: list[str],
        urls: list[str],
    ) -> ResumeProfile:
        sections = self._run_state_machine(geometry)
        profile = self._text_parser.parse_sections(sections, urls)
        if geometry.table_skills:
            merged = list(profile.skills)
            seen = set(s.lower() for s in merged)
            for ts in geometry.table_skills:
                if ts.lower() not in seen:
                    seen.add(ts.lower())
                    merged.append(ts)
            profile = profile.model_copy(update={"skills": merged})
        return profile

    def _run_state_machine(self, geometry: DocumentGeometry) -> dict[str, list[str]]:
        accumulator = SectionAccumulator()
        state = State.HEADER

        page_medians: dict[int, float] = {
            p.page: _page_median_font(p) for p in geometry.pages
        }

        for page in geometry.pages:
            median_font = page_medians[page.page]
            header_zone_bottom = page.height * 0.18

            for line in page.lines:
                text = line.text.strip()
                if not text:
                    continue

                classified = _classify_line(line, median_font, self.font_scale_threshold)

                if (
                    classified.is_heading
                    and classified.heading_confidence >= self.heading_confidence_threshold
                ):
                    state = State.SECTION_BODY
                    accumulator.set_section(classified.section_key)

                elif state == State.HEADER:
                    in_header_zone = (
                        page.page == 0 and line.top <= header_zone_bottom
                    )
                    if in_header_zone:
                        accumulator.add_line(text)
                    else:
                        sig_section, sig_conf, _ = best_section([text])
                        if sig_section and sig_conf >= 0.55:
                            accumulator.set_section(sig_section)
                            state = State.SECTION_BODY
                        else:
                            accumulator.add_line(text)

                else:
                    accumulator.add_line(text)

        return _content_signature_reclassify(accumulator)

    def score(self, profile: ResumeProfile) -> int:
        return self._text_parser.score(profile)
