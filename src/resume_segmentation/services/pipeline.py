from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .career_intelligence import CareerIntelligence, CareerIntelligenceAnalyzer
from .confidence_engine import ConfidenceEngine, ConfidenceReport
from .document_evidence import DocumentEvidence
from .gpa_normalizer import NormalizedGPA, normalize_gpa
from .resume_processor import DependencyError, ResumeProcessor
from .resume_quality_reporter import QualityReport, ResumeQualityReporter
from .skills_normalizer import (
    NormalizedSkill, canonicalize_skills, group_skills_by_category,
    get_tech_stack_score, normalize_skills_list,
)
from .timeline_validator import TimelineReport, TimelineValidator
from ..models.resume import ResumeProfile
from ..settings import settings

SCHEMA_VERSION = "3.1.0"


@dataclass
class ResumeEnrichment:
    normalized_skills: list[NormalizedSkill] = field(default_factory=list)
    skills_by_category: dict[str, list[str]] = field(default_factory=dict)
    tech_stack_score: float = 0.0
    career_intelligence: Optional[CareerIntelligence] = None
    quality_report: Optional[QualityReport] = None
    timeline_report: Optional[TimelineReport] = None
    gpa_normalized: list[dict] = field(default_factory=list)
    detected_language: str = "English"
    layout: str = "single_column"
    page_count: int = 1
    word_count: int = 0
    processing_time_ms: int = 0

    def to_dict(self) -> dict:
        ci = self.career_intelligence
        qr = self.quality_report
        tr = self.timeline_report
        return {
            "normalized_skills": [
                {
                    "canonical": ns.canonical, "category": ns.category.value,
                    "weight": ns.weight, "level": ns.level,
                    "was_normalized": ns.was_normalized,
                }
                for ns in self.normalized_skills
            ],
            "skills_by_category": self.skills_by_category,
            "tech_stack_score": self.tech_stack_score,
            "career_intelligence": {
                "career_level": ci.career_level.value,
                "total_years_experience": ci.total_years_experience,
                "primary_domain": ci.primary_domain.value,
                "domain_scores": ci.domain_scores,
                "title": ci.title_from_experience,
                "current_employer": ci.current_employer,
                "notable_companies": ci.notable_companies,
                "notable_universities": ci.notable_universities,
                "career_gaps": ci.career_gaps,
                "is_fresher": ci.is_fresher,
                "has_management_experience": ci.has_management_experience,
                "seniority_score": ci.seniority_score,
                "tech_stack_summary": ci.tech_stack_summary,
            } if ci else None,
            "quality_report": qr.to_dict() if qr else None,
            "timeline": tr.to_dict() if tr else None,
            "gpa_normalized": self.gpa_normalized,
            "detected_language": self.detected_language,
            "layout": self.layout,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "processing_time_ms": self.processing_time_ms,
        }


@dataclass
class ExtractionResult:
    profile: ResumeProfile
    enrichment: ResumeEnrichment
    confidence: ConfidenceReport
    strategy_results: list = field(default_factory=list)
    evidence: Optional[DocumentEvidence] = None
    error: Optional[str] = None
    success: bool = True

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "success": self.success,
            "error": self.error,
            "profile": self.profile.model_dump() if self.profile else None,
            "enrichment": self.enrichment.to_dict(),
            "confidence": self.confidence.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @property
    def profile_dict(self) -> dict:
        return self.profile.model_dump() if self.profile else {}


def _detect_language(text_lines: list[str]) -> str:
    sample = " ".join(text_lines[:30]).lower()
    if any("\u0900" <= c <= "\u097f" for c in sample):
        return "Hindi"
    if any("\u0600" <= c <= "\u06ff" for c in sample):
        return "Arabic"
    if any("\u4e00" <= c <= "\u9fff" for c in sample):
        return "Japanese" if any("\u3040" <= c <= "\u30ff" for c in sample) else "Chinese"
    if sum(1 for w in {"experiencia", "habilidades", "educacion", "educación", "idiomas"} if w in sample) >= 2:
        return "Spanish"
    if sum(1 for w in {"expérience", "compétences", "competences", "formation", "langues"} if w in sample) >= 2:
        return "French"
    if sum(1 for w in {"berufserfahrung", "ausbildung", "kenntnisse", "sprachen"} if w in sample) >= 2:
        return "German"
    if sum(1 for w in {"experiência", "formação", "competências", "idiomas", "projetos"} if w in sample) >= 2:
        return "Portuguese"
    return "English"


def _normalize_education_gpas(profile: ResumeProfile) -> list[dict]:
    results = []
    for entry in profile.education:
        if not entry.gpa:
            continue
        ng = normalize_gpa(entry.gpa)
        if ng.is_valid:
            results.append({
                "institution": entry.institution,
                "raw": ng.raw,
                "percentage": ng.percentage,
                "gpa_4": ng.gpa_4,
                "cgpa_10": ng.cgpa_10,
                "scale": ng.scale,
                "display": ng.display,
            })
    return results


class ARIEPipeline:

    def __init__(self, output_dir: Optional[Path] = None):
        self._output_dir = output_dir or settings.output_dir
        self._processor = ResumeProcessor(output_dir=self._output_dir)
        self._confidence_engine = ConfidenceEngine()
        self._career_analyzer = CareerIntelligenceAnalyzer()
        self._quality_reporter = ResumeQualityReporter()
        self._timeline_validator = TimelineValidator()

    def extract(self, pdf_path: str | Path) -> ExtractionResult:
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            return self._error_result(f"File not found: {pdf_path}", time.monotonic())
        if pdf_path.stat().st_size < 100:
            return self._error_result("File is empty or corrupt.", time.monotonic())
        if pdf_path.suffix.lower() != ".pdf":
            return self._error_result("Only PDF files are supported.", time.monotonic())

        start_time = time.monotonic()

        try:
            profile, strategy_results, evidence = self._processor.process_with_diagnostics(pdf_path)
        except DependencyError as exc:
            return self._error_result(str(exc), start_time)
        except Exception as exc:
            return self._error_result(f"Extraction failed: {exc}", start_time)

        normalized_skills = normalize_skills_list(profile.skills)
        skills_by_category = group_skills_by_category(profile.skills)
        tech_score = get_tech_stack_score(profile.skills)
        canonical_skills = [ns.canonical for ns in normalized_skills]
        profile = profile.model_copy(update={"skills": canonical_skills})

        text_lines: list[str] = []
        try:
            from .pdf_text_extractor import PDFTextExtractor
            text_lines, _ = PDFTextExtractor().extract(str(pdf_path))
        except Exception:
            pass

        language = _detect_language(text_lines)
        layout = "single_column"
        page_count = 1
        try:
            from .document_geometry import GeometryExtractor
            geom = GeometryExtractor().extract(str(pdf_path))
            page_count = len(geom.pages)
            layout = "two_column" if "two_column" in [p.layout for p in geom.pages] else "single_column"
        except Exception:
            pass

        word_count = sum(len(line.split()) for line in text_lines)
        career_intel = self._career_analyzer.analyze(profile)
        quality_report = self._quality_reporter.analyze(profile, layout)
        timeline_report = self._timeline_validator.validate(profile)
        gpa_normalized = _normalize_education_gpas(profile)
        confidence = self._confidence_engine.score(profile, strategy_results, evidence)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        enrichment = ResumeEnrichment(
            normalized_skills=normalized_skills,
            skills_by_category=skills_by_category,
            tech_stack_score=tech_score,
            career_intelligence=career_intel,
            quality_report=quality_report,
            timeline_report=timeline_report,
            gpa_normalized=gpa_normalized,
            detected_language=language,
            layout=layout,
            page_count=page_count,
            word_count=word_count,
            processing_time_ms=elapsed_ms,
        )

        return ExtractionResult(
            profile=profile,
            enrichment=enrichment,
            confidence=confidence,
            strategy_results=strategy_results,
            evidence=evidence,
            success=True,
        )

    def extract_batch(self, pdf_paths: list[str | Path]) -> list[ExtractionResult]:
        return [self.extract(p) for p in pdf_paths]

    def save(self, result: ExtractionResult, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.to_json(), encoding="utf-8")
        return output_path

    def _error_result(self, error_msg: str, start_time: float) -> ExtractionResult:
        from ..models.resume import PersonalInfo
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        empty_profile = ResumeProfile(personal_info=PersonalInfo())
        empty_enrichment = ResumeEnrichment(processing_time_ms=elapsed_ms)
        empty_confidence = ConfidenceReport(overall=0.0, grade="F", warnings=[error_msg])
        return ExtractionResult(
            profile=empty_profile,
            enrichment=empty_enrichment,
            confidence=empty_confidence,
            success=False,
            error=error_msg,
        )
