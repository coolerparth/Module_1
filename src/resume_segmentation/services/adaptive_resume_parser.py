from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..models.resume import (
    DateRange,
    EducationEntry,
    ExperienceEntry,
    LinkItem,
    PersonalInfo,
    ProjectEntry,
    ResumeProfile,
)
from .date_extractor import extract_date_range, has_date
from .document_geometry import DocumentGeometry, LineNode
from .entry_signatures import best_section, score_section_signatures
from .personal_info_extractor import extract_personal_info
from .section_catalog import match_section_heading

_BULLET_RE = re.compile(r"^[•\-–—►▸●▶✓✔*]\s+")
_GPA_RE = re.compile(
    r"(?:CGPA|GPA|Percentage|Score|Marks)[:\s]*([0-9.]+(?:\s*/\s*[0-9.]+)?%?)",
    re.IGNORECASE,
)
_DEGREE_RE = re.compile(
    r"\b(?:B\.?(?:Sc|Tech|E|S|A|Com|Ed|Arch)|M\.?(?:Sc|Tech|E|S|A|Com|Ed|B|Phil|Arch)|"
    r"Ph\.?D|B\.?B\.?A|M\.?B\.?A|B\.?C\.?A|M\.?C\.?A|"
    r"Bachelor|Master|Doctor|Doctorate|Associate|Diploma|"
    r"BTech|MTech|BCA|MCA|BSc|MSc|BBA|MBA|BE|ME|"
    r"B\.Eng|M\.Eng|10th|12th|SSC|HSC|CBSE|ICSE)\b",
    re.IGNORECASE,
)
_JOB_TITLE_WORDS = frozenset({
    "intern", "engineer", "developer", "analyst", "manager", "designer",
    "scientist", "researcher", "professor", "assistant", "associate",
    "lead", "senior", "junior", "director", "officer", "specialist",
    "consultant", "architect", "trainer", "coordinator", "head",
    "fellow", "staff", "trainee", "apprentice",
})
_EDU_INSTITUTION_WORDS = frozenset({
    "university", "college", "institute", "school", "iit", "nit",
    "academy", "polytechnic", "campus", "faculty",
})


@dataclass
class SectionBlock:
    name: str
    lines: list[str] = field(default_factory=list)
    raw_lines: list[LineNode] = field(default_factory=list)


class AdaptiveHeadingDetector:

    def __init__(self, font_scale: float = 1.05):
        self.font_scale = font_scale

    def is_heading(self, line: LineNode, page_median_font: float) -> Optional[str]:
        text = line.text.strip()
        if not text or len(text.split()) > 7:
            return None

        section = match_section_heading(text)
        if section:
            return section

        font_boosted = (
            line.font_size is not None
            and line.font_size >= page_median_font * self.font_scale
        )
        if (font_boosted or line.is_bold) and len(text.split()) <= 5:
            s2 = match_section_heading(text)
            if s2:
                return s2

        return None


class EntryBoundaryDetector:

    def is_entry_start(self, line: str, section: str) -> bool:
        stripped = line.strip()
        if _BULLET_RE.match(stripped):
            return False
        if has_date(stripped):
            return True
        if section == "experience":
            words = stripped.split()
            if len(words) <= 6 and stripped[0:1].isupper():
                if any(w in stripped.lower() for w in _JOB_TITLE_WORDS):
                    return True
        if section == "education":
            if _DEGREE_RE.search(stripped):
                return True
            words = stripped.split()
            if len(words) <= 6 and stripped[0:1].isupper():
                if any(w in stripped.lower() for w in _EDU_INSTITUTION_WORDS):
                    return True
        if section == "projects":
            words = stripped.split()
            if 1 <= len(words) <= 8 and stripped[0:1].isupper() and not stripped.endswith("."):
                return True
        return False


def parse_skills_adaptive(lines: list[str]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()

    def _add(skill: str) -> None:
        cleaned = re.sub(r"\s+", " ", skill.strip()).strip("•-–—*")
        if cleaned and 1 <= len(cleaned) <= 50:
            key = cleaned.lower()
            if key not in seen:
                seen.add(key)
                skills.append(cleaned)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _BULLET_RE.match(stripped):
            stripped = _BULLET_RE.sub("", stripped).strip()
        if ":" in stripped:
            _, _, items = stripped.partition(":")
            if "," in items or items.strip():
                for item in re.split(r"[,|]", items):
                    _add(item.strip())
                continue
        if "," in stripped:
            for item in re.split(r"[,|]", stripped):
                _add(item.strip())
            continue
        _add(stripped)

    return skills


def _parse_experience_group(lines: list[str]) -> Optional[ExperienceEntry]:
    if not lines:
        return None

    header_lines: list[str] = []
    bullets: list[str] = []

    for line in lines:
        stripped = line.strip()
        if _BULLET_RE.match(stripped):
            bullets.append(_BULLET_RE.sub("", stripped).strip())
        else:
            header_lines.append(stripped)

    date_range: Optional[DateRange] = None
    cleaned_headers: list[str] = []

    for line in header_lines:
        remaining, dr = extract_date_range(line)
        if dr and not date_range:
            date_range = dr
        if remaining.strip():
            cleaned_headers.append(remaining.strip())

    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None

    if len(cleaned_headers) >= 2:
        l0, l1 = cleaned_headers[0], cleaned_headers[1]
        t0 = any(w in l0.lower() for w in _JOB_TITLE_WORDS)
        t1 = any(w in l1.lower() for w in _JOB_TITLE_WORDS)
        if t0 and not t1:
            title, company = l0, l1
        elif t1 and not t0:
            company, title = l0, l1
        else:
            company, title = l0, l1
    elif cleaned_headers:
        only = cleaned_headers[0]
        if any(w in only.lower() for w in _JOB_TITLE_WORDS):
            title = only
        else:
            company = only

    if company and "," in company:
        parts = [p.strip() for p in company.split(",", 1)]
        if len(parts) == 2 and len(parts[1]) <= 30:
            company, location = parts[0], parts[1]

    return ExperienceEntry(
        company=company or None,
        title=title or None,
        date_range=date_range,
        location=location,
        bullets=bullets,
    )


def parse_experience_adaptive(lines: list[str]) -> list[ExperienceEntry]:
    if not lines:
        return []
    bd = EntryBoundaryDetector()
    groups: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if cur and bd.is_entry_start(line, "experience"):
            groups.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        groups.append(cur)
    entries = []
    for g in groups:
        e = _parse_experience_group(g)
        if e and (e.company or e.title or e.bullets):
            entries.append(e)
    return entries


def _parse_education_group(lines: list[str]) -> Optional[EducationEntry]:
    if not lines:
        return None
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    date_range: Optional[DateRange] = None
    gpa: Optional[str] = None
    remaining_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        remaining, dr = extract_date_range(stripped)
        if dr and not date_range:
            date_range = dr
        gpa_m = _GPA_RE.search(remaining)
        if gpa_m:
            gpa = gpa_m.group(1).strip()
            remaining = _GPA_RE.sub("", remaining).strip(" ,-")
        if remaining.strip():
            remaining_lines.append(remaining.strip())

    for line in remaining_lines:
        lower = line.lower()
        is_inst = any(w in lower for w in _EDU_INSTITUTION_WORDS)
        has_deg = bool(_DEGREE_RE.search(line))
        if has_deg and not degree:
            m_in = re.search(r"\bin\s+(.+)$", line, re.IGNORECASE)
            if m_in:
                degree = line[:m_in.start()].strip() or None
                field_of_study = m_in.group(1).strip()
            else:
                degree = line
        elif is_inst and not institution:
            institution = line
        elif not institution and not degree:
            institution = line

    return EducationEntry(
        institution=institution,
        degree=degree,
        field_of_study=field_of_study,
        date_range=date_range,
        gpa=gpa,
    )


def parse_education_adaptive(lines: list[str]) -> list[EducationEntry]:
    if not lines:
        return []
    bd = EntryBoundaryDetector()
    groups: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if cur and bd.is_entry_start(line, "education"):
            groups.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        groups.append(cur)
    entries = []
    for g in groups:
        e = _parse_education_group(g)
        if e and (e.institution or e.degree):
            entries.append(e)
    return entries


def _parse_project_group(lines: list[str]) -> Optional[ProjectEntry]:
    if not lines:
        return None
    name: Optional[str] = None
    bullets: list[str] = []
    date_range: Optional[DateRange] = None
    for line in lines:
        stripped = line.strip()
        if _BULLET_RE.match(stripped):
            bullets.append(_BULLET_RE.sub("", stripped).strip())
        else:
            remaining, dr = extract_date_range(stripped)
            if dr and not date_range:
                date_range = dr
            if remaining.strip() and not name:
                name = remaining.strip()
    return ProjectEntry(
        name=name,
        description=" ".join(bullets) if bullets else None,
        date_range=date_range,
        technologies=[],
        url=None,
    )


def parse_projects_adaptive(lines: list[str]) -> list[ProjectEntry]:
    if not lines:
        return []
    bd = EntryBoundaryDetector()
    groups: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if cur and bd.is_entry_start(stripped, "projects"):
            groups.append(cur)
            cur = [stripped]
        else:
            cur.append(stripped)
    if cur:
        groups.append(cur)
    entries = []
    for g in groups:
        e = _parse_project_group(g)
        if e and e.name:
            entries.append(e)
    return entries


def parse_list_section(lines: list[str]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        item = _BULLET_RE.sub("", stripped).strip() if _BULLET_RE.match(stripped) else stripped
        if "," in item and len(item) < 100:
            for part in item.split(","):
                part = part.strip()
                if part and part.lower() not in seen:
                    seen.add(part.lower())
                    items.append(part)
        elif item and item.lower() not in seen:
            seen.add(item.lower())
            items.append(item)
    return items


class AdaptiveResumeParser:

    def __init__(self):
        self.heading_detector = AdaptiveHeadingDetector()

    def parse(self, pdf_path: str) -> ResumeProfile:
        from .document_geometry import GeometryExtractor
        geometry = GeometryExtractor().extract(pdf_path)
        return self.parse_geometry(geometry)

    def parse_geometry(self, geometry: DocumentGeometry) -> ResumeProfile:
        sections = self._segment_into_sections(geometry)
        return self._build_profile(sections, geometry.urls)

    def score(self, profile: ResumeProfile) -> int:
        s = 0
        if profile.personal_info.name: s += 2
        if profile.personal_info.email: s += 2
        if profile.personal_info.phone: s += 2
        if profile.links: s += 2
        if profile.education: s += 2
        if profile.experience: s += 2
        if profile.projects: s += 2
        if len(profile.skills) >= 5: s += 2
        if profile.awards: s += 1
        if profile.interests: s += 1
        return s

    def _compute_page_medians(self, geometry: DocumentGeometry) -> dict[int, float]:
        medians: dict[int, float] = {}
        for page in geometry.pages:
            sizes = [l.font_size for l in page.lines if l.font_size]
            if sizes:
                ordered = sorted(sizes)
                mid = len(ordered) // 2
                medians[page.page] = (
                    ordered[mid] if len(ordered) % 2
                    else (ordered[mid - 1] + ordered[mid]) / 2
                )
            else:
                medians[page.page] = 10.0
        return medians

    def _segment_into_sections(self, geometry: DocumentGeometry) -> dict[str, list[str]]:
        page_medians = self._compute_page_medians(geometry)
        sections: dict[str, list[str]] = {"header": []}
        current_section = "header"
        first_heading_seen = False
        pending_lines: list[str] = []

        for page in geometry.pages:
            median = page_medians.get(page.page, 10.0)
            for line_node in page.lines:
                text = line_node.text.strip()
                if not text:
                    continue
                detected = self.heading_detector.is_heading(line_node, median)
                if detected:
                    if pending_lines:
                        sections.setdefault(current_section, []).extend(pending_lines)
                        pending_lines = []
                    first_heading_seen = True
                    current_section = detected
                    sections.setdefault(current_section, [])
                else:
                    if not first_heading_seen:
                        sections["header"].append(text)
                    else:
                        pending_lines.append(text)
                        if len(pending_lines) >= 5:
                            sections.setdefault(current_section, []).extend(pending_lines)
                            pending_lines = []

        if pending_lines:
            sections.setdefault(current_section, []).extend(pending_lines)

        if len(sections.get("header", [])) > 10:
            sections = self._refine_oversized_header(sections)

        return sections

    def _refine_oversized_header(
        self, sections: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        header = sections.get("header", [])
        if len(header) <= 10:
            return sections
        new_sections: dict[str, list[str]] = {"header": []}
        current = "header"
        header_line_limit = 6
        for i, line in enumerate(header):
            if i < header_line_limit:
                new_sections["header"].append(line)
                continue
            detected = match_section_heading(line)
            if detected:
                current = detected
                new_sections.setdefault(current, [])
            else:
                new_sections.setdefault(current, []).append(line)
        for key, lines in sections.items():
            if key == "header":
                continue
            existing = new_sections.get(key, [])
            new_sections[key] = existing + lines
        return new_sections

    def _build_profile(
        self, sections: dict[str, list[str]], pdf_urls: list[str]
    ) -> ResumeProfile:
        header_lines = sections.get("header", [])
        info = extract_personal_info(header_lines, pdf_urls)
        links = [LinkItem(label=l["label"], url=l["url"]) for l in info.get("links", [])]
        return ResumeProfile(
            personal_info=PersonalInfo(
                name=info.get("name"),
                email=info.get("email"),
                phone=info.get("phone"),
                location=info.get("location"),
                headline=info.get("headline"),
            ),
            links=links,
            summary=(" ".join(l.strip() for l in sections.get("summary", []) if l.strip()) or None),
            skills=parse_skills_adaptive(sections.get("skills", [])),
            experience=parse_experience_adaptive(sections.get("experience", [])),
            education=parse_education_adaptive(sections.get("education", [])),
            projects=parse_projects_adaptive(sections.get("projects", [])),
            certifications=[],
            languages=parse_list_section(sections.get("languages", [])),
            awards=parse_list_section(sections.get("awards", [])),
            interests=parse_list_section(sections.get("interests", [])),
        )
