from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from ..models.resume import EducationEntry, ExperienceEntry, LinkItem, ProjectEntry

if TYPE_CHECKING:
    from .profile_consensus import StrategyResult


@dataclass
class CandidateNode:
    field_name: str
    key: str
    support: int = 0
    weighted_support: float = 0.0
    strategies: set[str] = field(default_factory=set)
    best_value: Any = None
    best_score: float = -1.0
    first_seen_order: int = 10**9


class FieldCandidateGraph:
    def __init__(self):
        self._nodes: dict[str, dict[str, CandidateNode]] = defaultdict(dict)

    def add_candidate(
        self,
        *,
        field_name: str,
        key: str,
        value: Any,
        strategy_name: str,
        strategy_score: float,
        completeness: float,
        order: int,
    ) -> None:
        if not key:
            return

        bucket = self._nodes[field_name]
        node = bucket.get(key)
        if node is None:
            node = CandidateNode(field_name=field_name, key=key)
            bucket[key] = node

        if strategy_name not in node.strategies:
            node.strategies.add(strategy_name)
            node.support += 1
            node.weighted_support += strategy_score

        node.first_seen_order = min(node.first_seen_order, order)

        value_score = completeness + strategy_score * 0.4
        if value_score > node.best_score:
            node.best_score = value_score
            node.best_value = value

    def select_strings(self, field_name: str, fallback: list[str]) -> list[str]:
        field_nodes = self._nodes.get(field_name, {})
        nodes = list(field_nodes.values())
        ordered: list[str] = []
        seen: set[str] = set()

        for value in fallback:
            key = _normalize_text(value)
            if not key or key in seen:
                continue
            if key in field_nodes:
                value = _clean_text(field_nodes[key].best_value)
            if key and key not in seen:
                seen.add(key)
                ordered.append(value)

        for node in sorted(nodes, key=_rank_key, reverse=True):
            value = _clean_text(node.best_value)
            key = _normalize_text(value)
            if not key or key in seen:
                continue
            if node.support < 1:
                continue
            seen.add(key)
            ordered.append(value)

        return ordered

    def select_links(self, fallback: list[LinkItem]) -> list[LinkItem]:
        field_nodes = self._nodes.get("links", {})
        nodes = list(field_nodes.values())
        ordered: list[LinkItem] = []
        seen: set[str] = set()

        for item in fallback:
            key = _normalize_url(item.url)
            if not key or key in seen:
                continue
            if key in field_nodes:
                item = field_nodes[key].best_value
            if key and key not in seen:
                seen.add(key)
                ordered.append(item)

        for node in sorted(nodes, key=_rank_key, reverse=True):
            item = node.best_value
            key = _normalize_url(item.url)
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(item)

        return ordered

    def select_education(self, fallback: list[EducationEntry]) -> list[EducationEntry]:
        return self._select_structured("education", fallback)

    def select_experience(self, fallback: list[ExperienceEntry]) -> list[ExperienceEntry]:
        return self._select_structured("experience", fallback)

    def select_projects(self, fallback: list[ProjectEntry]) -> list[ProjectEntry]:
        return self._select_structured("projects", fallback)

    def _select_structured(self, field_name: str, fallback: list[Any]) -> list[Any]:
        field_nodes = self._nodes.get(field_name, {})
        nodes = list(field_nodes.values())
        ordered: list[Any] = []
        seen: set[str] = set()

        for item in fallback:
            key = self._structured_key(field_name, item)
            if not key or key in seen:
                continue
            if key in field_nodes:
                item = field_nodes[key].best_value
            if key and key not in seen:
                seen.add(key)
                ordered.append(item)

        for node in sorted(nodes, key=_rank_key, reverse=True):
            item = node.best_value
            key = self._structured_key(field_name, item)
            if not key or key in seen:
                continue
            if node.support < 2 and node.weighted_support < 1.6:
                continue
            seen.add(key)
            ordered.append(item)

        return ordered

    def _structured_key(self, field_name: str, item: Any) -> str:
        if field_name == "education":
            return education_key(item)
        if field_name == "experience":
            return experience_key(item)
        if field_name == "projects":
            return project_key(item)
        return ""


class FieldCandidateGraphBuilder:
    def build(self, strategy_results: list["StrategyResult"]) -> FieldCandidateGraph:
        graph = FieldCandidateGraph()

        for result_index, result in enumerate(strategy_results):
            base_order = result_index * 10_000
            for item_index, item in enumerate(result.profile.links):
                graph.add_candidate(
                    field_name="links",
                    key=_normalize_url(item.url),
                    value=item,
                    strategy_name=result.strategy,
                    strategy_score=result.global_score,
                    completeness=link_completeness(item),
                    order=base_order + item_index,
                )

            for item_index, item in enumerate(result.profile.skills):
                graph.add_candidate(
                    field_name="skills",
                    key=_normalize_text(item),
                    value=_clean_text(item),
                    strategy_name=result.strategy,
                    strategy_score=result.global_score,
                    completeness=string_completeness(item),
                    order=base_order + 100 + item_index,
                )

            for item_index, item in enumerate(result.profile.awards):
                graph.add_candidate(
                    field_name="awards",
                    key=_normalize_text(item),
                    value=_clean_text(item),
                    strategy_name=result.strategy,
                    strategy_score=result.global_score,
                    completeness=string_completeness(item),
                    order=base_order + 200 + item_index,
                )

            for item_index, item in enumerate(result.profile.interests):
                graph.add_candidate(
                    field_name="interests",
                    key=_normalize_text(item),
                    value=_clean_text(item),
                    strategy_name=result.strategy,
                    strategy_score=result.global_score,
                    completeness=string_completeness(item),
                    order=base_order + 300 + item_index,
                )

            for item_index, item in enumerate(result.profile.education):
                graph.add_candidate(
                    field_name="education",
                    key=education_key(item),
                    value=item,
                    strategy_name=result.strategy,
                    strategy_score=result.global_score,
                    completeness=education_completeness(item),
                    order=base_order + 400 + item_index,
                )

            for item_index, item in enumerate(result.profile.experience):
                graph.add_candidate(
                    field_name="experience",
                    key=experience_key(item),
                    value=item,
                    strategy_name=result.strategy,
                    strategy_score=result.global_score,
                    completeness=experience_completeness(item),
                    order=base_order + 500 + item_index,
                )

            for item_index, item in enumerate(result.profile.projects):
                graph.add_candidate(
                    field_name="projects",
                    key=project_key(item),
                    value=item,
                    strategy_name=result.strategy,
                    strategy_score=result.global_score,
                    completeness=project_completeness(item),
                    order=base_order + 600 + item_index,
                )

        return graph


def education_key(item: EducationEntry) -> str:
    institution = _normalize_text(item.institution)
    degree = _normalize_text(item.degree)
    return institution or degree


def experience_key(item: ExperienceEntry) -> str:
    company = _normalize_text(item.company)
    title = _normalize_text(item.title)
    return company or title


def project_key(item: ProjectEntry) -> str:
    name = _normalize_text(item.name)
    return name or _normalize_text(item.description)


def string_completeness(value: str | None) -> float:
    cleaned = _clean_text(value)
    if not cleaned:
        return 0.0
    return min(len(cleaned.split()) / 8, 1.0)


def link_completeness(item: LinkItem) -> float:
    parsed = urlparse(item.url)
    return 1.0 if parsed.scheme in {"http", "https"} and parsed.netloc else 0.3


def education_completeness(item: EducationEntry) -> float:
    score = 0.0
    if item.institution:
        score += 0.35
    if item.degree:
        score += 0.25
    if item.date_range and item.date_range.start:
        score += 0.2
    if item.gpa:
        score += 0.2
    return min(score, 1.0)


def experience_completeness(item: ExperienceEntry) -> float:
    score = 0.0
    if item.company:
        score += 0.3
    if item.title:
        score += 0.25
    if item.date_range and item.date_range.start:
        score += 0.2
    if item.bullets:
        score += 0.25
    return min(score, 1.0)


def project_completeness(item: ProjectEntry) -> float:
    score = 0.0
    if item.name:
        score += 0.45
    if item.description:
        score += 0.4
    if item.date_range and item.date_range.start:
        score += 0.1
    if item.technologies or item.url:
        score += 0.05
    return min(score, 1.0)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned


def _normalize_text(value: str | None) -> str:
    cleaned = _clean_text(value).lower()
    cleaned = re.sub(r"[^a-z0-9+.#/ ]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _normalize_url(value: str | None) -> str:
    cleaned = _clean_text(value).rstrip("/")
    return cleaned.lower()


def _rank_key(node: CandidateNode) -> tuple[float, int, float]:
    return (node.support + node.weighted_support, -node.first_seen_order, node.best_score)
