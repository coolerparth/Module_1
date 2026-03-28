from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .pdf_text_extractor import PDFTextExtractor
from .section_catalog import match_section_heading

_CORE_SECTIONS = frozenset({"header", "summary", "skills", "experience", "education", "projects"})


@dataclass(frozen=True)
class TextExtractionCandidate:
    source: str
    lines: list[str]
    urls: list[str]
    score: float
    heading_count: int
    core_section_count: int
    malformed_ratio: float
    short_line_ratio: float
    duplicate_ratio: float
    contact_signal_count: int


@dataclass
class TextExtractionResult:
    best_source: str | None
    lines: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    candidates: list[TextExtractionCandidate] = field(default_factory=list)


class DocumentTextExtractor:
    def __init__(self) -> None:
        self._pdf_extractor = PDFTextExtractor()

    def extract(self, path: str) -> tuple[list[str], list[str]]:
        result = self.extract_with_diagnostics(path)
        return result.lines, result.urls

    def extract_with_diagnostics(self, path: str) -> TextExtractionResult:
        suffix = Path(path).suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf_with_diagnostics(path)
        if suffix == ".docx":
            lines, urls = self._extract_docx(path)
            candidate = self._build_candidate("docx_xml", lines, urls)
            return TextExtractionResult(
                best_source=candidate.source,
                lines=candidate.lines,
                urls=candidate.urls,
                candidates=[candidate],
            )
        raise RuntimeError("Only PDF and DOCX files are supported.")

    def _extract_pdf_with_diagnostics(self, path: str) -> TextExtractionResult:
        candidates: list[TextExtractionCandidate] = []

        for source, fn in (
            ("pdfplumber", self._extract_with_pdfplumber),
            ("docling", self._extract_with_docling),
        ):
            try:
                lines, urls = fn(path)
            except Exception:
                continue
            if lines or urls:
                candidates.append(self._build_candidate(source, lines, urls))

        if not candidates:
            raise RuntimeError("No text extractor succeeded for this PDF.")

        best = self._select_best_candidate(candidates)
        rescued_lines = self._rescue_missing_sections(best, candidates)
        final_lines = best.lines + rescued_lines if rescued_lines else best.lines
        return TextExtractionResult(
            best_source=best.source,
            lines=final_lines,
            urls=self._merge_urls(*(candidate.urls for candidate in candidates)),
            candidates=candidates,
        )

    def _rescue_missing_sections(
        self,
        best: TextExtractionCandidate,
        candidates: list[TextExtractionCandidate],
    ) -> list[str]:
        rescued: list[str] = []
        for section_name in ("education",):
            best_block = self._extract_section_block(best.lines, section_name)
            best_quality = self._score_section_block(best_block, section_name)
            rescue_threshold = 2.0 if section_name == "education" else 1.0
            for candidate in candidates:
                if candidate.source == best.source:
                    continue
                block = self._extract_section_block(candidate.lines, section_name)
                if not block:
                    continue
                candidate_quality = self._score_section_block(block, section_name)
                if candidate_quality > best_quality + rescue_threshold:
                    rescued.extend(block)
                    break
        return rescued

    def _extract_section_block(self, lines: list[str], target: str) -> list[str]:
        block: list[str] = []
        active = False
        for line in lines:
            heading = match_section_heading(line)
            if heading == target:
                active = True
                block.append(line)
                continue
            if active and heading and heading != target:
                break
            if active:
                block.append(line)
        return block

    def _score_section_block(self, lines: list[str], target: str) -> float:
        if not lines:
            return 0.0

        content_lines = [line for line in lines if match_section_heading(line) != target]
        word_count = sum(len(line.split()) for line in content_lines)
        score = len(content_lines) + min(word_count / 8.0, 6.0)

        if target == "education":
            score += sum(
                1.0
                for line in content_lines
                if any(
                    token in line.lower()
                    for token in ("university", "college", "school", "academy", "b.tech", "class x", "class xii")
                )
            )

        return round(score, 3)

    def _extract_docx(self, path: str) -> tuple[list[str], list[str]]:
        lines: list[str] = []
        urls: list[str] = []
        seen_urls: set[str] = set()

        with zipfile.ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
            rel_map = self._read_relationships(archive)

        ns = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }
        root = ET.fromstring(document_xml)

        for paragraph in root.findall(".//w:p", ns):
            text = self._paragraph_text(paragraph)
            cleaned = self._clean_line(text)
            if cleaned:
                lines.append(cleaned)

            for hyperlink in paragraph.findall(".//w:hyperlink", ns):
                rel_id = hyperlink.attrib.get(f"{{{ns['r']}}}id")
                if not rel_id:
                    continue
                target = rel_map.get(rel_id, "").strip()
                if target.startswith(("http://", "https://")) and target not in seen_urls:
                    seen_urls.add(target)
                    urls.append(target)

        return lines, urls

    def _extract_with_pdfplumber(self, path: str) -> tuple[list[str], list[str]]:
        return self._pdf_extractor._extract_with_pdfplumber(path)

    def _extract_with_docling(self, path: str) -> tuple[list[str], list[str]]:
        from .docling_layout_extractor import DoclingLayoutExtractor

        geometry = DoclingLayoutExtractor().extract(path)
        lines = geometry.smart_ordered_lines() or geometry.ordered_lines()
        return lines, list(geometry.urls)

    def _build_candidate(
        self,
        source: str,
        lines: list[str],
        urls: list[str],
    ) -> TextExtractionCandidate:
        non_empty = [line.strip() for line in lines if line.strip()]
        heading_sections = [match_section_heading(line) for line in non_empty]
        headings = [section for section in heading_sections if section]
        unique_sections = set(headings)
        core_section_count = len(unique_sections & _CORE_SECTIONS)
        word_count = sum(len(line.split()) for line in non_empty)
        malformed_ratio = self._ratio(non_empty, self._looks_malformed)
        short_line_ratio = self._ratio(non_empty, lambda line: len(line.split()) <= 2)
        duplicate_ratio = 0.0
        if non_empty:
            duplicate_ratio = 1.0 - (len(set(non_empty)) / len(non_empty))
        contact_signal_count = self._contact_signal_count(non_empty[:8])

        score = (
            min(len(non_empty) / 30.0, 1.0) * 0.18
            + min(word_count / 220.0, 1.0) * 0.22
            + min(core_section_count / 4.0, 1.0) * 0.24
            + min(len(unique_sections) / 6.0, 1.0) * 0.12
            + min(len(urls) / 2.0, 1.0) * 0.06
            + (1.0 - min(short_line_ratio, 1.0)) * 0.08
            + (1.0 - min(duplicate_ratio, 1.0)) * 0.05
            + min(contact_signal_count / 3.0, 1.0) * 0.10
            - min(malformed_ratio, 1.0) * 0.20
        )
        if source == "docling" and core_section_count >= 2:
            score += 0.03
        if source == "pdfplumber" and len(non_empty) >= 12:
            score += 0.02
        if source == "pdfplumber" and contact_signal_count >= 2:
            score += 0.04
        score = round(max(score, 0.0), 3)

        return TextExtractionCandidate(
            source=source,
            lines=non_empty,
            urls=urls,
            score=score,
            heading_count=len(unique_sections),
            core_section_count=core_section_count,
            malformed_ratio=round(malformed_ratio, 3),
            short_line_ratio=round(short_line_ratio, 3),
            duplicate_ratio=round(duplicate_ratio, 3),
            contact_signal_count=contact_signal_count,
        )

    def _select_best_candidate(
        self,
        candidates: list[TextExtractionCandidate],
    ) -> TextExtractionCandidate:
        return max(
            candidates,
            key=lambda candidate: (
                candidate.score,
                candidate.core_section_count,
                candidate.heading_count,
                candidate.contact_signal_count,
                len(candidate.lines),
                -candidate.malformed_ratio,
            ),
        )

    def _contact_signal_count(self, lines: list[str]) -> int:
        count = 0
        for line in lines:
            if (
                re.search(r"@", line)
                or re.search(r"(?:\+?\d[\d\s\-()]{8,}\d)", line)
                or re.search(r"(?:linkedin|github|email|phone|mobile)", line, re.IGNORECASE)
            ):
                count += 1
        return count

    def _merge_urls(self, *url_lists: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for urls in url_lists:
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    merged.append(url)
        return merged

    def _read_relationships(self, archive: zipfile.ZipFile) -> dict[str, str]:
        rels_path = "word/_rels/document.xml.rels"
        if rels_path not in archive.namelist():
            return {}
        rel_root = ET.fromstring(archive.read(rels_path))
        return {
            rel.attrib.get("Id", ""): rel.attrib.get("Target", "")
            for rel in rel_root.findall("{*}Relationship")
            if rel.attrib.get("Id")
        }

    def _paragraph_text(self, paragraph: ET.Element) -> str:
        parts: list[str] = []
        for node in paragraph.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "t" and node.text:
                parts.append(node.text)
            elif tag in {"tab", "br", "cr"}:
                parts.append(" ")
        return "".join(parts)

    def _ratio(self, items: list[str], predicate) -> float:
        if not items:
            return 0.0
        return sum(1 for item in items if predicate(item)) / len(items)

    def _looks_malformed(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if len(stripped) >= 30 and " " not in stripped:
            return True
        alpha = sum(ch.isalpha() for ch in stripped)
        weird = sum(not (ch.isalnum() or ch.isspace() or ch in ".,:/&()-+%#@") for ch in stripped)
        return bool(alpha and weird / max(len(stripped), 1) > 0.12)

    def _clean_line(self, line: str) -> str:
        line = re.sub(r"[\x00-\x1f\x7f]", " ", line)
        line = line.replace("\u00a0", " ")
        line = re.sub(r"\s*,\s*", ", ", line)
        line = re.sub(r"\s+", " ", line).strip()
        return line
