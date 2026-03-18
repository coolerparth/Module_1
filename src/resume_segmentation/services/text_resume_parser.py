"""
text_resume_parser.py — Enhanced text-based resume parser.

Improvements over v1:
  - Uses date_extractor module for comprehensive date handling (30+ formats)
  - Uses personal_info_extractor for better name/phone/location detection
  - Better skills parsing (handles "Category: item1, item2" patterns)
  - Improved experience entry boundary detection
  - Better project parsing with tech extraction
  - Handles awards, interests, languages
  - More robust bullet detection
"""
from __future__ import annotations

import re
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
from .personal_info_extractor import (
    extract_links,
    extract_location,
    looks_like_name,
)
from .section_catalog import match_section_heading

                                                                               
          
                                                                               
_EMAIL_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.+\-]*"
    r"@[A-Za-z0-9][A-Za-z0-9\-]*"
    r"(?:\.[A-Za-z0-9\-]+)*"                                                           
    r"\.[A-Za-z]{2,}"                      
)
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")
_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com/[^\s]+|github\.com/[^\s]+)")
_GPA_RE = re.compile(r"(CGPA|GPA|Percentage)[:\s]*([0-9.]+(?:\s*/\s*[0-9.]+)?%?)", re.IGNORECASE)
_DEGREE_RE = re.compile(
    r"\b(?:B\.?(?:Sc|Tech|E|S|A|Com|Ed)|M\.?(?:Sc|Tech|E|S|A|Com|Ed|B|Phil)|"
    r"Ph\.?D|B\.?B\.?A|M\.?B\.?A|B\.?C\.?A|M\.?C\.?A|"
    r"Bachelor|Master|Doctor|Doctorate|Associate|Diploma|"
    r"BTech|MTech|BCA|MCA|BSc|MSc|BBA|MBA|BE|ME|"
    r"B\.Eng|M\.Eng|High\s+School|Secondary|Intermediate|10th|12th|SSC|HSC|CBSE|ICSE)\b",
    re.IGNORECASE,
)

_BULLET_CHARS = ("–", "-", "•", "▸", "►", "●", "▶", "✓", "✔", "*", "·", "◦")
_BULLET_PREFIX_RE = re.compile(r"^[•\-–—►▸●▶✓✔*·◦]\s+")

_JOB_TITLE_WORDS = frozenset({
    "intern", "internship", "engineer", "developer", "analyst", "manager",
    "senior", "junior", "associate", "lead", "architect", "consultant",
    "specialist", "coordinator", "director", "officer", "head",
    "executive", "researcher", "scientist", "professor", "assistant",
    "teaching", "part-time", "full-time", "contract", "freelance",
    "trainee", "apprentice", "fellow", "staff",
})

_EDU_INSTITUTION_WORDS = frozenset({
    "university", "college", "institute", "school", "iit", "nit", "bits",
    "academy", "polytechnic", "campus",
})

                                
_TECH_PATTERNS: dict[str, str] = {
    "Python": r"\bpython\b",
    "Java": r"\bjava\b(?!script)",
    "JavaScript": r"\bjavascript\b|\bjs\b",
    "TypeScript": r"\btypescript\b|\bts\b",
    "C++": r"\bc\+\+\b",
    "C#": r"\bc#\b",
    "Go": r"\bgolang\b|\bgo\b",
    "Rust": r"\brust\b",
    "React": r"\breact(?:\.js|js)?\b",
    "Node.js": r"\bnode(?:\.js|js)\b",
    "Angular": r"\bangular\b",
    "Vue": r"\bvue(?:\.js|js)?\b",
    "Django": r"\bdjango\b",
    "Flask": r"\bflask\b",
    "FastAPI": r"\bfastapi\b",
    "Spring": r"\bspring(?:\s+boot)?\b",
    "TensorFlow": r"\btensorflow\b",
    "PyTorch": r"\bpytorch\b",
    "Pandas": r"\bpandas\b",
    "NumPy": r"\bnumpy\b",
    "scikit-learn": r"\bscikit[-\s]learn\b",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"\bkubernetes\b|\bk8s\b",
    "AWS": r"\baws\b",
    "GCP": r"\bgcp\b",
    "Azure": r"\bazure\b",
    "MySQL": r"\bmysql\b",
    "PostgreSQL": r"\bpostgresql\b|\bpostgres\b",
    "MongoDB": r"\bmongodb\b",
    "Redis": r"\bredis\b",
    "Git": r"\bgit\b",
    "Linux": r"\blinux\b",
    "Streamlit": r"\bstreamlit\b",
    "LangChain": r"\blangchain\b",
    "NLP": r"\bnlp\b",
    "LLM": r"\bllm\b",
    "OpenCV": r"\bopencv\b",
    "PyMuPDF": r"\bpymupdf\b",
    "Pillow": r"\bpillow\b|\bpil\b",
    "Tailwind": r"\btailwind\b",
    "Bootstrap": r"\bbootstrap\b",
    "GraphQL": r"\bgraphql\b",
    "REST": r"\brest\s*api\b",
    "Firebase": r"\bfirebase\b",
    "Figma": r"\bfigma\b",
    "Tableau": r"\btableau\b",
    "Power BI": r"\bpower\s*bi\b",
    "Excel": r"\bexcel\b",
    "MATLAB": r"\bmatlab\b",
    "R": r"\bR\b(?:\s+programming|\s+language)?",
    "Scala": r"\bscala\b",
    "Kotlin": r"\bkotlin\b",
    "Swift": r"\bswift\b",
    "PHP": r"\bphp\b",
    "Ruby": r"\bruby(?:\s+on\s+rails)?\b",
}


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10 and digits[0] in "6789":
        return "+91 " + digits[:5] + " " + digits[5:]
    return raw


class TextResumeParser:
    def parse(self, lines: list[str], urls: list[str]) -> ResumeProfile:
        sections = self._split_sections(lines)
        return self.parse_sections(sections, urls)

    def parse_sections(self, sections: dict[str, list[str]], urls: list[str]) -> ResumeProfile:
        header_lines = sections.get("header", [])
        links = self._collect_links(header_lines, urls)

        awards_lines = (sections.get("awards", []) +
                        sections.get("publications", []) +
                        sections.get("references", []))
        interests_lines = (sections.get("interests", []) +
                           sections.get("activities", []))

        return ResumeProfile(
            personal_info=self._parse_personal_info(header_lines, links),
            links=links,
            summary=self._parse_summary(sections.get("summary", [])),
            skills=self._parse_skills(sections.get("skills", [])),
            experience=self._parse_experience(sections.get("experience", [])),
            education=self._parse_education(
                sections.get("education", []) + sections.get("courses", [])
            ),
            projects=self._parse_projects(sections.get("projects", [])),
            certifications=self._parse_certifications(sections.get("certifications", [])),
            languages=self._parse_simple_list(sections.get("languages", [])),
            awards=self._parse_simple_list(awards_lines),
            interests=self._parse_simple_list(interests_lines),
        )

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

                                                                               

    def _split_sections(self, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {"header": []}
        current = "header"

        for line in lines:
            stripped = line.strip()
                                                                                
            if self._is_bullet_line(stripped):
                sections.setdefault(current, []).append(stripped)
                continue
            key = match_section_heading(stripped)
            if key:
                current = key
                sections.setdefault(current, [])
                continue
            sections.setdefault(current, []).append(stripped)

        return sections

                                                                               

    def _parse_personal_info(self, header_lines: list[str], links: list[LinkItem]) -> PersonalInfo:
        combined = " ".join(header_lines)

        name: Optional[str] = None
        for line in header_lines[:4]:
            segments = re.split(r"\s*[|•·]\s*", line.strip())
            for seg in segments:
                seg = _EMAIL_RE.sub("", seg)
                seg = _PHONE_RE.sub("", seg)
                seg = _URL_RE.sub("", seg)
                seg = re.sub(r"\s+", " ", seg).strip()
                if looks_like_name(seg):
                    name = seg
                    break
            if name:
                break

        if not name and header_lines:
            first = re.split(r"\s*[|•·]\s*", header_lines[0].strip())[0].strip()
            if len(first.split()) <= 5 and not _EMAIL_RE.search(first):
                name = first or None

        email_match = _EMAIL_RE.search(combined)

                                                                  
        phone: Optional[str] = None
        for line in header_lines:
            clean = _EMAIL_RE.sub("", line)
            clean = _URL_RE.sub("", clean)
            m = _PHONE_RE.search(clean)
            if m:
                raw = m.group(0).strip()
                digits = sum(c.isdigit() for c in raw)
                if digits >= 10:
                    phone = _normalize_phone(raw)
                    break

        location = extract_location(header_lines)

                                                                          
        headline: Optional[str] = None
        for line in header_lines[1:5]:
            stripped = line.strip()
            if not stripped or stripped == name:
                continue
            if _EMAIL_RE.search(stripped) or _PHONE_RE.search(stripped):
                continue
            if _URL_RE.search(stripped):
                continue
            segs = re.split(r"\s*[|•·]\s*", stripped)
            candidate = segs[0].strip()
            if not candidate:
                continue
            words = candidate.split()
            if 2 <= len(words) <= 12 and not any(c.isdigit() for c in candidate):
                if not any(w.lower() in ("linkedin", "github", "http", "www") for w in words):
                    headline = candidate
                    break

        return PersonalInfo(
            name=name,
            email=email_match.group(0).lower() if email_match else None,
            phone=phone,
            location=location,
            headline=headline,
        )

    def _collect_links(self, header_lines: list[str], urls: list[str]) -> list[LinkItem]:
        raw_links = extract_links(header_lines, urls)
        return [LinkItem(label=lnk["label"], url=lnk["url"]) for lnk in raw_links]

                                                                               

    def _parse_summary(self, lines: list[str]) -> Optional[str]:
        if not lines:
            return None
        text = " ".join(line.strip() for line in lines if line.strip())
        return text if len(text) > 30 else None

                                                                               

    def _parse_skills(self, lines: list[str]) -> list[str]:
        skills: list[str] = []
        seen: set[str] = set()

        def _add(skill: str) -> None:
            cleaned = re.sub(r"\s+", " ", skill).strip().strip("•-–—*")
                                              
            cleaned = re.sub(r"\s*\((?:Basic|Intermediate|Advanced|Beginner|Expert|Proficient)\)\s*", "", cleaned, flags=re.IGNORECASE)
            if cleaned and 1 <= len(cleaned) <= 60:
                key = cleaned.lower()
                if key not in seen:
                    seen.add(key)
                    skills.append(cleaned)

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

                                 
            if _BULLET_PREFIX_RE.match(stripped):
                stripped = _BULLET_PREFIX_RE.sub("", stripped).strip()

                                     
            if ":" in stripped:
                _, _, items_part = stripped.partition(":")
                raw_items = items_part.strip()
                if raw_items:
                    for item in re.split(r"[,|]", raw_items):
                        _add(item.strip())
                    continue

                                  
            if "," in stripped or "|" in stripped:
                for item in re.split(r"[,|]", stripped):
                    _add(item.strip())
                continue

                          
            _add(stripped)

        return skills

                                                                               

    def _parse_education(self, lines: list[str]) -> list[EducationEntry]:
        lines = [l.strip() for l in lines if l.strip()]
        if not lines:
            return []

                                        
                                                                               
                                                                                
        groups: list[list[str]] = []
        current: list[str] = []

        for line in lines:
            starts_new = False
            if current:
                                                           
                _, dr = extract_date_range(line)
                has_degree = bool(_DEGREE_RE.search(line))
                lower = line.lower()
                is_institution = any(w in lower for w in _EDU_INSTITUTION_WORDS)
                gpa_only = bool(_GPA_RE.search(line)) and not has_degree and not is_institution

                                                                               
                if gpa_only:
                    starts_new = False
                elif dr and not line.replace(line[line.find(dr.start or ""):], "").strip():
                                                               
                    starts_new = False
                elif has_degree and not is_institution:
                                                                             
                    has_degree_in_current = any(_DEGREE_RE.search(l) for l in current)
                    starts_new = has_degree_in_current
                elif is_institution and not has_degree:
                                                                                     
                    has_inst_in_current = any(
                        any(w in l.lower() for w in _EDU_INSTITUTION_WORDS)
                        for l in current
                    )
                    starts_new = has_inst_in_current

            if starts_new:
                                                                                      
                                                                                       
                last_line = current[-1] if current else ""
                _, last_dr = extract_date_range(last_line)
                last_has_degree = bool(_DEGREE_RE.search(last_line))
                last_has_gpa = bool(_GPA_RE.search(last_line))
                last_is_orphan = (
                    last_line
                    and not last_dr
                    and not last_has_degree
                    and not last_has_gpa
                    and last_line[0:1].isupper()
                )
                if last_is_orphan:
                    groups.append(current[:-1])                             
                    current = [last_line, line]                                      
                else:
                    groups.append(current)
                    current = [line]
            else:
                current.append(line)

        if current:
            groups.append(current)

        entries: list[EducationEntry] = []
        for group in groups:
            entry = self._parse_edu_group(group)
            if entry and (entry.institution or entry.degree):
                entries.append(entry)

        return entries

                                                                                            
    _EDU_SKIP_PREFIXES = re.compile(
        r"^(?:Thesis|Dissertation|Research|Topic|Project|Specialization|Minor|Focus|"
        r"Concentration|Advisor|Supervisor|Committee|Note|Award|Honours?|Cum\s+Laude)"
        r"\s*[:\-–]",
        re.IGNORECASE,
    )

    def _parse_edu_group(self, lines: list[str]) -> Optional[EducationEntry]:
        institution: Optional[str] = None
        degree: Optional[str] = None
        field_of_study: Optional[str] = None
        date_range = None
        gpa: Optional[str] = None

        for line in lines:
                                                                           
            if self._EDU_SKIP_PREFIXES.match(line.strip()):
                continue

            remaining, dr = extract_date_range(line)
            if dr and not date_range:
                date_range = dr
            line = remaining.strip() if remaining.strip() else line

            gpa_m = _GPA_RE.search(line)
            if gpa_m:
                gpa = gpa_m.group(2).strip()
                line = _GPA_RE.sub("", line).strip(" ,-")

            if not line:
                continue

            if _DEGREE_RE.search(line):
                                                             
                m_in = re.search(r"\bin\s+(.+)$", line, re.IGNORECASE)
                                                                          
                m_dash = re.search(r"\s+[–—\-]\s+(.+)$", line)
                if m_in:
                    degree = line[:m_in.start()].strip() or None
                    field_of_study = m_in.group(1).strip()
                elif m_dash and _DEGREE_RE.search(line[:m_dash.start()]):
                    degree = line[:m_dash.start()].strip() or None
                    field_of_study = m_dash.group(1).strip()
                else:
                    degree = line
            elif not institution:
                institution = line
            elif not degree:
                degree = line

        return EducationEntry(
            institution=institution,
            degree=degree,
            field_of_study=field_of_study,
            date_range=date_range,
            gpa=gpa,
        )

                                                                               

    def _parse_experience(self, lines: list[str]) -> list[ExperienceEntry]:
        if not lines:
            return []

        lines = self._merge_wrapped_lines(lines, self._looks_like_experience_header)
        entries: list[ExperienceEntry] = []
        i = 0

        while i < len(lines):
            header_lines: list[str] = []
            bullets: list[str] = []

                                             
            while i < len(lines) and not self._is_bullet_line(lines[i]):
                header_lines.append(lines[i].strip())
                i += 1

                                  
            while i < len(lines) and self._is_bullet_line(lines[i]):
                bullets.append(self._strip_bullet(lines[i]))
                i += 1

            if not header_lines:
                continue

            date_range: Optional[DateRange] = None
            cleaned_headers: list[str] = []

            for line in header_lines:
                remaining, dr = extract_date_range(line)
                if dr and not date_range:
                    date_range = dr
                if remaining.strip():
                    cleaned_headers.append(remaining.strip())

            cleaned_headers = [h for h in cleaned_headers if h]

            title: Optional[str] = None
            company: Optional[str] = None
            location: Optional[str] = None

            if len(cleaned_headers) >= 2:
                first, second = cleaned_headers[0], cleaned_headers[1]
                if self._looks_like_title(first):
                    title, company = first, second
                else:
                    company, title = first, second
            elif cleaned_headers:
                only = cleaned_headers[0]
                if self._looks_like_title(only):
                    title = only
                else:
                    company = only

                                                                        
                                                                 
            _COMPANY_SUFFIXES = re.compile(
                r'^(?:Inc|Ltd|LLC|LLP|Corp|Co|Pvt|Private|Limited|'
                r'Group|Holdings|Partners|Associates|Solutions|Services|'
                r'Technologies|Consulting|Ventures|International|Global)\.?$',
                re.IGNORECASE,
            )
            if company and "," in company:
                parts = [p.strip() for p in company.split(",", 1)]
                                                                                  
                if (len(parts) == 2
                        and len(parts[1]) <= 35
                        and not _COMPANY_SUFFIXES.match(parts[1].strip())):
                    company = parts[0]
                    location = parts[1]

            entries.append(ExperienceEntry(
                company=company,
                title=title,
                date_range=date_range,
                location=location,
                bullets=bullets,
            ))

        return [e for e in entries if e.company or e.title or e.bullets]

                                                                               

    def _parse_projects(self, lines: list[str]) -> list[ProjectEntry]:
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
                                                          
                if projects:
                    last = projects[-1]
                    desc = ((last.description or "") + " " + self._strip_bullet(line)).strip()
                    projects[-1] = ProjectEntry(
                        name=last.name, description=desc,
                        date_range=last.date_range,
                        technologies=last.technologies, url=last.url,
                    )
                i += 1
                continue

            remaining, date_range = extract_date_range(line)

                                                                 
            if not remaining.strip() and date_range:
                if projects and not projects[-1].date_range:
                    last = projects[-1]
                    projects[-1] = ProjectEntry(
                        name=last.name, description=last.description,
                        date_range=date_range,
                        technologies=last.technologies, url=last.url,
                    )
                i += 1
                continue

            name = (remaining.strip() or line.strip())

            proj_url: Optional[str] = None
            if "|" in name:
                parts = [p.strip() for p in name.split("|")]
                url_parts = [p for p in parts if re.search(r'https?://|github\.com|gitlab\.com|bitbucket\.org', p, re.I)]
                non_url_parts = [p for p in parts if p not in url_parts]
                if url_parts:
                    raw_url = url_parts[0]
                    proj_url = raw_url if raw_url.startswith("http") else "https://" + raw_url
                name = " | ".join(non_url_parts).strip() if non_url_parts else parts[0]

            name = re.sub(r'\s*[–—·]\s*$', '', name).strip()
            i += 1

                                                              
                                                          
                             
                                                                            
            all_content: list[str] = []

                                   
            if i < len(lines):
                rem2, dr2 = extract_date_range(lines[i].strip())
                if not rem2.strip() and dr2 and not date_range:
                    date_range = dr2
                    i += 1

                                                             
            while i < len(lines):
                nxt = lines[i].strip()
                if not nxt:
                    i += 1
                    continue
                if self._is_bullet_line(nxt):
                    all_content.append(self._strip_bullet(nxt))
                    i += 1
                elif self._looks_like_project_header(nxt):
                    break                       
                else:
                                                       
                    all_content.append(nxt)
                    i += 1

            description = " ".join(all_content) if all_content else None
            techs = self._extract_technologies(" ".join([name] + all_content))

            projects.append(ProjectEntry(
                name=name,
                description=description,
                date_range=date_range,
                technologies=techs,
                url=proj_url,
            ))

        return [p for p in projects if p.name]

                                                                                

    def _parse_certifications(self, lines: list[str]) -> list:
        from ..models.resume import CertificationEntry
        entries: list[CertificationEntry] = []
        seen: set[str] = set()

        _CERT_DATE_RE = re.compile(r"\((\d{4})\)\s*$|\b(\d{4})\s*$")
        _ISSUER_RE = re.compile(
            r"\b(?:by|from|issued\s+by|provider:)\s+(.+)$",
            re.IGNORECASE,
        )

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_bullet_line(stripped):
                stripped = self._strip_bullet(stripped)

            date: Optional[str] = None
            issuer: Optional[str] = None
            name_part = stripped

            date_m = _CERT_DATE_RE.search(stripped)
            if date_m:
                date = date_m.group(1) or date_m.group(2)
                name_part = stripped[:date_m.start()].strip().rstrip("(- ,")

            issuer_m = _ISSUER_RE.search(name_part)
            if issuer_m:
                issuer = issuer_m.group(1).strip()
                name_part = name_part[:issuer_m.start()].strip().rstrip("- ,")

            name_part = name_part.strip()
            if not name_part:
                continue
            key = name_part.lower()
            if key in seen:
                continue
            seen.add(key)
            entries.append(CertificationEntry(name=name_part, issuer=issuer, date=date))

        return entries

    def _parse_simple_list(self, lines: list[str]) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if self._is_bullet_line(stripped):
                item = self._strip_bullet(stripped)
            elif "," in stripped and len(stripped) < 100:
                for part in stripped.split(","):
                    part = part.strip()
                    if part and part.lower() not in seen:
                        seen.add(part.lower())
                        items.append(part)
                continue
            else:
                item = stripped

            if item and item.lower() not in seen:
                seen.add(item.lower())
                items.append(item)

        return items

                                                                                

    def _extract_technologies(self, text: str) -> list[str]:
        lowered = text.lower()
        found: list[str] = []
        for label, pattern in _TECH_PATTERNS.items():
            if re.search(pattern, lowered, re.IGNORECASE):
                found.append(label)
        return found

                                                                               

    def _is_bullet_line(self, line: str) -> bool:
        return _BULLET_PREFIX_RE.match(line.strip()) is not None

    def _strip_bullet(self, line: str) -> str:
        return _BULLET_PREFIX_RE.sub("", line.strip()).strip()

    def _looks_like_title(self, text: str) -> bool:
        lowered = text.lower()
                                                                  
                                                                                    
        return any(
            re.search(r'\b' + re.escape(token) + r'\b', lowered)
            for token in _JOB_TITLE_WORDS
        )

    def _looks_like_experience_header(self, line: str) -> bool:
        stripped = line.strip()
        if self._is_bullet_line(stripped):
            return False
        cleaned, date_range = extract_date_range(stripped)
        if date_range or self._looks_like_title(cleaned):
            return True
                                                                          
        _SUFFIX_DOT = re.compile(
            r'\b(?:Ltd|Inc|Corp|Co|LLC|LLP|Pvt|PVT|Ltd|Plc|Llp)\.$', re.IGNORECASE
        )
        effective = _SUFFIX_DOT.sub("", cleaned).rstrip()
        return bool(
            effective[:1].isupper()
            and len(cleaned) <= 80
            and (not cleaned.endswith(".") or _SUFFIX_DOT.search(cleaned))
        )

    def _looks_like_project_header(self, line: str) -> bool:
        stripped = line.strip()
        if self._is_bullet_line(stripped):
            return False
        cleaned, date_range = extract_date_range(stripped)
        if date_range and not cleaned.strip():
            return False                                       
        if date_range:
            return True
        words = cleaned.split()
                                                                              
        if len(words) > 7:
            return False
                                                              
        return bool(
            cleaned[:1].isupper()
            and len(cleaned) <= 80
            and not cleaned.endswith(".")
        )

    def _merge_wrapped_lines(self, lines: list[str], is_new_header) -> list[str]:
        merged: list[str] = []
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if not merged:
                merged.append(line)
                continue
            if self._is_bullet_line(line) or is_new_header(line):
                merged.append(line)
                continue
                                      
            if self._is_bullet_line(merged[-1]):
                merged[-1] = f"{merged[-1]} {line}".strip()
            else:
                merged[-1] = f"{merged[-1]} {line}".strip()
        return merged
