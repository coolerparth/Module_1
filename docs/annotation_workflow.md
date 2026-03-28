# Annotation Workflow

Use this workflow to build a 25-sample company-grade benchmark pack.

## 1. Generate scaffolds

```bash
./venv/bin/python scripts/scaffold_benchmark_pack.py
```

This creates 25 starter metadata files and 25 truth templates.

## 2. Add real resumes

Place the actual PDFs in a separate reviewed dataset directory, for example:

```text
data/resumes/reviewed/
```

Recommended mix:

- 5 single-column ATS resumes
- 5 two-column resumes
- 5 sidebar/design-heavy resumes
- 4 academic/research resumes
- 3 OCR/scanned resumes
- 3 intentionally messy exports

## 3. Fill metadata

For each sample metadata file:

- set `label_status`
- set `annotation_status`
- confirm `archetype`
- add any special notes such as:
  - `sidebar_left`
  - `table_skills`
  - `ocr_noise`
  - `multi_page`

## 4. Fill truth JSON carefully

Rules:

- only record evidence-backed values
- do not infer missing dates or URLs
- keep names and titles exact when possible
- use `null` or empty arrays instead of guessing
- keep project descriptions optional unless they matter for regression

## 5. Validate the pack

```bash
./venv/bin/python scripts/check_truth_pack.py
```

## 6. Run evaluation

```bash
./venv/bin/python scripts/evaluate.py data/resumes/reviewed data/ground_truth
```

## 7. Track parser regressions

For every parser change:

- compare overall score
- compare project score
- compare experience score
- check hallucination-style regressions manually

## Annotation priorities

Most important fields:

1. personal info
2. links
3. experience entries
4. education entries
5. project names
6. project technologies
7. skills

Descriptions, awards, and interests can be lighter-weight at the start.
