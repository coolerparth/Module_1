from __future__ import annotations

import re
from typing import Any


_HEADER_SKIP = frozenset({
    "languages", "language", "frameworks", "framework", "libraries", "library",
    "tools", "tool", "technologies", "technology", "platforms", "platform",
    "databases", "database", "cloud", "skills", "skill", "category",
    "proficiency", "level", "rating", "score", "expertise",
    "beginner", "intermediate", "advanced", "expert", "proficient",
    "basic", "familiar", "experienced", "competent",
    "name", "type", "domain", "area", "stack",
})

_RATING_RE = re.compile(
    r"^[\d.]+\s*(?:/\s*[\d.]+)?$"
    r"|^[\d]+\s*(?:year|yr|month|mon)s?\b",
    re.IGNORECASE,
)

_STAR_RE = re.compile(r"^[\u2605\u2606\u25cf\u25cb\u25c9\u25ce\u25cc\s]{1,15}$")

_NOISE_RE = re.compile(
    r"^[\s\-\u2013\u2014|/\\.,;:!?*\u2022\u25b8\u25ba\u25cf\u25b6]+$"
)


def extract_skills_from_table(table_item: Any) -> list[str]:
    grid = _get_grid(table_item)
    if not grid:
        return []

    skills: list[str] = []
    seen: set[str] = set()

    header_row_indices = _detect_header_rows(grid)
    header_col_indices = _detect_header_cols(grid, header_row_indices)

    for row_idx, row in enumerate(grid):
        if row_idx in header_row_indices:
            continue
        for col_idx, cell_text in enumerate(row):
            if col_idx in header_col_indices:
                continue
            extracted = _parse_cell(cell_text)
            for skill in extracted:
                key = skill.lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    skills.append(skill)

    return skills


_CATEGORY_PREFIX_RE = re.compile(
    r"^(?:Advanced|Intermediate|Basic|Beginner|Expert|Proficient|"
    r"Familiar|Languages?|Frameworks?|Libraries|Tools?|Databases?|"
    r"Cloud|Platforms?|Technologies|Frontend|Backend|Others?)[:\s]+",
    re.IGNORECASE,
)

def extract_skills_from_table_text(raw_text: str) -> list[str]:
    if not raw_text:
        return []

    skills: list[str] = []
    seen: set[str] = set()

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    for line in lines:
        clean_line = _CATEGORY_PREFIX_RE.sub("", line).strip()
        if not clean_line:
            continue
        parts = re.split(r"[,|/]|\t+|\s{2,}|\u2022|\u25b8|\u25ba", clean_line)
        for part in parts:
            part = re.sub(r"\s*\([^)]+\)\s*$", "", part)
            part = part.strip().strip("•-–—*|/")
            if not part or len(part) > 60:
                continue
            if _is_noise(part):
                continue
            if _CATEGORY_PREFIX_RE.match(part + ":"):
                continue
            key = part.lower()
            if key not in seen:
                seen.add(key)
                skills.append(part)

    return skills


def _get_grid(table_item: Any) -> list[list[str]]:
    try:
        if hasattr(table_item, "data") and hasattr(table_item.data, "grid"):
            raw_grid = table_item.data.grid
            result: list[list[str]] = []
            for row in raw_grid:
                row_texts: list[str] = []
                for cell in row:
                    if hasattr(cell, "text"):
                        row_texts.append(str(cell.text).strip())
                    elif hasattr(cell, "body"):
                        row_texts.append(str(cell.body).strip())
                    else:
                        row_texts.append(str(cell).strip())
                result.append(row_texts)
            return result
    except Exception:
        pass

    try:
        if hasattr(table_item, "export_to_dataframe"):
            df = table_item.export_to_dataframe()
            return [
                [str(v) if v is not None else "" for v in row]
                for row in df.values.tolist()
            ]
    except Exception:
        pass

    return []


def _detect_header_rows(grid: list[list[str]]) -> set[int]:
    header_indices: set[int] = set()
    if not grid:
        return header_indices

    first_row = grid[0]
    if not first_row:
        return header_indices

    non_empty = [c for c in first_row if c.strip()]
    if not non_empty:
        return header_indices

    matching = sum(
        1 for c in non_empty
        if c.lower().strip() in _HEADER_SKIP
    )
    if matching >= len(non_empty) * 0.5:
        header_indices.add(0)

    return header_indices


def _detect_header_cols(
    grid: list[list[str]], header_row_indices: set[int]
) -> set[int]:
    header_col_indices: set[int] = set()
    if not grid:
        return header_col_indices

    data_rows = [r for i, r in enumerate(grid) if i not in header_row_indices]
    if not data_rows:
        return header_col_indices

    num_cols = max(len(r) for r in data_rows) if data_rows else 0
    for col_idx in range(num_cols):
        col_values = [
            r[col_idx] for r in data_rows
            if col_idx < len(r) and r[col_idx].strip()
        ]
        if not col_values:
            continue

        rating_count = sum(1 for v in col_values if _RATING_RE.match(v.strip()))
        header_word_count = sum(
            1 for v in col_values
            if v.lower().strip() in _HEADER_SKIP
        )

        is_pure_rating = rating_count >= len(col_values) * 0.7
        is_pure_header_words = header_word_count >= len(col_values) * 0.7
        is_single_word_col = all(len(v.split()) <= 2 for v in col_values)

        if is_pure_rating:
            header_col_indices.add(col_idx)
        elif is_pure_header_words and is_single_word_col:
            header_col_indices.add(col_idx)

    return header_col_indices


def _parse_cell(cell_text: str) -> list[str]:
    cell_text = cell_text.strip()
    if not cell_text or _is_noise(cell_text):
        return []

    if _RATING_RE.match(cell_text):
        return []

    lower = cell_text.lower()
    if lower in _HEADER_SKIP:
        return []

    if len(cell_text) > 100:
        return []

    if "," in cell_text:
        parts = [p.strip() for p in cell_text.split(",")]
        results: list[str] = []
        for p in parts:
            p = p.strip().strip("•-–—*")
            if p and not _is_noise(p) and not _RATING_RE.match(p) and p.lower() not in _HEADER_SKIP:
                if len(p) <= 60:
                    results.append(p)
        return results

    if "\n" in cell_text:
        parts = [p.strip() for p in cell_text.split("\n")]
        results = []
        for p in parts:
            p = p.strip().strip("•-–—*")
            if p and not _is_noise(p) and not _RATING_RE.match(p) and p.lower() not in _HEADER_SKIP:
                if len(p) <= 60:
                    results.append(p)
        return results

    cleaned = cell_text.strip("•-–—*|/").strip()
    if cleaned and len(cleaned) <= 60:
        return [cleaned]

    return []


def _is_noise(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) <= 1:
        return True
    if _NOISE_RE.match(text):
        return True
    if _STAR_RE.match(stripped):
        return True
    if _RATING_RE.match(stripped):
        return True
    return False
