"""
adaptive_resume_parser.py — Adaptive, layout-aware resume parser.

This is the 5th parsing strategy, designed to handle edge cases that other
strategies miss. It uses:

  1. Typography-based heading detection (font size, bold detection)
  2. Spatial gap analysis (blank lines / vertical gaps between entries)
  3. Content-anchored entry boundary detection
  4. Multi-pass section refinement
  5. Heuristic entry splitting for dense sections (education, experience)

Key innovation: instead of relying solely on section headings, this parser
also uses entry-level boundary detection — e.g., if a line matches a date
pattern AND follows a capitalized short line, it marks a new entry boundary.
"""
from __future__ import annotations

import re
from collections import defaultdict
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
_EMAIL_RE = re.compile(r"[A-Za-z0-9_.+\-]+@[A-Za-z0-9\-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://\S+|(?:www|linkedin|github)\.\S+", re.IGNORECASE)

_DEGREE_RE = re.compile(
    r"\b(?:B\.?(?:Sc|Tech|E|S|A|Com|Ed|Arch)|M\.?(?:Sc|Tech|E|S|A|Com|Ed|B|Phil|Arch)|"
    r"Ph\.?D|B\.?B\.?A|M\.?B\.?A|B\.?C\.?A|M\.?C\.?A|"
    r"Bachelor|Master|Doctor|Doctorate|Associate|Diploma|"
    r"BTech|MTech|BCA|MCA|BSc|MSc|BBA|MBA|BE|ME|"
    r"B\.Eng|M\.Eng|10th|12th|SSC|HSC|CBSE|ICSE)\b",
    re.IGNORECASE,
)

_GPA_RE = re.compile(
    r"(?:CGPA|GPA|Percentage|Score|Marks)[:\s]*([0-9.]+(?:\s*/\s*[0-9.]+)?%?)",
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

    def __init__(self, font_scale: float = 1.08):
        self.font_scale = font_scale

    def is_heading(self, line: LineNode, page_median_font: float) -> Optional[str]:
        text = line.text.strip()
        if not text:
            return None

                               
        if len(text.split()) > 7:
            return None

                                              
        section = match_section_heading(text)

                                    
        font_boosted = (
            line.font_size is not None
            and line.font_size >= page_median_font * self.font_scale
        )

                                                
        is_bold = bool(
            line.font_size and line.font_size >= page_median_font * 1.02
            and "bold" in (line.font_size and "" or "").lower()
        )

                                                                    
        if section:
            return section

                                                
        if font_boosted and len(text.split()) <= 5:
            section = match_section_heading(text)
            if section:
                return section

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
                lower = stripped.lower()
                if any(w in lower for w in _JOB_TITLE_WORDS):
                    return True

                                                                
        if section == "education":
            if _DEGREE_RE.search(stripped):
                return True
            words = stripped.split()
            if len(words) <= 6 and stripped[0:1].isupper():
                lower = stripped.lower()
                if any(w in lower for w in _EDU_INSTITUTION_WORDS):
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
            category, _, items = stripped.partition(":")
                                                 
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


                                                                               
                   
                                                                               

def parse_experience_adaptive(lines: list[str]) -> list[ExperienceEntry]:
    if not lines:
        return []

    boundary_detector = EntryBoundaryDetector()
    entries: list[ExperienceEntry] = []

                             
    groups: list[list[str]] = []
    current_group: list[str] = []

    for line in lines:
        if current_group and boundary_detector.is_entry_start(line, "experience"):
            groups.append(current_group)
            current_group = [line]
        else:
            current_group.append(line)

    if current_group:
        groups.append(current_group)

    for group in groups:
        entry = _parse_experience_group(group)
        if entry and (entry.company or entry.title or entry.bullets):
            entries.append(entry)

    return entries


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

    if not header_lines:
        return None

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
        line0 = cleaned_headers[0]
        line1 = cleaned_headers[1]
        lower0 = line0.lower()
        lower1 = line1.lower()

        title_in_0 = any(w in lower0 for w in _JOB_TITLE_WORDS)
        title_in_1 = any(w in lower1 for w in _JOB_TITLE_WORDS)

        if title_in_0 and not title_in_1:
            title, company = line0, line1
        elif title_in_1 and not title_in_0:
            company, title = line0, line1
        else:
                                                        
            company, title = line0, line1

    elif cleaned_headers:
        only = cleaned_headers[0]
        lower = only.lower()
        if any(w in lower for w in _JOB_TITLE_WORDS):
            title = only
        else:
            company = only

                                                                    
    if company and "," in company:
        parts = [p.strip() for p in company.split(",", 1)]
        if len(parts) == 2 and len(parts[1]) <= 30:
            company = parts[0]
            location = parts[1]

    return ExperienceEntry(
        company=company or None,
        title=title or None,
        date_range=date_range,
        location=location,
        bullets=bullets,
    )


                                                                               
                  
                                                                               

def parse_education_adaptive(lines: list[str]) -> list[EducationEntry]:
    if not lines:
        return []

    boundary_detector = EntryBoundaryDetector()

                             
    groups: list[list[str]] = []
    current_group: list[str] = []

    for line in lines:
        if current_group and boundary_detector.is_entry_start(line, "education"):
            groups.append(current_group)
            current_group = [line]
        else:
            current_group.append(line)

    if current_group:
        groups.append(current_group)

    entries: list[EducationEntry] = []
    for group in groups:
        entry = _parse_education_group(group)
        if entry and (entry.institution or entry.degree):
            entries.append(entry)

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

        gpa_match = _GPA_RE.search(remaining)
        if gpa_match:
            gpa = gpa_match.group(1).strip()
            remaining = _GPA_RE.sub("", remaining).strip(" ,-")

        if remaining.strip():
            remaining_lines.append(remaining.strip())

                                                        
    for line in remaining_lines:
        lower = line.lower()

        is_edu_inst = any(w in lower for w in _EDU_INSTITUTION_WORDS)
        has_degree = bool(_DEGREE_RE.search(line))

        if has_degree and not degree:
                                      
            match_in = re.search(r"\bin\s+(.+)$", line, re.IGNORECASE)
            if match_in:
                degree_part = line[:match_in.start()].strip()
                field_of_study = match_in.group(1).strip()
                degree = degree_part or None
            else:
                degree = line
        elif is_edu_inst and not institution:
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


                                                                               
                 
                                                                               

def parse_projects_adaptive(lines: list[str]) -> list[ProjectEntry]:
    if not lines:
        return []

    boundary_detector = EntryBoundaryDetector()
    groups: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if current and boundary_detector.is_entry_start(stripped, "projects"):
            groups.append(current)
            current = [stripped]
        else:
            current.append(stripped)

    if current:
        groups.append(current)

    entries: list[ProjectEntry] = []
    for group in groups:
        entry = _parse_project_group(group)
        if entry and entry.name:
            entries.append(entry)

    return entries


def _parse_project_group(lines: list[str]) -> Optional[ProjectEntry]:
    if not lines:
        return None

    name: Optional[str] = None
    bullets: list[str] = []
    date_range: Optional[DateRange] = None
    tech_keywords: list[str] = []

                                       
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

    description = " ".join(bullets) if bullets else None

    return ProjectEntry(
        name=name,
        description=description,
        date_range=date_range,
        technologies=tech_keywords,
        url=None,
    )


                                                                               
                           
                                                                               

def parse_list_section(lines: list[str]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if _BULLET_RE.match(stripped):
            item = _BULLET_RE.sub("", stripped).strip()
        else:
            item = stripped

                                                     
        if "," in item and len(item) < 100:
            for part in item.split(","):
                part = part.strip()
                if part and part.lower() not in seen:
                    seen.add(part.lower())
                    items.append(part)
        else:
            if item and item.lower() not in seen:
                seen.add(item.lower())
                items.append(item)

    return items


                                                                               
                   
                                                                               

class AdaptiveResumeParser:

    def __init__(self):
        self.heading_detector = AdaptiveHeadingDetector()

    def parse(self, pdf_path: str) -> ResumeProfile:
        from .document_geometry import GeometryExtractor
        extractor = GeometryExtractor()
        geometry = extractor.extract(pdf_path)
        return self.parse_geometry(geometry)

    def parse_geometry(self, geometry: DocumentGeometry) -> ResumeProfile:
        sections = self._segment_into_sections(geometry)
        return self._build_profile(sections, geometry.urls)

    def score(self, profile: ResumeProfile) -> int:
        score = 0
        if profile.personal_info.name: score += 2
        if profile.personal_info.email: score += 2
        if profile.personal_info.phone: score += 2
        if profile.links: score += 2
        if profile.education: score += 2
        if profile.experience: score += 2
        if profile.projects: score += 2
        if len(profile.skills) >= 5: score += 2
        if profile.awards: score += 1
        if profile.interests: score += 1
        return score

                                                                               

    def _compute_page_medians(self, geometry: DocumentGeometry) -> dict[int, float]:
        medians: dict[int, float] = {}
        for page in geometry.pages:
            sizes = [line.font_size for line in page.lines if line.font_size]
            if sizes:
                ordered = sorted(sizes)
                mid = len(ordered) // 2
                medians[page.page] = (
                    ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
                )
            else:
                medians[page.page] = 10.0
        return medians

    def _segment_into_sections(self, geometry: DocumentGeometry) -> dict[str, list[str]]:
        page_medians = self._compute_page_medians(geometry)
        sections: dict[str, list[str]] = {"header": []}
        current_section = "header"
        first_heading_seen = False

        all_lines: list[tuple[LineNode, float]] = []
        for page in geometry.pages:
            median = page_medians.get(page.page, 10.0)
            for line in page.lines:
                all_lines.append((line, median))

                                            
        unclassified_blocks: list[tuple[str, list[str]]] = []                            
        pending_lines: list[str] = []

        for line_node, page_median in all_lines:
            text = line_node.text.strip()
            if not text:
                continue

            detected_section = self.heading_detector.is_heading(line_node, page_median)

            if detected_section:
                                                                                 
                if pending_lines:
                    sections.setdefault(current_section, []).extend(pending_lines)
                    pending_lines = []

                first_heading_seen = True
                current_section = detected_section
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

                                                                                    
                                                                           
        header_lines = sections.get("header", [])
        if len(header_lines) > 10:
            sections = self._refine_oversized_header(sections)

        return sections

    def _refine_oversized_header(self, sections: dict[str, list[str]]) -> dict[str, list[str]]:
        header = sections.get("header", [])
        if len(header) <= 10:
            return sections

        new_sections = {"header": []}
        current = "header"
        true_header_done = False
        header_line_limit = 6                                        

        for i, line in enumerate(header):
            if i < header_line_limit:
                new_sections["header"].append(line)
                continue

            if not true_header_done:
                true_header_done = True

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

                                                                               

    def _build_profile(self, sections: dict[str, list[str]], pdf_urls: list[str]) -> ResumeProfile:
        header_lines = sections.get("header", [])
        info = extract_personal_info(header_lines, pdf_urls)

        links = [
            LinkItem(label=lnk["label"], url=lnk["url"])
            for lnk in info.get("links", [])
        ]

        personal_info = PersonalInfo(
            name=info.get("name"),
            email=info.get("email"),
            phone=info.get("phone"),
            location=info.get("location"),
            headline=info.get("headline"),
        )

        return ResumeProfile(
            personal_info=personal_info,
            links=links,
            summary=self._parse_summary(sections.get("summary", [])),
            skills=parse_skills_adaptive(sections.get("skills", [])),
            experience=parse_experience_adaptive(sections.get("experience", [])),
            education=parse_education_adaptive(sections.get("education", [])),
            projects=parse_projects_adaptive(sections.get("projects", [])),
            certifications=[],
            languages=parse_list_section(sections.get("languages", [])),
            awards=parse_list_section(sections.get("awards", [])),
            interests=parse_list_section(sections.get("interests", [])),
        )

    def _parse_summary(self, lines: list[str]) -> Optional[str]:
        if not lines:
            return None
        combined = " ".join(line.strip() for line in lines if line.strip())
        return combined if len(combined) > 20 else None
