"""
cli.py — ARIA Command Line Interface

Usage examples:
  # Extract a single resume
  python -m resume_segmentation.cli extract resume.pdf

  # Extract and save to file
  python -m resume_segmentation.cli extract resume.pdf --output result.json

  # Extract with full enrichment
  python -m resume_segmentation.cli extract resume.pdf --enrich

  # Batch process a directory
  python -m resume_segmentation.cli batch ./resumes/ --output ./results/

  # Show quality report
  python -m resume_segmentation.cli quality resume.pdf

  # Anonymize before extraction
  python -m resume_segmentation.cli extract resume.pdf --anonymize

  # Start the REST API server
  python -m resume_segmentation.cli serve --port 8000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def _get_pipeline():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from resume_segmentation.services.pipeline import ARIEPipeline
    return ARIEPipeline()


def cmd_extract(args):
    pdf = Path(args.pdf)
    if not pdf.exists():
        print(f"Error: {pdf} not found", file=sys.stderr)
        return 1

    pipeline = _get_pipeline()
    print(f"Extracting: {pdf.name} ...", end=" ", flush=True)
    t0 = time.monotonic()
    result = pipeline.extract(pdf)
    elapsed = time.monotonic() - t0
    print(f"done ({elapsed*1000:.0f}ms)")

    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    output = result.to_dict() if args.enrich else result.profile.model_dump()

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved: {out_path}")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

    if args.summary:
        pi = result.profile.personal_info
        print(f"\n── Summary ──────────────────────────────")
        print(f"  Name:       {pi.name}")
        print(f"  Email:      {pi.email}")
        print(f"  Phone:      {pi.phone}")
        print(f"  Location:   {pi.location}")
        if result.enrichment.career_intelligence:
            ci = result.enrichment.career_intelligence
            print(f"  Level:      {ci.career_level.value}")
            print(f"  Experience: {ci.total_years_experience} years")
            print(f"  Domain:     {ci.primary_domain.value}")
        print(f"  Confidence: {result.confidence.overall:.0%} ({result.confidence.grade})")
        print(f"  Skills:     {', '.join(result.profile.skills[:8])}")
        print(f"  Experience: {len(result.profile.experience)} entries")
        print(f"  Education:  {len(result.profile.education)} entries")
        print(f"  Projects:   {len(result.profile.projects)} entries")
    return 0


def cmd_quality(args):
    pdf = Path(args.pdf)
    if not pdf.exists():
        print(f"Error: {pdf} not found", file=sys.stderr)
        return 1

    pipeline = _get_pipeline()
    result = pipeline.extract(pdf)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    from resume_segmentation.services.resume_quality_reporter import ResumeQualityReporter
    layout = result.enrichment.layout
    report = ResumeQualityReporter().analyze(result.profile, layout)

    print(f"\n── Quality Report: {pdf.name} ─────────────────")
    print(f"  ATS Score:      {report.ats_score:.0f}/100  ({report.ats_grade})")
    print(f"  Completeness:   {report.completeness_score:.0f}/100")
    print(f"  Bullet Quality: {report.bullet_score:.0f}/100")
    print(f"  Overall:        {report.overall_score:.0f}/100  ({report.overall_grade})")

    if report.missing_fields:
        print(f"\n  Missing: {', '.join(report.missing_fields)}")

    if report.suggestions:
        print("\n  Top suggestions:")
        for s in report.suggestions[:5]:
            print(f"    [{s.priority}] [{s.category}] {s.message}")
            if s.example:
                print(f"         Example: {s.example}")

    if report.weak_bullets:
        print("\n  Bullets to improve:")
        for b in report.weak_bullets:
            print(f"    • {b[:80]}")

    return 0


def cmd_batch(args):
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(input_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {input_dir}")
        return 1

    pipeline = _get_pipeline()
    print(f"Processing {len(pdfs)} files → {output_dir}")
    ok = errors = 0

    for pdf in pdfs:
        print(f"  {pdf.name} ...", end=" ", flush=True)
        result = pipeline.extract(pdf)
        if result.success:
            out = output_dir / f"{pdf.stem}_extracted.json"
            out.write_text(result.to_json(), encoding="utf-8")
            ci = result.enrichment.career_intelligence
            level = ci.career_level.value if ci else "?"
            print(f"✓  conf={result.confidence.overall:.0%}  {level}")
            ok += 1
        else:
            print(f"✗  {result.error}")
            errors += 1

    print(f"\nDone: {ok} ok, {errors} errors")
    return 0 if errors == 0 else 1


def cmd_serve(args):
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Run: pip install uvicorn[standard]")
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    uvicorn.run(
        "resume_segmentation.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="aria",
        description="A.R.I.E. — Automated Resume Intelligence Engine",
    )
    sub = parser.add_subparsers(dest="command")

             
    p_extract = sub.add_parser("extract", help="Extract a single PDF resume")
    p_extract.add_argument("pdf", help="Path to PDF file")
    p_extract.add_argument("-o", "--output", help="Output JSON file path")
    p_extract.add_argument("--enrich", action="store_true",
                            help="Include enrichment (career intel, confidence, etc.)")
    p_extract.add_argument("--summary", action="store_true",
                            help="Print a human-readable summary")
    p_extract.add_argument("--anonymize", action="store_true",
                            help="Mask PII before output")

             
    p_quality = sub.add_parser("quality", help="Show resume quality & ATS report")
    p_quality.add_argument("pdf", help="Path to PDF file")

           
    p_batch = sub.add_parser("batch", help="Batch extract all PDFs in a directory")
    p_batch.add_argument("input_dir", help="Directory containing PDF resumes")
    p_batch.add_argument("-o", "--output", default="./results",
                          help="Output directory (default: ./results)")

           
    p_serve = sub.add_parser("serve", help="Start REST API server")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        "extract": cmd_extract,
        "quality": cmd_quality,
        "batch": cmd_batch,
        "serve": cmd_serve,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
