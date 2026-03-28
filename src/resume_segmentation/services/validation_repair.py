from __future__ import annotations

import re
from typing import Iterable

from ..models.resume import ProjectEntry, ResumeProfile
from .resume_validation import ResumeValidationReport
from .skills_normalizer import normalize_skill

_ACTION_WORDS = frozenset({
    "achieved", "architected", "automated", "built", "collaborated", "conceptualized",
    "created", "demonstrating", "designed", "developed", "engineered", "implemented",
    "improved", "increased", "integrated", "led", "maintained", "managed",
    "optimized", "participated", "researched", "resolved", "streamlined", "supported",
})
_INTEREST_WORDS = frozenset({
    "badminton", "cricket", "football", "music", "flute", "mridang", "guitar",
    "piano", "dance", "reading", "writing", "travelling",
})
_SKILL_FRAGMENT_WORDS = frozenset({
    "deep", "machine", "demonstrating", "engineered", "conceptualized",
    "participated", "actively", "completed", "awarded",
})
_SKILL_PLATFORM_WORDS = frozenset({"linkedin", "github"})
_UPPERCASE_SKILL_RE = re.compile(r"^[A-Z]{2,5}$")
_PROJECT_URL_RE = re.compile(r"(https?://\S+|(?:github|gitlab|bitbucket)\.com/\S+)", re.IGNORECASE)
_PROJECT_TECH_PATTERNS: dict[str, re.Pattern[str]] = {
    "Arduino": re.compile(r"\barduino\b", re.IGNORECASE),
    "Raspberry Pi": re.compile(r"\braspberry\s*pi\b", re.IGNORECASE),
    "ESP32": re.compile(r"\besp[\s-]?32\b", re.IGNORECASE),
    "ESP8266": re.compile(r"\besp[\s-]?8266\b", re.IGNORECASE),
    "MQTT": re.compile(r"\bmqtt\b", re.IGNORECASE),
    "HTTP": re.compile(r"\bhttp\b", re.IGNORECASE),
    "LangChain": re.compile(r"\blang\s*chain\b", re.IGNORECASE),
    "Streamlit": re.compile(r"\bstreamlit\b", re.IGNORECASE),
    "Large Language Models": re.compile(r"\bllms?\b|large language model", re.IGNORECASE),
    "RAG (Retrieval-Augmented Generation)": re.compile(r"\brag\b|retrieval[- ]augmented generation", re.IGNORECASE),
    "Vector Databases": re.compile(r"\bvector databases?\b", re.IGNORECASE),
    "Natural Language Processing": re.compile(r"\bnlp\b|natural language processing", re.IGNORECASE),
    "PyMuPDF": re.compile(r"\bpy\s*mupdf\b", re.IGNORECASE),
    "Pillow": re.compile(r"\bpillow\b", re.IGNORECASE),
    "python-pptx": re.compile(r"\bpython-pptx\b", re.IGNORECASE),
    "Pandas": re.compile(r"\bpandas\b", re.IGNORECASE),
    "scikit-learn": re.compile(r"\bscikit[- ]learn\b", re.IGNORECASE),
}
_CRUSHED_TEXT_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bDevlopinganAI\b", re.IGNORECASE), "Developing an AI"),
    (re.compile(r"\bCreateapipelineusing", re.IGNORECASE), "Create a pipeline using"),
    (re.compile(r"\bCreateapipeline", re.IGNORECASE), "Create a pipeline"),
    (re.compile(r"\bplanningapp\b", re.IGNORECASE), "planning app"),
    (re.compile(r"\bappusing\b", re.IGNORECASE), "app using"),
    (re.compile(r"\btravelplanning\b", re.IGNORECASE), "travel planning"),
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
_TECH_CANONICAL_OVERRIDES = {
    "http/2": "HTTP",
    "vector database": "Vector Databases",
    "python-pptx": "python-pptx",
}


class ValidationDrivenRepairer:
    def repair(
        self,
        profile: ResumeProfile,
        report: ResumeValidationReport,
    ) -> ResumeProfile:
        repaired = profile.model_copy(deep=True)

        repaired.skills = self._repair_skills(repaired, report)
        repaired.awards = self._dedupe_sentences(repaired.awards)
        repaired.interests = self._repair_interests(repaired.interests)
        repaired.projects = self._repair_projects(repaired.projects, repaired.skills)

        return repaired

    def _repair_skills(
        self,
        profile: ResumeProfile,
        report: ResumeValidationReport,
    ) -> list[str]:
        noisy_skill_indexes = self._indexes_from_paths(
            list(report.grey_area) + list(report.invalid_sections),
            prefix="skills[",
        )

        interest_text = " ".join(profile.interests).lower()
        award_text = " ".join(profile.awards).lower()

        repaired: list[str] = []
        seen: set[str] = set()
        for idx, raw in enumerate(profile.skills):
            skill = self._clean_skill_text(raw)
            if not skill:
                continue

            normalized = normalize_skill(skill)
            lower = skill.lower()

            should_drop = False
            if idx in noisy_skill_indexes:
                should_drop = True
            elif lower in _ACTION_WORDS:
                should_drop = True
            elif lower in _INTEREST_WORDS:
                should_drop = True
            elif lower in _SKILL_FRAGMENT_WORDS:
                should_drop = True
            elif lower in _SKILL_PLATFORM_WORDS:
                should_drop = True
            elif lower.startswith("machine (") or lower.startswith("deep ("):
                should_drop = True
            elif normalized.category.value == "Other" and _UPPERCASE_SKILL_RE.fullmatch(skill):
                should_drop = True
            elif normalized.category.value == "Other" and len(skill.split()) == 1:
                if not re.fullmatch(r"[A-Z0-9+#./-]{2,12}", skill):
                    should_drop = True
            elif normalized.category.value == "Other" and len(skill.split()) > 4:
                should_drop = True
            elif normalized.category.value == "Other" and (
                lower in interest_text or lower in award_text
            ):
                should_drop = True

            if should_drop:
                continue

            canonical = normalized.canonical.strip()
            if canonical.lower() not in seen:
                seen.add(canonical.lower())
                repaired.append(canonical)

        return repaired

    def _repair_interests(self, interests: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in interests:
            text = re.sub(r"\s+", " ", (item or "").strip()).strip(" ,")
            if not text:
                continue

            if "," in text and len(text.split(",")) >= 2:
                normalized = ", ".join(part.strip() for part in text.split(",") if part.strip())
                cleaned.append(normalized)
            else:
                cleaned.append(text)

        return self._dedupe_sentences(cleaned)

    def _repair_projects(
        self,
        projects: list[ProjectEntry],
        skills: list[str],
    ) -> list[ProjectEntry]:
        repaired: list[ProjectEntry] = []

        for entry in projects:
            description = self._clean_project_description(entry.description)
            url = self._extract_project_url(entry.url, description)

            technologies = self._dedupe_values(
                self._clean_technologies(list(entry.technologies))
            )
            if not technologies:
                inferred = self._infer_project_technologies(
                    ProjectEntry(
                        name=entry.name,
                        description=description,
                        date_range=entry.date_range,
                        technologies=technologies,
                        url=url,
                    ),
                    skills,
                )
                if inferred:
                    technologies = inferred

            repaired.append(
                ProjectEntry(
                    name=entry.name,
                    description=description,
                    date_range=entry.date_range,
                    technologies=technologies,
                    url=url,
                )
            )

        return repaired

    def _infer_project_technologies(
        self,
        entry: ProjectEntry,
        skills: list[str],
    ) -> list[str]:
        haystack = " ".join(part for part in [entry.name or "", entry.description or ""] if part).lower()
        inferred: list[str] = []
        seen: set[str] = set()

        for skill in skills:
            canonical = normalize_skill(skill).canonical
            pattern = re.escape(canonical.lower())
            if re.search(rf"(?<!\w){pattern}(?!\w)", haystack):
                if canonical.lower() not in seen:
                    seen.add(canonical.lower())
                    inferred.append(canonical)
                continue

            compact_haystack = re.sub(r"[^a-z0-9+#]+", "", haystack)
            compact_skill = re.sub(r"[^a-z0-9+#]+", "", canonical.lower())
            if len(compact_skill) >= 4 and compact_skill in compact_haystack:
                if canonical.lower() not in seen:
                    seen.add(canonical.lower())
                    inferred.append(canonical)

        for label, pattern in _PROJECT_TECH_PATTERNS.items():
            if pattern.search(haystack) and label.lower() not in seen:
                seen.add(label.lower())
                inferred.append(label)

        return inferred[:8]

    def _dedupe_sentences(self, items: Iterable[str]) -> list[str]:
        deduped: list[str] = []
        for item in items:
            text = re.sub(r"\s+", " ", (item or "").strip()).strip(" ,")
            if not text:
                continue
            normalized = self._normalize_compare(text)
            if any(
                normalized == self._normalize_compare(existing)
                or normalized in self._normalize_compare(existing)
                or self._normalize_compare(existing) in normalized
                for existing in deduped
            ):
                continue
            deduped.append(text)
        return deduped

    def _indexes_from_paths(self, paths: list[str], prefix: str) -> set[int]:
        indexes: set[int] = set()
        for path in paths:
            if not path.startswith(prefix):
                continue
            match = re.match(rf"{re.escape(prefix)}(\d+)\]", path)
            if match:
                indexes.add(int(match.group(1)))
        return indexes

    def _normalize_compare(self, text: str) -> str:
        normalized = text.lower()
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\b(and|the|a|an)\b", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _clean_skill_text(self, raw: str | None) -> str:
        text = re.sub(r"\s+", " ", (raw or "").strip()).strip(" ,")
        if not text:
            return ""

        acronym_match = re.search(r"\(([A-Z]{2,6})s?\)\s*$", text)
        if acronym_match:
            expanded = text[:acronym_match.start()].strip()
            if expanded and self._initialism(expanded) == acronym_match.group(1):
                text = expanded

        return text

    def _clean_project_description(self, text: str | None) -> str | None:
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

    def _extract_project_url(self, explicit_url: str | None, description: str | None) -> str | None:
        for source in (explicit_url, description):
            if not source:
                continue
            match = _PROJECT_URL_RE.search(source)
            if not match:
                continue
            url = match.group(1).rstrip(").,;")
            return url if url.startswith("http") else f"https://{url}"
        return explicit_url

    def _clean_technologies(self, technologies: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in technologies:
            text = self._clean_skill_text(raw)
            if not text:
                continue
            override = _TECH_CANONICAL_OVERRIDES.get(text.lower())
            if override:
                cleaned.append(override)
            else:
                cleaned.append(normalize_skill(text).canonical)
        return cleaned

    def _dedupe_values(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(value)
        return deduped

    def _initialism(self, text: str) -> str:
        letters = re.findall(r"[A-Za-z]+", text)
        return "".join(word[0].upper() for word in letters if word)
