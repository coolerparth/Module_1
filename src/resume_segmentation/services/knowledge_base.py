from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"


def _load_yaml_like_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        return json.loads(text)


@lru_cache(maxsize=16)
def load_knowledge(name: str) -> Any:
    path = _KNOWLEDGE_DIR / f"{name}.yml"
    if not path.exists():
        return {}
    return _load_yaml_like_file(path)


def load_section_heading_ontology() -> dict[str, list[str]]:
    data = load_knowledge("section_headings")
    return data if isinstance(data, dict) else {}


def load_skill_alias_ontology() -> dict[str, dict[str, Any]]:
    data = load_knowledge("skill_aliases")
    return data if isinstance(data, dict) else {}


def load_project_technology_ontology() -> dict[str, dict[str, Any]]:
    data = load_knowledge("project_technologies")
    return data if isinstance(data, dict) else {}


def load_degree_alias_ontology() -> dict[str, list[str]]:
    data = load_knowledge("degree_aliases")
    return data if isinstance(data, dict) else {}
