# Benchmarking

This project now supports a simple golden-fixture benchmarking flow.

## Ground truth layout

- PDFs live in a source directory, for example the repo root or a dataset folder.
- Hand-labeled truth JSON lives in `data/ground_truth/` using the naming pattern:
  `resume_name.truth.json`
- Optional metadata for benchmark manifests lives in `data/benchmark/metadata/`.

## Included sample

- Sample PDF: `ADev_Resume.pdf`
- Ground truth: `data/ground_truth/ADev_Resume.truth.json`
- Metadata: `data/benchmark/metadata/ADev_Resume.json`

## Run evaluation

Normalize common dataset link issues before validation when needed:

```bash
./venv/bin/python scripts/normalize_resume_dataset.py Resume_(PDF)files
```

Validate `Resume_(PDF)files/resume_dataset.json` before benchmarking:

```bash
./venv/bin/python scripts/validate_resume_dataset_schema.py Resume_(PDF)files
```

Evaluate extracted output against labeled truth:

```bash
./venv/bin/python scripts/evaluate.py . data/ground_truth
```

Evaluate the resume dataset benchmark pack:

```bash
./venv/bin/python scripts/evaluate_resume_dataset.py Resume_(PDF)files
```

Build a benchmark manifest:

```bash
./venv/bin/python scripts/build_manifest.py . --truth-dir data/ground_truth --metadata-dir data/benchmark/metadata
```

Run lightweight regression tests:

```bash
./venv/bin/python -m unittest discover -s tests -v
```

## How to expand the benchmark set

1. Add a PDF.
2. Create `data/ground_truth/<name>.truth.json`.
3. Optionally create `data/benchmark/metadata/<name>.json`.
4. Re-run `scripts/evaluate.py`.
5. If the sample captures a known tricky pattern, add a dedicated regression test.

## Recommended labeling strategy

- Keep contact fields exact.
- Keep skills representative, not necessarily exhaustive.
- Keep project names exact and descriptions optional unless that field matters for the regression.
- Prefer stable assertions over brittle ones.
