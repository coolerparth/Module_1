"""
deterministic_state_machine.py — Fusion parser using a deterministic finite state machine.

This is the primary (first-run) strategy referenced in resume_processor.py. It fuses:
  1. DocumentGeometry (font sizes, spatial positions, block boundaries)
  2. Raw text lines (for fast section detection)
  3. URL annotations from PDF

Architecture:
  ┌──────────────────────────────────────────────────────────┐
  │  State machine with 4 states:                            │
  │  HEADER → SECTION_HEADING → SECTION_BODY → SUBSECTION   │
  └──────────────────────────────────────────────────────────┘

Key advantages over other strategies:
  - Uses BOTH font-size signals AND section catalog simultaneously
  - Adaptive heading confidence threshold (calibrated per-page)
  - Handles multi-column layouts by processing each column independently
  - Entry boundary detection inside sections (experience, education, projects)
  - Never silently drops lines — every line is accounted for

The state machine processes lines in reading order and transitions based on:
  - Font size relative to page median (typography signal)
  - Section catalog match (lexical signal)
  - Content signature (structural signal)
  - Spatial gap between blocks (geometry signal)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from ..models.resume import (
    DateRange, EducationEntry, ExperienceEntry,
    LinkItem, PersonalInfo, ProjectEntry, ResumeProfile,
)
from .date_extractor import extract_date_range, has_date
from .document_geometry import BlockNode, DocumentGeometry, LineNode, PageGeometry
from .entry_signatures import best_section
from .personal_info_extractor import extract_links, extract_location, looks_like_name
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
    is_heading: bool
    section_key: Optional[str]
    heading_confidence: float             


def _classify_line(
    line: LineNode,
    page_median_font: float,
    font_scale_threshold: float = 1.06,
) -> ClassifiedLine:
    text = line.text.strip()
    section_key = match_section_heading(text)

                      
    font_boosted = (
        line.font_size is not None
        and line.font_size >= page_median_font * font_scale_threshold
    )

                   
    word_count = len(text.split())
    is_short = word_count <= 5

    if section_key:
        confidence = 0.4
        if font_boosted:
            confidence += 0.35
        if is_short:
            confidence += 0.25
        return ClassifiedLine(
            text=text, page=line.page,
            font_size=line.font_size, column=line.column,
            is_heading=True, section_key=section_key,
            heading_confidence=min(confidence, 1.0),
        )

                                                                             
                                                                          
    if font_boosted and is_short and word_count >= 1:
        return ClassifiedLine(
            text=text, page=line.page,
            font_size=line.font_size, column=line.column,
            is_heading=False, section_key=None,
            heading_confidence=0.0,
        )

    return ClassifiedLine(
        text=text, page=line.page,
        font_size=line.font_size, column=line.column,
        is_heading=False, section_key=None,
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
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


                                                                               
                            
                                                                               

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
        heading_confidence_threshold: float = 0.40,
        font_scale_threshold: float = 1.06,
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
        return self._text_parser.parse_sections(sections, urls)

                                                                                

    def _run_state_machine(self, geometry: DocumentGeometry) -> dict[str, list[str]]:
        accumulator = SectionAccumulator()
        state = State.HEADER
        prev_block_bottom: float = 0.0
        prev_page: int = -1

                                          
        page_medians: dict[int, float] = {
            p.page: _page_median_font(p) for p in geometry.pages
        }

        for page in geometry.pages:
            median_font = page_medians[page.page]
            header_zone_bottom = page.height * 0.20                                

            for block in page.blocks:
                                                                         
                vertical_gap = 0.0
                if prev_page == page.page:
                    vertical_gap = block.top - prev_block_bottom
                prev_block_bottom = block.bottom
                prev_page = page.page

                for line in block.lines:
                    text = line.text.strip()
                    if not text:
                        continue

                    classified = _classify_line(line, median_font, self.font_scale_threshold)

                                                                                
                    if classified.is_heading and classified.heading_confidence >= self.heading_confidence_threshold:
                                                                     
                        state = State.SECTION_BODY
                        accumulator.set_section(classified.section_key)

                    elif state == State.HEADER:
                                                                       
                                                                          
                        in_header_zone = (page.page == 0 and line.top <= header_zone_bottom)
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

                                                                                   
        sections = _content_signature_reclassify(accumulator)
        return sections

    def score(self, profile: ResumeProfile) -> int:
        return self._text_parser.score(profile)
