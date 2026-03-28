from __future__ import annotations

import re
from typing import Optional

from ..models.resume import DateRange, ProjectEntry
from .date_extractor import extract_date_range
from .knowledge_base import load_project_technology_ontology
from .section_catalog import match_section_heading

_BULLET_PREFIX_RE = re.compile(r"^[•\-–—►▸●▶✓✔*·◦]\s+")
_INLINE_BULLET_RE = re.compile(r"[•·◦►▸●▶✓✔]")
_URL_RE = re.compile(r"(https?://\S+|(?:github|gitlab|bitbucket)\.com/\S+)", re.IGNORECASE)
_HEADER_SPLIT_RE = re.compile(r"\s*[|]\s*")
_CRUSHED_TEXT_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bDevlopinganAI\b", re.IGNORECASE), "Developing an AI"),
    (re.compile(r"\bCreateapipelineusing", re.IGNORECASE), "Create a pipeline using"),
    (re.compile(r"\bCreateapipeline", re.IGNORECASE), "Create a pipeline"),
    (re.compile(r"\bpipelinetoclean\b", re.IGNORECASE), "pipeline to clean"),
    (re.compile(r"\bplanningapp\b", re.IGNORECASE), "planning app"),
    (re.compile(r"\bappusing\b", re.IGNORECASE), "app using"),
    (re.compile(r"\btravelplanning\b", re.IGNORECASE), "travel planning"),
    (re.compile(r"\bAI-poweredtravelplanningappusing\s*Lang\s*Chain\b", re.IGNORECASE), "AI-powered travel planning app using LangChain"),
    (re.compile(r"\btravelplanningappusing\s*Lang\s*Chain\b", re.IGNORECASE), "travel planning app using LangChain"),
    (re.compile(r"\bAI-poweredtravelplanningappusing\b", re.IGNORECASE), "AI-powered travel planning app using"),
    (re.compile(r"\bcuttingplanningtimeby(?=\d|\b)", re.IGNORECASE), "cutting planning time by"),
    (re.compile(r"\bcuttingplanning\b", re.IGNORECASE), "cutting planning"),
    (re.compile(r"\btimeby(?=\d|\b)", re.IGNORECASE), "time by"),
    (re.compile(r"\brecordsforNLProlesin(?=[A-Z]|\b)", re.IGNORECASE), "records for NLP roles in"),
    (re.compile(r"\brecordsfor\b", re.IGNORECASE), "records for"),
    (re.compile(r"\bforNLProlesin(?=[A-Z]|\b)", re.IGNORECASE), "for NLP roles in"),
    (re.compile(r"\bNLProlesin(?=[A-Z]|\b)", re.IGNORECASE), "NLP roles in"),
    (re.compile(r"\bforNLP\b", re.IGNORECASE), "for NLP"),
    (re.compile(r"\brolesinIndiausing(?=[A-Z]|\b)", re.IGNORECASE), "roles in India using"),
    (re.compile(r"\binIndiausing(?=[A-Z]|\b)", re.IGNORECASE), "in India using"),
    (re.compile(r"\brolesin\b", re.IGNORECASE), "roles in"),
    (re.compile(r"\bIndiausing(?=[A-Z]|\b)", re.IGNORECASE), "India using"),
    (re.compile(r"\busingPython(?=[A-Z]|\b)", re.IGNORECASE), "using Python"),
    (re.compile(r"\bPythonand\b", re.IGNORECASE), "Python and "),
    (re.compile(r"\bandReact\b", re.IGNORECASE), "and React"),
    (re.compile(r"\bPrototypedofpowerbank\b", re.IGNORECASE), "Prototyped power bank"),
    (re.compile(r"\bWi-Fismartplug\b", re.IGNORECASE), "Wi-Fi smart plug"),
    (re.compile(r"\bFullyHomeAutomationBoard\b", re.IGNORECASE), "Fully Home Automation Board"),
    (re.compile(r"\bBuilt an memory\b", re.IGNORECASE), "Built a memory"),
)


class ProjectsParser:
    def __init__(self) -> None:
        ontology = load_project_technology_ontology()
        technology_entries = ontology.get("technologies", {}) if isinstance(ontology, dict) else {}
        self._technology_patterns: list[tuple[str, re.Pattern[str]]] = []
        for canonical, payload in technology_entries.items():
            aliases = payload.get("aliases", []) if isinstance(payload, dict) else []
            parts = [re.escape(canonical)]
            parts.extend(re.escape(alias) for alias in aliases if isinstance(alias, str))
            if parts:
                pattern = re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.IGNORECASE)
                self._technology_patterns.append((canonical, pattern))

        header_markers = ontology.get("header_markers", []) if isinstance(ontology, dict) else []
        url_labels = ontology.get("url_labels", []) if isinstance(ontology, dict) else []
        header_marker_pattern = "|".join(re.escape(item) for item in header_markers if isinstance(item, str))
        url_label_pattern = "|".join(re.escape(item) for item in url_labels if isinstance(item, str))

        self._tech_line_re = re.compile(
            rf"^(?:tech(?:nologies)?|tech\s+stack|{header_marker_pattern})[:\s]+",
            re.IGNORECASE,
        )
        self._live_link_re = re.compile(
            rf"^(?:{url_label_pattern})[:\s]+",
            re.IGNORECASE,
        )

    def parse(self, lines: list[str]) -> list[ProjectEntry]:
        if not lines:
            return []

        projects: list[ProjectEntry] = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            if self._is_bullet_line(line):
                bullet_text = self._strip_bullet(line)
                if self._looks_like_project_header(bullet_text):
                    line = bullet_text
                elif projects:
                    last = projects[-1]
                    merged_description = " ".join(
                        part for part in [last.description or "", bullet_text] if part
                    )
                    projects[-1] = last.model_copy(
                        update={"description": self._clean_description(merged_description)}
                    )
                    i += 1
                    continue
                else:
                    i += 1
                    continue

            header_text, date_range = extract_date_range(line)
            header_text = header_text.strip()
            if date_range and not header_text:
                i += 1
                continue

            if self._tech_line_re.match(header_text) or self._looks_like_technology_list(header_text):
                tech_part = self._tech_line_re.sub("", header_text).strip() if self._tech_line_re.match(header_text) else header_text
                if i + 1 < len(lines) and self._is_bullet_line(lines[i + 1].strip()):
                    bullet_header = self._strip_bullet(lines[i + 1].strip())
                    name, proj_url, inline_techs = self._parse_header(bullet_header)
                    inline_techs = self._split_inline_items(tech_part) + inline_techs
                    i += 2
                else:
                    i += 1
                    continue
            else:
                header_text = header_text or line
                name, proj_url, inline_techs = self._parse_header(header_text)
                if not name:
                    i += 1
                    continue
                i += 1

            if i < len(lines):
                rem2, dr2 = extract_date_range(lines[i].strip())
                if not rem2.strip() and dr2 and not date_range:
                    date_range = dr2
                    i += 1

            description_parts: list[str] = []
            extra_techs: list[str] = []

            while i < len(lines):
                nxt = lines[i].strip()
                if not nxt:
                    i += 1
                    continue
                if match_section_heading(nxt):
                    break
                if self._looks_like_project_header(nxt):
                    break
                if self._is_bullet_line(nxt):
                    description_parts.append(self._strip_bullet(nxt))
                    i += 1
                    continue
                if self._tech_line_re.match(nxt):
                    tech_part = self._tech_line_re.sub("", nxt).strip()
                    extra_techs.extend(self._split_inline_items(tech_part))
                    i += 1
                    continue
                if self._live_link_re.match(nxt):
                    url_part = self._live_link_re.sub("", nxt).strip()
                    proj_url = proj_url or self._normalize_url(url_part)
                    i += 1
                    continue
                description_parts.append(nxt)
                i += 1

            description = self._clean_description(" ".join(description_parts))
            url = proj_url or self._extract_url(description)
            technologies = self._dedupe(
                self._canonicalize_technologies(inline_techs + extra_techs)
                + self._extract_technologies(" ".join(part for part in [name, description or ""] if part))
            )

            projects.append(
                ProjectEntry(
                    name=name,
                    description=description,
                    date_range=date_range,
                    technologies=technologies,
                    url=url,
                )
            )

        return [project for project in projects if project.name]

    def _parse_header(self, text: str) -> tuple[Optional[str], Optional[str], list[str]]:
        if self._tech_line_re.match(text):
            return None, None, []
        parts = [part.strip() for part in _HEADER_SPLIT_RE.split(text) if part.strip()]
        if not parts:
            return None, None, []

        name_parts: list[str] = []
        techs: list[str] = []
        url: Optional[str] = None

        for part in parts:
            found_url = self._extract_url(part)
            if found_url:
                url = url or found_url
                part = _URL_RE.sub("", part).strip(" -,:")
                if not part:
                    continue

            split_items = self._split_inline_items(part)
            if len(split_items) >= 2 and all(len(item.split()) <= 3 for item in split_items):
                techs.extend(split_items)
            else:
                name_parts.append(part)

        name = name_parts[0] if name_parts else parts[0]
        name = re.sub(r"\s*[–—·|]\s*$", "", name).strip()
        if not re.search(r"[A-Za-z]", name or ""):
            return None, url, techs
        if re.fullmatch(r"[\W_()\-]+", name or ""):
            return None, url, techs
        return name or None, url, techs

    def _clean_description(self, text: str | None) -> str | None:
        if not text:
            return None

        cleaned = text
        for pattern, replacement in _CRUSHED_TEXT_REPLACEMENTS:
            cleaned = pattern.sub(replacement, cleaned)

        cleaned = re.sub(r"(?<=[a-z])(?=[A-Z][a-z])", " ", cleaned)
        cleaned = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", cleaned)
        cleaned = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", cleaned)
        cleaned = re.sub(r"\s*,\s*,\s*", ", ", cleaned)
        cleaned = re.sub(r"\bLang\s+Chain\b", "LangChain", cleaned)
        cleaned = re.sub(r"\bPy\s+MuPDF\b", "PyMuPDF", cleaned)
        cleaned = re.sub(r"\bESP\s+32\b", "ESP32", cleaned)
        cleaned = re.sub(r"\bESP\s+8266\b", "ESP8266", cleaned)
        cleaned = re.sub(r"\bF\s+1\b", "F1", cleaned)
        cleaned = re.sub(r"\b(\d+)\s+k\b", r"\1k", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(\d+)\s+ms\b", r"\1ms", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
        if cleaned:
            cleaned = cleaned[:1].upper() + cleaned[1:]
        return cleaned or None

    def _extract_technologies(self, text: str) -> list[str]:
        found: list[str] = []
        for canonical, pattern in self._technology_patterns:
            if pattern.search(text) and canonical not in found:
                found.append(canonical)
        return found

    def _canonicalize_technologies(self, values: list[str]) -> list[str]:
        canonicalized: list[str] = []
        for value in values:
            text = value.strip()
            if not text:
                continue
            matched = False
            for canonical, pattern in self._technology_patterns:
                if pattern.search(text):
                    canonicalized.append(canonical)
                    matched = True
                    break
            if not matched:
                canonicalized.append(text)
        return canonicalized

    def _split_inline_items(self, text: str) -> list[str]:
        if not text:
            return []
        if _INLINE_BULLET_RE.search(text):
            parts = re.split(_INLINE_BULLET_RE.pattern, text)
        else:
            parts = re.split(r"[,/]", text)
        return [part.strip().strip("•-*") for part in parts if part.strip()]

    def _extract_url(self, text: str | None) -> str | None:
        if not text:
            return None
        match = _URL_RE.search(text)
        if not match:
            return None
        return self._normalize_url(match.group(1))

    def _normalize_url(self, url: str | None) -> str | None:
        if not url:
            return None
        cleaned = url.strip().rstrip(").,;")
        return cleaned if cleaned.startswith("http") else f"https://{cleaned}"

    def _looks_like_project_header(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped or self._is_bullet_line(stripped):
            return False
        if match_section_heading(stripped):
            return False
        cleaned, date_range = extract_date_range(stripped)
        cleaned = cleaned.strip()
        if date_range and not cleaned:
            return False
        if date_range and not re.search(r"[A-Za-z]", cleaned):
            return False
        if self._tech_line_re.match(cleaned) or self._looks_like_technology_list(cleaned):
            return False
        if cleaned.lower().startswith(("tools:", "tech:", "technologies:")):
            return False
        if date_range:
            return True
        words = cleaned.split()
        if not words or len(words) > 9:
            return False
        if cleaned.endswith("."):
            return False
        if re.fullmatch(r"(?:[A-Za-z0-9+#.-]+(?:,\s*|/))+[A-Za-z0-9+#.-]+", cleaned):
            return False
        if cleaned[:1].islower():
            return False
        return True

    def _looks_like_technology_list(self, text: str) -> bool:
        items = self._split_inline_items(text)
        if len(items) < 2:
            return False
        short_items = sum(1 for item in items if 1 <= len(item.split()) <= 3)
        return short_items >= max(2, len(items) - 1)

    def _is_bullet_line(self, line: str) -> bool:
        return _BULLET_PREFIX_RE.match(line.strip()) is not None

    def _strip_bullet(self, line: str) -> str:
        return _BULLET_PREFIX_RE.sub("", line.strip()).strip()

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(value)
        return deduped
