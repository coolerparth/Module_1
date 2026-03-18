from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any

from ..models.resume import ResumeProfile
from .adaptive_resume_parser import AdaptiveResumeParser
from .content_signature_resume_parser import ContentSignatureResumeParser
from .deterministic_state_machine import DeterministicStateMachine
from .document_evidence import DocumentEvidence, DocumentEvidenceBuilder
from .document_geometry import GeometryExtractor
from .geometry_resume_parser import GeometryResumeParser
from .pdf_text_extractor import PDFTextExtractor
from .profile_consensus import ProfileConsensusEngine
from .profile_constraint_solver import ProfileConstraintSolver
from .section_graph_resume_parser import SectionGraphResumeParser
from .text_resume_parser import TextResumeParser


class DependencyError(RuntimeError):
    pass


class ResumeProcessor:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    @cached_property
    def _geometry_extractor(self) -> GeometryExtractor:
        return self._build(GeometryExtractor)

    @cached_property
    def _pdf_text_extractor(self) -> PDFTextExtractor:
        return self._build(PDFTextExtractor)

    @cached_property
    def _evidence_builder(self) -> DocumentEvidenceBuilder:
        return self._build(DocumentEvidenceBuilder)

    @cached_property
    def _dsm(self) -> DeterministicStateMachine:
        return self._build(DeterministicStateMachine)

    @cached_property
    def _text_parser(self) -> TextResumeParser:
        return self._build(TextResumeParser)

    @cached_property
    def _geometry_parser(self) -> GeometryResumeParser:
        return self._build(GeometryResumeParser)

    @cached_property
    def _section_graph_parser(self) -> SectionGraphResumeParser:
        return self._build(SectionGraphResumeParser)

    @cached_property
    def _content_sig_parser(self) -> ContentSignatureResumeParser:
        return self._build(ContentSignatureResumeParser)

    @cached_property
    def _adaptive_parser(self) -> AdaptiveResumeParser:
        return self._build(AdaptiveResumeParser)

    @cached_property
    def _consensus(self) -> ProfileConsensusEngine:
        return self._build(ProfileConsensusEngine)

    @cached_property
    def _solver(self) -> ProfileConstraintSolver:
        return self._build(ProfileConstraintSolver)

    def _build(self, factory):
        try:
            return factory()
        except RuntimeError as exc:
            raise DependencyError(str(exc)) from exc

    def process(self, pdf_path: Path) -> ResumeProfile:
        profile, _, _ = self.process_with_diagnostics(pdf_path)
        return profile

    def process_with_diagnostics(self, pdf_path: Path) -> tuple[ResumeProfile, list, DocumentEvidence]:
        geometry = self._geometry_extractor.extract(str(pdf_path))
        lines, urls = self._pdf_text_extractor.extract(str(pdf_path))
        evidence = self._evidence_builder.build(geometry=geometry, text_lines=lines)

        strategies: list[tuple[str, ResumeProfile]] = []

        def collect(name: str, fn) -> None:
            try:
                strategies.append((name, fn()))
            except Exception:
                pass

        collect("deterministic_fusion",
                lambda: self._dsm.parse(geometry=geometry, text_lines=lines, urls=urls))
        collect("text_lines",
                lambda: self._text_parser.parse(lines, urls))
        collect("ordered_geometry",
                lambda: self._geometry_parser.parse_geometry(geometry))
        collect("section_graph",
                lambda: self._section_graph_parser.parse_geometry(geometry))
        collect("content_signature",
                lambda: self._content_sig_parser.parse_geometry(geometry))
        collect("adaptive_boundary",
                lambda: self._adaptive_parser.parse_geometry(geometry))

        if not strategies:
            raise RuntimeError("No extraction strategy produced a profile.")

        results = [self._consensus.evaluate(name, profile, evidence) for name, profile in strategies]

        merged  = self._consensus.merge(results)
        repaired = self._solver.repair(merged, results, evidence)
        repaired_result = self._consensus.evaluate("repaired", repaired, evidence)

        final = max(results + [repaired_result], key=lambda r: r.global_score)
        if final.global_score < 0.40:
            raise DependencyError(
                f"Best parser confidence {final.global_score:.2f} too low. "
                "PDF may be scanned or image-based."
            )
        results.append(repaired_result)
        return final.profile, results, evidence

    def save_output(self, output_dict: dict[str, Any], original_filename: str | None) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in Path(original_filename or "resume").stem
        )
        output_file = self.output_dir / f"{safe_stem}_extracted.json"
        with output_file.open("w", encoding="utf-8") as fh:
            json.dump(output_dict, fh, indent=4, ensure_ascii=False)
        return output_file
