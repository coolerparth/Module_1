# Company-Grade Parser Roadmap

This project is now organized around three principles:

1. Deterministic extraction
2. Validation-driven repair
3. Benchmark-driven iteration

## Immediate focus areas

- `projects_parser.py`
  Project boundaries, URL extraction, tech stack inference, and crushed-text cleanup.
- `knowledge/*.yml`
  Data-driven ontologies for section headings, skill aliases, and project technologies.
- multi-resume benchmark pack
  Use `scripts/scaffold_benchmark_pack.py` to generate labeled-fixture templates.

## Recommended benchmark pack composition

- 5 single-column ATS resumes
- 5 two-column/sidebar resumes
- 3 academic/research resumes
- 3 project-heavy fresher resumes
- 3 senior/multi-page resumes
- 3 difficult OCR/table-heavy resumes
- 3 intentionally messy edge cases

## Quality gates

- Contact info exact-match >= 0.99 on supported resumes
- Experience/Education entry F1 >= 0.95
- Project name match >= 0.95
- Project technology precision >= 0.90
- Hallucination rate = 0.0
- Unsupported/non-English inputs must fail explicitly

## Scaffold usage

```bash
./venv/bin/python scripts/scaffold_benchmark_pack.py
```

This creates:

- `data/benchmark/templates/metadata/*.json`
- `data/benchmark/templates/ground_truth/*.truth.json`
- `data/benchmark/templates/scaffold_manifest.json`

Use those files as the starting point for a 10, 25, or 100 resume gold set.
