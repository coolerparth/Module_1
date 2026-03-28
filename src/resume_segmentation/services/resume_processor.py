from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from ..models.resume import ResumeProfile
from .adaptive_resume_parser import AdaptiveResumeParser
from .content_signature_resume_parser import ContentSignatureResumeParser
from .deterministic_state_machine import DeterministicStateMachine
from .document_evidence import DocumentEvidence, DocumentEvidenceBuilder
from .document_geometry import DocumentGeometry, GeometryExtractor
from .document_text_extractor import DocumentTextExtractor
from .geometry_resume_parser import GeometryResumeParser
from .profile_consensus import ProfileConsensusEngine
from .profile_constraint_solver import ProfileConstraintSolver
from .section_graph_resume_parser import SectionGraphResumeParser
from .text_resume_parser import TextResumeParser


class DependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeometryCandidate:
    source: str
    geometry: DocumentGeometry
    score: float
    line_count: int
    block_count: int
    section_count: int
    heading_count: int
    page_coverage: float
    table_skill_count: int


class ResumeProcessor:

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self._last_extractor_report: dict[str, Any] = {"text": None, "geometry": None}

    @property
    def last_extractor_report(self) -> dict[str, Any]:
        return copy.deepcopy(self._last_extractor_report)

    @cached_property
    def _docling_extractor(self):
        from .docling_layout_extractor import DoclingLayoutExtractor
        return DoclingLayoutExtractor()

    @cached_property
    def _geometry_extractor(self) -> GeometryExtractor:
        return GeometryExtractor()

    @cached_property
    def _document_text_extractor(self) -> DocumentTextExtractor:
        return DocumentTextExtractor()

    @cached_property
    def _evidence_builder(self) -> DocumentEvidenceBuilder:
        return DocumentEvidenceBuilder()

    @cached_property
    def _dsm(self) -> DeterministicStateMachine:
        return DeterministicStateMachine()

    @cached_property
    def _text_parser(self) -> TextResumeParser:
        return TextResumeParser()

    @cached_property
    def _geometry_parser(self) -> GeometryResumeParser:
        return GeometryResumeParser()

    @cached_property
    def _section_graph_parser(self) -> SectionGraphResumeParser:
        return SectionGraphResumeParser()

    @cached_property
    def _content_sig_parser(self) -> ContentSignatureResumeParser:
        return ContentSignatureResumeParser()

    @cached_property
    def _adaptive_parser(self) -> AdaptiveResumeParser:
        return AdaptiveResumeParser()

    @cached_property
    def _consensus(self) -> ProfileConsensusEngine:
        return ProfileConsensusEngine()

    @cached_property
    def _solver(self) -> ProfileConstraintSolver:
        return ProfileConstraintSolver()

    def process(self, pdf_path: Path) -> ResumeProfile:
        profile, _, _ = self.process_with_diagnostics(pdf_path)
        return profile

    def process_with_diagnostics(
        self, pdf_path: Path
    ) -> tuple[ResumeProfile, list, DocumentEvidence]:
        self._last_extractor_report = {"text": None, "geometry": None}
        suffix = pdf_path.suffix.lower()
        geometry = self._extract_geometry(str(pdf_path)) if suffix == ".pdf" else None
        text_result = self._document_text_extractor.extract_with_diagnostics(str(pdf_path))
        self._last_extractor_report["text"] = {
            "best_source": text_result.best_source,
            "candidate_count": len(text_result.candidates),
            "candidates": [self._text_candidate_to_dict(candidate) for candidate in text_result.candidates],
        }
        lines = text_result.lines
        urls = self._merge_urls(
            text_result.urls,
            geometry.urls if geometry is not None else [],
        )
        evidence = self._evidence_builder.build(geometry=geometry, text_lines=lines)

        strategies: list[tuple[str, ResumeProfile]] = []

        def collect(name: str, fn) -> None:
            try:
                strategies.append((name, fn()))
            except Exception:
                pass

        if geometry is not None:
            collect(
                "deterministic_fusion",
                lambda: self._dsm.parse(geometry=geometry, text_lines=lines, urls=urls),
            )
        collect("text_lines", lambda: self._text_parser.parse(lines, urls))
        if geometry is not None:
            collect(
                "ordered_geometry",
                lambda: self._geometry_parser.parse_geometry(geometry),
            )
            collect(
                "section_graph",
                lambda: self._section_graph_parser.parse_geometry(geometry),
            )
            collect(
                "content_signature",
                lambda: self._content_sig_parser.parse_geometry(geometry),
            )
            collect(
                "adaptive_boundary",
                lambda: self._adaptive_parser.parse_geometry(geometry),
            )

        if not strategies:
            raise DependencyError(
                "No extraction strategy produced any output. "
                "Document may be completely empty or corrupted."
            )

        results = [
            self._consensus.evaluate(name, profile, evidence)
            for name, profile in strategies
        ]

        merged = self._consensus.merge(results)
        repaired = self._solver.repair(merged, results, evidence)
        repaired_result = self._consensus.evaluate("repaired", repaired, evidence)

        results.append(repaired_result)
        final = max(results, key=lambda r: r.global_score)

        return final.profile, results, evidence

    def _extract_geometry(self, pdf_path: str) -> DocumentGeometry:
        candidates: list[GeometryCandidate] = []
        errors: dict[str, Exception] = {}

        for source, extractor in (
            ("docling", self._docling_extractor),
            ("pdfplumber", self._geometry_extractor),
        ):
            try:
                geometry = extractor.extract(pdf_path)
            except Exception as exc:
                errors[source] = exc
                continue
            candidates.append(self._score_geometry_candidate(source, geometry))

        if not candidates:
            error_text = (
                "Both Docling and geometry extractors failed. "
                f"Docling: {errors.get('docling')}. Geometry: {errors.get('pdfplumber')}"
            )
            self._last_extractor_report["geometry"] = {
                "best_source": None,
                "candidate_count": 0,
                "candidates": [],
                "error": error_text,
            }
            raise DependencyError(error_text)

        best = self._select_best_geometry_candidate(candidates)
        others = [candidate for candidate in candidates if candidate.source != best.source]
        merged = self._merge_geometry_signals(best, others)
        self._last_extractor_report["geometry"] = {
            "best_source": best.source,
            "candidate_count": len(candidates),
            "candidates": [self._geometry_candidate_to_dict(candidate) for candidate in candidates],
            "selected_layouts": [page.layout for page in merged.pages],
            "url_count": len(merged.urls),
            "table_skill_count": len(merged.table_skills),
        }
        return merged

    def _score_geometry_candidate(
        self,
        source: str,
        geometry: DocumentGeometry,
    ) -> GeometryCandidate:
        evidence = self._evidence_builder.build(geometry=geometry)
        line_count = sum(len(page.lines) for page in geometry.pages)
        block_count = sum(len(page.blocks) for page in geometry.pages)
        page_count = max(len(geometry.pages), 1)
        pages_with_lines = sum(1 for page in geometry.pages if page.lines)
        page_coverage = pages_with_lines / page_count if geometry.pages else 0.0
        two_column_pages = sum(1 for page in geometry.pages if page.layout == "two_column")
        font_lines = sum(
            1
            for page in geometry.pages
            for line in page.lines
            if line.font_size is not None
        )
        font_coverage = font_lines / line_count if line_count else 0.0
        section_count = len(evidence.present_sections)
        heading_count = len(evidence.headings)
        table_skill_count = len(geometry.table_skills)
        url_count = len(geometry.urls)

        score = (
            min(line_count / 60.0, 1.0) * 0.28
            + min(block_count / 20.0, 1.0) * 0.08
            + min(section_count / 5.0, 1.0) * 0.24
            + min(heading_count / 8.0, 1.0) * 0.12
            + page_coverage * 0.10
            + min(url_count / 2.0, 1.0) * 0.04
            + min(table_skill_count / 4.0, 1.0) * 0.06
            + (two_column_pages / page_count) * 0.05
            + font_coverage * 0.03
        )
        if source == "docling" and table_skill_count:
            score += 0.04
        if source == "pdfplumber" and two_column_pages:
            score += 0.03
        if source == "pdfplumber" and font_coverage >= 0.75:
            score += 0.02

        return GeometryCandidate(
            source=source,
            geometry=geometry,
            score=round(score, 3),
            line_count=line_count,
            block_count=block_count,
            section_count=section_count,
            heading_count=heading_count,
            page_coverage=round(page_coverage, 3),
            table_skill_count=table_skill_count,
        )

    def _select_best_geometry_candidate(
        self,
        candidates: list[GeometryCandidate],
    ) -> GeometryCandidate:
        return max(
            candidates,
            key=lambda candidate: (
                candidate.score,
                candidate.section_count,
                candidate.heading_count,
                candidate.line_count,
                candidate.block_count,
            ),
        )

    def _merge_geometry_signals(
        self,
        primary: GeometryCandidate,
        secondary: list[GeometryCandidate],
    ) -> DocumentGeometry:
        merged = copy.deepcopy(primary.geometry)
        merged.source_engine = primary.source

        for candidate in secondary:
            for url in candidate.geometry.urls:
                if url not in merged.urls:
                    merged.urls.append(url)

            existing_skills = {skill.casefold() for skill in merged.table_skills}
            for skill in candidate.geometry.table_skills:
                folded = skill.casefold()
                if folded not in existing_skills:
                    existing_skills.add(folded)
                    merged.table_skills.append(skill)

        return merged

    def _merge_urls(self, *url_lists: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for urls in url_lists:
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    merged.append(url)
        return merged

    def _text_candidate_to_dict(self, candidate) -> dict[str, Any]:
        return {
            "source": candidate.source,
            "score": candidate.score,
            "heading_count": candidate.heading_count,
            "core_section_count": candidate.core_section_count,
            "line_count": len(candidate.lines),
            "url_count": len(candidate.urls),
            "malformed_ratio": candidate.malformed_ratio,
            "short_line_ratio": candidate.short_line_ratio,
            "duplicate_ratio": candidate.duplicate_ratio,
            "contact_signal_count": candidate.contact_signal_count,
        }

    def _geometry_candidate_to_dict(self, candidate: GeometryCandidate) -> dict[str, Any]:
        return {
            "source": candidate.source,
            "score": candidate.score,
            "line_count": candidate.line_count,
            "block_count": candidate.block_count,
            "section_count": candidate.section_count,
            "heading_count": candidate.heading_count,
            "page_coverage": candidate.page_coverage,
            "table_skill_count": candidate.table_skill_count,
            "layouts": [page.layout for page in candidate.geometry.pages],
            "url_count": len(candidate.geometry.urls),
        }

    def save_output(
        self, output_dict: dict[str, Any], original_filename: str | None
    ) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in Path(original_filename or "resume").stem
        )
        output_file = self.output_dir / f"{safe_stem}_extracted.json"
        with output_file.open("w", encoding="utf-8") as fh:
            json.dump(output_dict, fh, indent=4, ensure_ascii=False)
        return output_file
