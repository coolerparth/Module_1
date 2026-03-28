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
from .personal_info_extractor import extract_links, extract_location, looks_like_name
from .knowledge_base import load_degree_alias_ontology
from .projects_parser import ProjectsParser
from .section_catalog import match_section_heading
from .spacy_ner_extractor import extract_orgs_from_section, ner_available

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.+\-]*"
    r"@[A-Za-z0-9][A-Za-z0-9\-]*"
    r"(?:\.[A-Za-z0-9\-]+)*"
    r"\.[A-Za-z]{2,}"
)
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")
_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:linkedin\.com/[^\s]+|github\.com/[^\s]+)",
    re.IGNORECASE,
)
_GPA_RE = re.compile(
    r"(CGPA|GPA|Percentage|Score|Marks|Grade|Points|CPI|SGPA|DGPA)[:\s]*([0-9.]+(?:\s*/\s*[0-9.]+)?%?)",
    re.IGNORECASE,
)
_GPA_TRAILING_RE = re.compile(
    r"([0-9.]+(?:\s*/\s*[0-9.]+)?%?)\s*(CGPA|GPA|Percentage|Score|Marks|Grade|Points|CPI|SGPA|DGPA)",
    re.IGNORECASE,
)
_BASE_DEGREE_TERMS = [
    "Bachelor", "Master", "Doctor", "Doctorate", "Associate", "Diploma",
    "BSc", "MSc", "BTech", "MTech", "BCA", "MCA", "BBA", "MBA",
    "B.E", "M.E", "B.Eng", "M.Eng", "High School", "Secondary",
    "Intermediate", "10th", "12th", "SSC", "HSC", "CBSE", "ICSE", "ISC", "CISCE",
]


def _build_degree_regex() -> re.Pattern[str]:
    terms = set(_BASE_DEGREE_TERMS)
    for _, aliases in load_degree_alias_ontology().items():
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if isinstance(alias, str) and alias.strip():
                terms.add(alias.strip())
    ordered = sorted(terms, key=len, reverse=True)
    pattern = r"\b(?:" + "|".join(
        re.escape(term).replace(r"\ ", r"\s+") for term in ordered
    ) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


_DEGREE_RE = _build_degree_regex()

_BULLET_PREFIX_RE = re.compile(r"^[•\-–—►▸●▶✓✔*·◦]\s+")
_BULLET_CHARS = ("–", "-", "•", "▸", "►", "●", "▶", "✓", "✔", "*", "·", "◦")

_JOB_TITLE_WORDS = frozenset({
    "intern", "internship", "engineer", "developer", "analyst", "manager",
    "senior", "junior", "associate", "lead", "architect", "consultant",
    "specialist", "coordinator", "director", "officer", "head",
    "executive", "researcher", "scientist", "professor", "assistant",
    "teaching", "part-time", "full-time", "contract", "freelance",
    "trainee", "apprentice", "fellow", "staff",
    "sde", "mle", "sre", "tpm", "tl", "em", "ic",
    "devops", "frontend", "backend", "fullstack", "full-stack",
    "mobile", "ios", "android", "ml", "ai", "data",
    "product", "design", "qa", "test", "automation",
    "cloud", "security", "network", "system", "software",
    "principal", "staff", "distinguished", "vice", "president",
    "cto", "ceo", "coo", "vp", "avp", "gm", "dgm",
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
    "Scala": r"\bscala\b",
    "Kotlin": r"\bkotlin\b",
    "Swift": r"\bswift\b",
    "PHP": r"\bphp\b",
    "Ruby": r"\bruby(?:\s+on\s+rails)?\b",
}

_COMPANY_SUFFIX_RE = re.compile(
    r"^(?:Inc|Ltd|LLC|LLP|Corp|Co|Pvt|Private|Limited|"
    r"Group|Holdings|Partners|Associates|Solutions|Services|"
    r"Technologies|Consulting|Ventures|International|Global)\.?$",
    re.IGNORECASE,
)


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10 and digits[0] in "6789":
        return "+91 " + digits[:5] + " " + digits[5:]
    return raw


_SOFT_SKILL_WORDS: frozenset[str] = frozenset({
    "communication", "teamwork", "leadership", "time management",
    "problem solving", "critical thinking", "self-motivated", "self motivated",
    "quick learner", "detail-oriented", "detail oriented", "adaptable",
    "interpersonal", "organizational", "multitasking", "collaborative",
    "proactive", "result-oriented", "result oriented", "deadline-driven",
    "fast learner", "team player", "hardworking", "dedicated",
    "passionate", "motivated", "creative", "innovative",
    "analytical", "strategic", "dynamic",
    "bilingual", "multilingual",
    "ability to", "ability to work", "willingness to",
})

_INLINE_BULLET_RE = re.compile(r"[•·◦►▸●▶✓✔]")
_SKILL_LABEL_PREFIX_RE = re.compile(
    r"^(?:languages?|programming\s+languages?|development|design|databases?|"
    r"developer\s+tools?|business\s+intelligence\s+tools?|ai/ml|ai\s*&\s*ml|"
    r"iot\s+platforms?|frameworks?|libraries|tools?|cloud|platforms?|"
    r"technologies|technical\s+skills?|core\s+skills?|key\s+skills?)\s*:\s*",
    re.IGNORECASE,
)

_CONTACT_SIGNAL_RE = re.compile(
    r"(?:email|e-?mail|phone|mobile|linkedin|github|gitlab|portfolio|website|contact|address)\s*[:\-]?",
    re.IGNORECASE,
)
_EMBEDDED_SKILL_LABEL_RE = re.compile(
    r"\s+(?=(?:AI/ML|Backend/Tools|Backend|Big\s+Data|Core\s+CS|Databases?|"
    r"Database\s*&\s*Cloud|Developer\s+Tools?|Frameworks(?:/Tools|\s*&\s*Tools)?|"
    r"Languages?|Libraries\s*&\s*Technologies|Tools?)\s*:)",
    re.IGNORECASE,
)
_DURATION_PAREN_RE = re.compile(
    r"\s*\((?:Less\s+Than\s+)?\d+\+?\s+Years?\)\s*",
    re.IGNORECASE,
)
_TRAILING_DURATION_RE = re.compile(
    r"\s*[-–,]?\s*(?:Less\s+Than\s+)?\d+\+?\s+Years?$",
    re.IGNORECASE,
)


def _is_header_label_line(text: str) -> bool:
    key = match_section_heading(text.strip().rstrip(':'))
    return key is not None

class TextResumeParser:
    def __init__(self) -> None:
        self._projects_parser = ProjectsParser()

    def parse(self, lines: list[str], urls: list[str]) -> ResumeProfile:
        sections = self._split_sections(lines)
        return self.parse_sections(sections, urls)

    def parse_sections(
        self, sections: dict[str, list[str]], urls: list[str]
    ) -> ResumeProfile:
        header_lines = sections.get("header", [])
        contact_lines = self._collect_contact_lines(header_lines, sections)
        links = self._collect_links(contact_lines, urls)

        awards_lines = (
            sections.get("awards", [])
            + sections.get("publications", [])
            + sections.get("references", [])
        )
        interests_lines = sections.get("interests", []) + sections.get("activities", [])

        education_lines = sections.get("education", []) + sections.get("courses", [])
        if not education_lines:
            education_lines = self._infer_header_education(header_lines)

        profile = ResumeProfile(
            personal_info=self._parse_personal_info(contact_lines, links),
            links=links,
            summary=self._parse_summary(sections.get("summary", [])),
            skills=self._parse_skills(sections.get("skills", [])),
            experience=self._parse_experience(sections.get("experience", [])),
            education=self._parse_education(education_lines),
            projects=self._parse_projects(sections.get("projects", [])),
            certifications=self._parse_certifications(sections.get("certifications", [])),
            languages=self._parse_simple_list(sections.get("languages", [])),
            awards=self._parse_simple_list(awards_lines),
            interests=self._parse_simple_list(interests_lines),
        )

        # P3: Supplement skills with tech terms implied from experience/project bullets
        profile.skills = self._augment_skills_from_bullets(
            profile.skills,
            sections.get("experience", []) + sections.get("projects", []),
        )

        return profile

    # Pre-compiled tech pattern matchers for bullet-implied skill extraction
    _COMPILED_TECH_RE: dict[str, re.Pattern] = {}

    @classmethod
    def _get_compiled_tech_re(cls) -> dict[str, re.Pattern]:
        if not cls._COMPILED_TECH_RE:
            cls._COMPILED_TECH_RE = {
                name: re.compile(pattern, re.IGNORECASE)
                for name, pattern in _TECH_PATTERNS.items()
            }
        return cls._COMPILED_TECH_RE

    def _augment_skills_from_bullets(
        self,
        existing_skills: list[str],
        bullet_lines: list[str],
    ) -> list[str]:
        """Scan experience/project bullets for well-known tech names and add to skills."""
        existing_lower = {s.lower().strip() for s in existing_skills}
        # Also normalize known aliases so we don't double-add (e.g. 'react' when 'React.js' exists)
        existing_canonical_lower = {
            re.sub(r"[.\-_\s]+", "", s.lower()) for s in existing_lower
        }

        found: list[str] = []
        full_text = " ".join(bullet_lines)
        compiled = self._get_compiled_tech_re()

        for tech_name, pattern in compiled.items():
            if pattern.search(full_text):
                key = tech_name.lower().strip()
                key_compact = re.sub(r"[.\-_\s]+", "", key)
                if key not in existing_lower and key_compact not in existing_canonical_lower:
                    found.append(tech_name)
                    existing_lower.add(key)
                    existing_canonical_lower.add(key_compact)

        return existing_skills + found

    def _collect_contact_lines(
        self,
        header_lines: list[str],
        sections: dict[str, list[str]],
    ) -> list[str]:
        combined = list(header_lines)
        seen = {line.strip() for line in combined if line.strip()}

        for section_name in ("summary",):
            for line in sections.get(section_name, [])[:12]:
                stripped = line.strip()
                if not stripped or stripped in seen:
                    continue
                if (
                    _EMAIL_RE.search(stripped)
                    or _PHONE_RE.search(stripped)
                    or _URL_RE.search(stripped)
                    or _CONTACT_SIGNAL_RE.search(stripped)
                ):
                    combined.append(stripped)
                    seen.add(stripped)

        return combined

    def _infer_header_education(self, header_lines: list[str]) -> list[str]:
        inferred: list[str] = []
        for raw in header_lines:
            stripped = raw.strip()
            if not stripped:
                continue
            if _EMAIL_RE.search(stripped) or _PHONE_RE.search(stripped) or _URL_RE.search(stripped):
                continue
            cleaned = self._clean_header_segment(stripped)
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in {"male", "female", "dob", "date of birth"}:
                continue
            if looks_like_name(cleaned) and len(cleaned.split()) <= 4:
                continue
            has_degree = bool(_DEGREE_RE.search(cleaned))
            has_institution = self._is_institution_name(cleaned)
            has_gpa = bool(
                _GPA_RE.search(cleaned)
                or _GPA_TRAILING_RE.search(cleaned)
                or re.search(r"[0-9]+(?:\.[0-9]+)?\s*%$", cleaned)
            )
            if has_degree or has_institution or has_gpa:
                inferred.append(cleaned)
        return inferred if len(inferred) >= 2 else []

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

    def _parse_personal_info(
        self, header_lines: list[str], links: list[LinkItem]
    ) -> PersonalInfo:
        combined = " ".join(header_lines)

        name: Optional[str] = None
        cleaned_header_lines = [self._clean_header_segment(line) for line in header_lines if line.strip()]

        if len(cleaned_header_lines) >= 2:
            first_two = cleaned_header_lines[:2]
            if all(
                line
                and len(line.split()) <= 2
                and re.fullmatch(r"[A-Za-z][A-Za-z\s.'-]*", line)
                for line in first_two
            ):
                joined = " ".join(first_two)
                if looks_like_name(joined.title()):
                    name = joined.title()

        for line in cleaned_header_lines[:8]:
            if _is_header_label_line(line):
                continue
            segments = re.split(r"\s*[|•·]\s*", line.strip())
            for seg in segments:
                seg = self._clean_header_segment(seg)
                if looks_like_name(seg):
                    name = seg
                    break
            if name:
                break

        if not name and cleaned_header_lines:
            first = re.split(r"\s*[|•·]\s*", cleaned_header_lines[0].strip())[0].strip()
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
                if sum(c.isdigit() for c in raw) >= 10:
                    phone = _normalize_phone(raw)
                    break

        location = extract_location(header_lines)

        headline: Optional[str] = None
        for line in cleaned_header_lines[1:8]:
            stripped = line.strip()
            if _is_header_label_line(stripped):
                continue
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
                if not any(
                    w.lower() in ("linkedin", "github", "http", "www") for w in words
                ):
                    headline = candidate
                    break

        return PersonalInfo(
            name=name,
            email=email_match.group(0).lower() if email_match else None,
            phone=phone,
            location=location,
            headline=headline,
        )

    def _clean_header_segment(self, value: str) -> str:
        cleaned = value.strip()
        cleaned = re.sub(r"/[A-Za-z_]+", " ", cleaned)
        cleaned = _EMAIL_RE.sub(" ", cleaned)
        cleaned = _PHONE_RE.sub(" ", cleaned)
        cleaned = _URL_RE.sub(" ", cleaned)
        cleaned = re.sub(
            r"^(?:email|e-?mail|phone|mobile|linkedin|github|gitlab|portfolio|website|contact|address)\s*[:\-]?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\b(?:email|e-?mail|phone|mobile|linkedin|github|gitlab|portfolio|website|contact|address)\s*[:\-]?\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" |•·:-")
        return cleaned

    def _collect_links(
        self, header_lines: list[str], urls: list[str]
    ) -> list[LinkItem]:
        raw_links = extract_links(header_lines, urls)
        return [LinkItem(label=lnk["label"], url=lnk["url"]) for lnk in raw_links]

    _SUMMARY_PREFIX_RE = re.compile(
        r"^(?:objective|career\s+objective|professional\s+objective|"
        r"summary|professional\s+summary|career\s+summary|"
        r"about\s+me|about|profile|professional\s+profile|"
        r"intro(?:duction)?|overview|background|career\s+overview|"
        r"value\s+proposition|professional\s+background|"
        r"career\s+goal|goals?|highlights?)\s*[:\-–]\s*",
        re.IGNORECASE,
    )

    def _parse_summary(self, lines: list[str]) -> Optional[str]:
        if not lines:
            return None
        clean_lines: list[str] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_bullet_line(stripped):
                stripped = self._strip_bullet(stripped)
            stripped = re.sub(r"\s+(?=(?:Big\s+Data|Backend/Tools|Databases|Core\s+CS|Languages?|Frameworks(?:/Tools|\s*&\s*Tools)?|Libraries\s*&\s*Technologies|Developer\s+Tools)\s*:)", " | ", stripped, flags=re.IGNORECASE)
            cleaned = self._SUMMARY_PREFIX_RE.sub("", stripped).strip()
            if cleaned:
                clean_lines.append(cleaned)
        text = " ".join(clean_lines)
        return text if len(text) >= 15 else None

    def _parse_skills(self, lines: list[str]) -> list[str]:
        skills: list[str] = []
        seen: set[str] = set()

        def _add(skill: str) -> None:
            cleaned = re.sub(r"\s+", " ", skill).strip().strip("•-–—*·◦►▸")
            cleaned = _DURATION_PAREN_RE.sub(" ", cleaned)
            cleaned = _TRAILING_DURATION_RE.sub("", cleaned)
            cleaned = re.sub(r"(?:Backend/Tools|Big\s+Data|Core\s+CS|Databases|Developer\s+Tools|Frameworks(?:/Tools|\s*&\s*Tools)?|Libraries\s*&\s*Technologies|Languages?)\s*:?$", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(
                r"\s*\((?:Basic|Intermediate|Advanced|Beginner|Expert|Proficient|"
                r"Familiar|Working\s+Knowledge|Strong|Moderate)\)\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                r"\s*[-–:]\s*(?:Basic|Intermediate|Advanced|Beginner|Expert|Proficient)\s*$",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = cleaned.strip()
            # Strip certification parenthetical suffixes like "MongoDB (Certified Associate Developer)"
            cleaned = re.sub(
                r"\s*\((?:Certified|Certification|Certificate|Global\s+Certification|Preparing\s+For|Currently\s+Preparing|Basic\s+Knowledge|[^)]{0,40}(?:Associate|Developer|Practitioner|Professional|Expert|Foundation)[^)]{0,40})\)\s*$",
                "",
                cleaned,
                flags=re.IGNORECASE,
            ).strip()
            if cleaned and 1 <= len(cleaned) <= 60 and not cleaned.isdigit():
                if match_section_heading(cleaned):
                    return
                key = cleaned.lower()
                if key in seen:
                    return
                if key in _SOFT_SKILL_WORDS:
                    return
                if any(key.startswith(p) for p in (
                    "ability to", "willingness to", "fluent in",
                    "knowledge of", "experience with", "experience in",
                )):
                    return
                if _EMAIL_RE.search(cleaned) or _PHONE_RE.search(cleaned) or _URL_RE.search(cleaned):
                    return
                # Only filter clear edu/location words
                if re.search(r"\b(?:university|college|school|academy|class x(?!ii)|class xii|secondary school|b\.?tech\s+in|cgpa|dehradun|present\b|202[0-9]\b)\b", key):
                    return
                # Filter GPA/grade bleeding from education ("GPA: 8.5", "9.87")
                if re.search(r"^gpa\s*[:=]|^cgpa\s*[:=]|^grade\s*[:=]|^marks\s*[:=]", key):
                    return
                # Filter date strings bleeding from education ("Apr 2020", "2020 - 2024")
                if re.search(r"^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}$", key):
                    return
                if re.match(r"^\d{4}\s*[-–]\s*(?:\d{4}|present)$", key, re.IGNORECASE):
                    return
                # Filter degree+institution lines like "B.Tech In Computer Science"
                if re.search(r"\b(?:bachelor|master|b\.tech|m\.tech|b\.sc|m\.sc|b\.e|m\.e|bca|mca|mba)\s+(?:in|of)\b", key):
                    return
                # Filter achievement/section header noise like "SCHOLASTIC / CO-SCHOLASTIC ACHIEVEMENTS"
                if re.search(r"\b(?:scholastic|co-scholastic|achievement|distinction|extracurricular|accomplishment)\b", key):
                    return
                # Filter all-caps acronym-heavy lines with slashes that read like section headers
                if "/" in cleaned and len(cleaned.split()) >= 3 and sum(1 for w in cleaned.split() if w.isupper()) >= 2:
                    return
                seen.add(key)
                skills.append(cleaned)

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if "\n" in stripped:
                for subline in stripped.split("\n"):
                    subline = subline.strip()
                    if subline:
                        _add(subline)
                continue
            stripped = _EMBEDDED_SKILL_LABEL_RE.sub(" | ", stripped)
            stripped = _SKILL_LABEL_PREFIX_RE.sub("", stripped)
            stripped = re.sub(
                r"^(?:Frontend|Backend|Others?|Skills?|Advanced|Intermediate|Basic|"
                r"Expert|Proficient|Familiar|Beginner|Working\s+Knowledge|Primary|Secondary)[:\s]+",
                "", stripped, flags=re.IGNORECASE
            ).strip()
            if not stripped:
                continue
            # P7: Table-cell splitting — multi-column rows like "Python   Java   C++"
            # Detect by: tab characters OR 2+ runs of 3+ consecutive spaces
            has_tabs = "\t" in stripped
            large_gaps = re.findall(r"   +", stripped)  # 3+ consecutive spaces
            if has_tabs or len(large_gaps) >= 2:
                sep = r"\t+|   +"  # Split on tab or 3+ spaces
                cells = [c.strip() for c in re.split(sep, stripped) if c.strip()]
                if len(cells) >= 2 and all(len(c) <= 40 for c in cells):
                    for cell in cells:
                        _add(cell)
                    continue
            if _INLINE_BULLET_RE.search(stripped) or "|" in stripped:
                for item in re.split(r"[|]|" + _INLINE_BULLET_RE.pattern, stripped):
                    _add(item.strip())
                continue
            if "," in stripped:
                for item in stripped.split(","):
                    _add(item.strip())
                continue
            _add(stripped)

        return skills

    def _parse_education(self, lines: list[str]) -> list[EducationEntry]:
        lines = [l.strip() for l in lines if l.strip()]
        if not lines:
            return []

        tabular = self._parse_tabular_education(lines)
        if tabular:
            return tabular

        groups: list[list[str]] = []
        current: list[str] = []

        for line in lines:
            starts_new = False
            if current:
                _, dr = extract_date_range(line)
                has_degree = bool(_DEGREE_RE.search(line))
                lower = line.lower()
                is_institution = any(w in lower for w in _EDU_INSTITUTION_WORDS)
                gpa_only = bool(_GPA_RE.search(line) or _GPA_TRAILING_RE.search(line)) and not has_degree and not is_institution

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
                last_has_gpa = bool(
                    _GPA_RE.search(last_line)
                    or _GPA_TRAILING_RE.search(last_line)
                    or re.match(r"^[0-9]+(?:\.[0-9]+)?\s*%\s*$", last_line.strip())
                    or re.search(r"[0-9]+(?:\.[0-9]+)?\s*%$", last_line.strip())
                )
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

    # Regex to detect table header rows (not actual data)
    _EDU_TABLE_HEADER_RE = re.compile(
        r"^(?:degree(?:/certificate)?|qualification|programme|course)\b.*\b(?:institute|institution|university|board|college|school)\b",
        re.IGNORECASE,
    )
    # Regex to detect Arzoo-style crushed text rows: date + degree + institution + gpa all on one line
    _CRUSHED_EDU_ROW_RE = re.compile(
        r"(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}|\d{4})\s*[-–]\s*(?P<end>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}|\d{4}|Present)\s+"
        r"(?P<degree>(?:B\.?Tech|M\.?Tech|B\.?Sc|M\.?Sc|B\.?E|M\.?E|B\.?Com|M\.?Com|MBA|BCA|MCA|Bachelor|Master|Ph\.?D|Secondary|Senior\s*Secondary|High\s*School|Diploma|Intermediate|12th|10th|SSC|HSC|CBSE|ICSE)[\w\s./()-]*)\s+"
        r"(?P<institution>[A-Z][^0-9]{4,80}?)\s+"
        r"(?P<gpa>[0-9]+(?:\.[0-9]+)?(?:\s*/\s*[0-9]+(?:\.[0-9]+)?)?%?)",
        re.IGNORECASE,
    )

    def _parse_tabular_education(self, lines: list[str]) -> list[EducationEntry]:
        # --- Path A: Pratik / standard "Degree/Certificate | Institute | GPA | Year" table ---
        has_std_header = any(
            self._EDU_TABLE_HEADER_RE.match(line.strip()) for line in lines
        )
        if has_std_header:
            body = [line for line in lines if not self._EDU_TABLE_HEADER_RE.match(line.strip())]
            # Strip bracket-style rows [gpa] [year]
            bracket_re = re.compile(r"^(?P<degree>.+?)\s+(?P<institution>.+?)\s+\[(?P<gpa>[^\]]+)\]\s+\[(?P<end>[^\]]+)\]$")
            entries: list[EducationEntry] = []
            merged: list[str] = []
            for line in body:
                stripped = line.strip()
                if not stripped:
                    continue
                if merged and "[" not in stripped and not extract_date_range(stripped)[1]:
                    merged[-1] = f"{merged[-1]} {stripped}"
                else:
                    merged.append(stripped)
            for row in merged:
                m = bracket_re.match(row)
                if m:
                    entries.append(EducationEntry(
                        institution=m.group("institution").strip(),
                        degree=m.group("degree").strip(),
                        field_of_study=None,
                        date_range=DateRange(start=None, end=m.group("end").strip(), is_current=False),
                        gpa=m.group("gpa").strip(),
                    ))
                    continue
                # Try inline date-range parse
                remaining, dr = extract_date_range(row)
                gpa_m = _GPA_RE.search(remaining)
                gpa = gpa_m.group(2).strip() if gpa_m else None
                text = _GPA_RE.sub("", remaining).strip(" ,-") if gpa_m else remaining.strip()
                if not text:
                    continue
                has_deg = bool(_DEGREE_RE.search(text))
                m_in = re.search(r"\bin\s+(.+)$", text, re.IGNORECASE) if has_deg else None
                if m_in:
                    deg = text[:m_in.start()].strip() or None
                    fos = m_in.group(1).strip()
                else:
                    deg = text.strip() if has_deg else None
                    fos = None
                inst_part = None if has_deg else text.strip()
                if inst_part or deg:
                    entries.append(EducationEntry(
                        institution=inst_part,
                        degree=deg,
                        field_of_study=fos,
                        date_range=dr,
                        gpa=gpa,
                    ))
            return entries if entries else []

        # --- Path B: Arzoo-style crushed-text rows (no brackets, date at start of row) ---
        crushed_entries: list[EducationEntry] = []
        for line in lines:
            m = self._CRUSHED_EDU_ROW_RE.match(line.strip())
            if not m:
                continue
            start_raw = m.group("start").strip()
            end_raw = m.group("end").strip()
            is_current = end_raw.lower() == "present"
            deg_raw = m.group("degree").strip()
            # Insert spaces in camelCase-crushed text (e.g. "B.TechinComputerScience" → "B.Tech in Computer Science")
            def _insert_spaces(s: str) -> str:
                # Insert between lowercase→uppercase transitions: "GraphicEra" → "Graphic Era"
                s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
                # Insert before known keywords: "inComputerScience" → "in Computer Science"
                s = re.sub(r"\bin\b", " in ", s)
                return re.sub(r"\s+", " ", s).strip()
            # Extract field-of-study from degree like "B.TechinComputerScience"
            fos_m = re.search(r"in\s*(.+)$", deg_raw, re.IGNORECASE)
            if fos_m:
                deg = _insert_spaces(deg_raw[:fos_m.start()].strip()) or None
                fos = _insert_spaces(fos_m.group(1).strip())
            else:
                deg = _insert_spaces(deg_raw) or None
                fos = None
            inst = _insert_spaces(m.group("institution").strip().strip(",- "))
            gpa = m.group("gpa").strip()
            crushed_entries.append(EducationEntry(
                institution=inst or None,
                degree=deg,
                field_of_study=fos or None,
                date_range=DateRange(start=start_raw, end=end_raw, is_current=is_current),
                gpa=gpa or None,
            ))
        if crushed_entries:
            return crushed_entries

        return []

    _EDU_SKIP_PREFIXES = re.compile(
        r"^(?:Thesis|Dissertation|Research|Topic|Project|Specialization|Minor|Focus|"
        r"Concentration|Advisor|Supervisor|Committee|Note|Award|Honours?|Cum\s+Laude)"
        r"\s*[:\-–]",
        re.IGNORECASE,
    )

    def _split_pipe_edu_line(self, line: str) -> Optional[EducationEntry]:
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 3:
            return None
        from .date_extractor import extract_date_range as _edr
        institution = None
        degree = None
        field_of_study = None
        date_range = None
        gpa = None
        leftover: list[str] = []

        for part in parts:
            remaining, dr = _edr(part)
            if dr and not date_range:
                date_range = dr
                continue
            gpa_m = _GPA_RE.search(part) or _GPA_TRAILING_RE.search(part)
            if gpa_m:
                gpa = gpa_m.group(2).strip() if gpa_m.re is _GPA_RE else gpa_m.group(1).strip()
                continue
            clean = (remaining or part).strip()
            if not clean:
                continue
            if _DEGREE_RE.search(clean):
                m_in = re.search(r"\bin\s+(.+)$", clean, re.IGNORECASE)
                if m_in:
                    degree = clean[:m_in.start()].strip() or None
                    field_of_study = m_in.group(1).strip()
                else:
                    if not degree:
                        degree = clean
                    elif not field_of_study:
                        field_of_study = clean
            elif any(w in clean.lower() for w in _EDU_INSTITUTION_WORDS):
                if not institution:
                    institution = clean
            else:
                leftover.append(clean)

        for item in leftover:
            if not field_of_study and degree and len(item.split()) >= 2:
                field_of_study = item
            elif not degree:
                degree = item
            elif not institution:
                institution = item

        if (institution or degree) and (date_range or gpa):
            return EducationEntry(
                institution=institution, degree=degree,
                field_of_study=field_of_study,
                date_range=date_range, gpa=gpa,
            )
        return None

    def _parse_edu_group(self, lines: list[str]) -> Optional[EducationEntry]:
        institution: Optional[str] = None
        degree: Optional[str] = None
        field_of_study: Optional[str] = None
        date_range = None
        gpa: Optional[str] = None

        for line in lines:
            if self._EDU_SKIP_PREFIXES.match(line.strip()):
                continue
            if "|" in line.strip() and line.strip().count("|") >= 2:
                result = self._split_pipe_edu_line(line.strip())
                if result and (result.institution or result.degree):
                    return result

            remaining, dr = extract_date_range(line)
            if dr and not date_range:
                date_range = dr
            line = remaining.strip() if remaining.strip() else line

            gpa_m = _GPA_RE.search(line)
            trailing_gpa_m = _GPA_TRAILING_RE.search(line)
            if gpa_m:
                gpa = gpa_m.group(2).strip()
                line = _GPA_RE.sub("", line).strip(" ,-")
            elif trailing_gpa_m:
                gpa = trailing_gpa_m.group(1).strip()
                line = _GPA_TRAILING_RE.sub("", line).strip(" ,-")
            elif re.match(r"^[0-9]+(?:\.[0-9]+)?\s*%\s*$", line.strip()):
                gpa = line.strip()
                line = ""
            elif re.match(r"^[0-9]+(?:\.[0-9]+)?\s*/\s*100\s*$", line.strip()):
                gpa = line.strip()
                line = ""
            elif not gpa:
                plain_gpa = re.search(r"\b([0-9]\.[0-9]{1,2}|10(?:\.0)?)\s*$", line.strip())
                if plain_gpa and _DEGREE_RE.search(line):
                    gpa = plain_gpa.group(1)
                    line = line[:plain_gpa.start()].strip(" ,-")

            if not line:
                continue

            if not institution and _DEGREE_RE.search(line) and self._is_institution_name(line):
                degree_match = _DEGREE_RE.search(line)
                if degree_match:
                    institution_prefix = line[:degree_match.start()].strip(" ,-")
                    degree_part = line[degree_match.start():].strip(" ,-")
                    if institution_prefix:
                        institution = institution_prefix
                        line = degree_part

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
            elif institution and self._looks_like_location(line):
                continue
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

    _AT_RE = re.compile(r"^(.+?)\s+at\s+(.+)$", re.IGNORECASE)
    _IN_RE = re.compile(r"^(.+?)\s+in\s+(.+)$", re.IGNORECASE)

    def _parse_pipe_entry(self, line: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        parts = [p.strip() for p in re.split(r"\s*\|\s*", line) if p.strip()]
        if len(parts) < 2:
            return None, None, None

        company: Optional[str] = None
        title: Optional[str] = None
        location: Optional[str] = None

        non_loc_parts: list[str] = []
        for part in parts:
            _, dr = extract_date_range(part)
            if dr:
                continue
            if self._looks_like_location(part):
                location = part
            else:
                non_loc_parts.append(part)

        if len(non_loc_parts) >= 2:
            if self._looks_like_title(non_loc_parts[0]):
                title, company = non_loc_parts[0], non_loc_parts[1]
            else:
                company, title = non_loc_parts[0], non_loc_parts[1]
        elif len(non_loc_parts) == 1:
            if self._looks_like_title(non_loc_parts[0]):
                title = non_loc_parts[0]
            else:
                company = non_loc_parts[0]

        return company, title, location

    def _parse_at_entry(self, line: str) -> tuple[Optional[str], Optional[str]]:
        m = self._AT_RE.match(line)
        if m:
            return m.group(2).strip(), m.group(1).strip()
        return None, None

    _STANDALONE_LOCATIONS = frozenset({
        "india", "usa", "uk", "us", "bangalore", "bengaluru", "mumbai",
        "delhi", "new delhi", "hyderabad", "pune", "chennai", "kolkata",
        "noida", "gurgaon", "gurugram", "remote", "london", "singapore",
        "dubai", "united states", "united kingdom", "canada", "australia",
        "germany", "france", "netherlands", "japan", "china",
        "bhopal", "indore", "jaipur", "lucknow", "ahmedabad", "surat",
        "vadodara", "nagpur", "patna", "ranchi", "bhubaneswar", "kochi",
        "thiruvananthapuram", "coimbatore", "visakhapatnam", "vizag",
        "chandigarh", "dehradun", "amritsar", "jalandhar",
        "mangalore", "mangaluru", "mysore", "mysuru", "thane",
        "ghaziabad", "meerut", "agra", "varanasi", "allahabad",
        "prayagraj", "jodhpur", "udaipur", "kota", "ajmer",
        "vellore", "madurai", "trichy", "salem", "erode",
        "tirunelveli", "tiruchirappalli", "vijayawada", "guntur",
        "warangal", "karimnagar", "belgaum", "hubli", "dharwad",
        "bellary", "shimoga", "tumkur", "udupi", "manipal",
        "calicut", "kozhikode", "thrissur", "palakkad", "kollam",
        "navi mumbai", "thane", "pune", "nashik", "aurangabad",
        "kolhapur", "solapur", "amravati", "nagpur",
        "raipur", "bilaspur", "bhilai", "guwahati", "shillong",
        "imphal", "aizawl", "agartala", "itanagar", "kohima",
        "jammu", "srinagar", "leh", "shimla", "dharamsala",
        "rishikesh", "haridwar", "nainital", "mussoorie",
        "bhilai", "durg", "korba", "bilaspur", "jagdalpur",
        "new york", "san francisco", "seattle", "austin", "boston",
        "chicago", "los angeles", "berlin", "toronto", "sydney",
        "amsterdam", "zurich", "paris", "hong kong", "bangalore",
    })
    _ORG_SUFFIXES = re.compile(
        r"\b(?:technologies|solutions|systems|services|labs|ltd|limited|"
        r"inc|corp|corporation|company|enterprises|group|global|"
        r"international|pvt|private|consulting|ventures|software|"
        r"tech|digital|research|analytics|networks|studios|works)\b",
        re.IGNORECASE,
    )

    _INSTITUTION_WORDS = frozenset({
        "university", "institute", "college", "school", "academy",
        "iit", "nit", "bits", "iisc", "iim", "nift", "iiit",
        "polytechnic", "faculty", "department",
        "of technology", "of science", "of engineering",
        "of management", "of arts",
    })

    def _is_institution_name(self, text: str) -> bool:
        lower = text.lower()
        return any(w in lower for w in self._INSTITUTION_WORDS)

    def _looks_like_location(self, text: str) -> bool:
        stripped = text.strip()
        words = stripped.split()
        if len(words) > 4 or len(words) == 0:
            return False

        if self._ORG_SUFFIXES.search(stripped):
            return False

        lower = stripped.lower()

        if lower in self._STANDALONE_LOCATIONS:
            return True

        if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?,\s*(?:[A-Z]{2,3}|[A-Z][a-z]+)", stripped):
            return True

        if len(words) == 1 and lower in self._STANDALONE_LOCATIONS:
            return True

        return False

    def _parse_experience(self, lines: list[str]) -> list[ExperienceEntry]:
        if not lines:
            return []

        lines = [line for line in lines if not self._is_experience_noise_line(line)]
        lines = self._merge_wrapped_lines(lines, self._looks_like_experience_header)
        entries: list[ExperienceEntry] = []

        for header_lines, bullets in self._bundle_experience_lines(lines):
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

            if len(cleaned_headers) == 1:
                only = cleaned_headers[0]

                if "|" in only:
                    company, title, location = self._parse_pipe_entry(only)
                elif " at " in only.lower():
                    company, title = self._parse_at_entry(only)
                elif self._looks_like_title(only):
                    title = only
                else:
                    company = only

            elif len(cleaned_headers) >= 2:
                first = cleaned_headers[0]
                second = cleaned_headers[1]

                if "|" in first:
                    company, title, location = self._parse_pipe_entry(first)
                    if len(cleaned_headers) >= 2 and not location:
                        if self._looks_like_location(second):
                            location = second
                elif " at " in first.lower():
                    company, title = self._parse_at_entry(first)
                elif self._looks_like_title(first) and not self._looks_like_title(second):
                    title, company = first, second
                elif self._looks_like_title(second) and not self._looks_like_title(first):
                    company, title = first, second
                else:
                    if ner_available():
                        ner_orgs = extract_orgs_from_section([first, second])
                        if ner_orgs:
                            first_is_org = any(
                                org.lower() in first.lower() for org in ner_orgs
                            )
                            second_is_org = any(
                                org.lower() in second.lower() for org in ner_orgs
                            )
                            if first_is_org and not second_is_org:
                                company, title = first, second
                            elif second_is_org and not first_is_org:
                                company, title = second, first
                            else:
                                company, title = first, second
                        else:
                            company, title = first, second
                    else:
                        company, title = first, second

                if not location and len(cleaned_headers) >= 3:
                    candidate = cleaned_headers[2]
                    if self._looks_like_location(candidate):
                        location = candidate

            if company and "," in company and not location:
                parts = [p.strip() for p in company.split(",", 1)]
                if (
                    len(parts) == 2
                    and len(parts[1]) <= 35
                    and not _COMPANY_SUFFIX_RE.match(parts[1].strip())
                    and self._looks_like_location(parts[1])
                    and not self._is_institution_name(parts[0])
                ):
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

    def _bundle_experience_lines(self, lines: list[str]) -> list[tuple[list[str], list[str]]]:
        bundles: list[tuple[list[str], list[str]]] = []
        header_lines: list[str] = []
        bullets: list[str] = []

        def flush() -> None:
            nonlocal header_lines, bullets
            if header_lines or bullets:
                bundles.append((header_lines[:], bullets[:]))
            header_lines = []
            bullets = []

        for raw in lines:
            stripped = raw.strip()
            if not stripped:
                continue
            if self._is_bullet_line(stripped):
                bullets.append(self._strip_bullet(stripped))
                continue

            has_existing_structure = bool(bullets) or len(header_lines) >= 2 or any(
                "|" in line or " at " in line.lower() for line in header_lines
            )
            is_date_only = bool(extract_date_range(stripped)[1] and not extract_date_range(stripped)[0].strip())
            if header_lines and has_existing_structure and self._looks_like_experience_header(stripped) and not is_date_only:
                flush()
            header_lines.append(stripped)

        flush()
        return [(headers, bullet_lines) for headers, bullet_lines in bundles if headers]

    def _parse_projects(self, lines: list[str]) -> list[ProjectEntry]:
        return self._projects_parser.parse(lines)

    def _parse_certifications(self, lines: list[str]) -> list:
        from ..models.resume import CertificationEntry

        entries: list[CertificationEntry] = []
        seen: set[str] = set()

        _CERT_YEAR_PAREN = re.compile(r"\((\d{4})\)\s*$")
        _CERT_YEAR_END   = re.compile(r",?\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?\b(\d{4})\s*$", re.IGNORECASE)
        _DASH_ISSUER_RE  = re.compile(r"\s+[-–—|]\s+([^(]+?)(?:\s*[|(]\s*(\d{4})\s*[|)]?)?\s*$")
        _BY_ISSUER_RE    = re.compile(r"\b(?:by|from|issued\s+by|provider:|certified\s+by)\s+(.+?)(?:\s*[,(]\s*(\d{4})\s*[,)])?\s*$", re.IGNORECASE)
        _PAREN_ISSUER_RE = re.compile(r"\(([^()]+?)(?:,\s*(\d{4}))?\)\s*$")

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_bullet_line(stripped):
                stripped = self._strip_bullet(stripped)

            date: Optional[str] = None
            issuer: Optional[str] = None
            name_part = stripped

            m = _CERT_YEAR_PAREN.search(name_part)
            if m:
                date = m.group(1)
                name_part = name_part[:m.start()].strip().rstrip("(- ,")

            m = _PAREN_ISSUER_RE.search(name_part)
            if m:
                content = m.group(1).strip()
                if m.group(2):
                    issuer = content
                    if not date:
                        date = m.group(2)
                elif any(c.isalpha() for c in content) and not content.isdigit():
                    issuer = content
                name_part = name_part[:m.start()].strip().rstrip("- ,")

            if not issuer:
                m = _BY_ISSUER_RE.search(name_part)
                if m:
                    issuer = m.group(1).strip().rstrip(", ")
                    if m.group(2) and not date:
                        date = m.group(2)
                    name_part = name_part[:m.start()].strip().rstrip("- ,")

            _TRAILING_DATE_RE = re.compile(
                r",?\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                r"[a-z]*\.?\s+)?\b(\d{4})\s*$",
                re.IGNORECASE,
            )
            if not issuer:
                m = _DASH_ISSUER_RE.search(name_part)
                if m:
                    candidate = m.group(1).strip()
                    tdm = _TRAILING_DATE_RE.search(candidate)
                    if tdm:
                        if not date:
                            date = tdm.group(2)
                        candidate = candidate[:tdm.start()].strip().rstrip(",")
                    if candidate and len(candidate) <= 60 and not candidate.isdigit():
                        issuer = candidate
                        if m.group(2) and not date:
                            date = m.group(2)
                        name_part = name_part[:m.start()].strip().rstrip("- ,")

            if not date:
                m = _CERT_YEAR_END.search(name_part)
                if m:
                    date = m.group(2)
                    name_part = name_part[:m.start()].strip().rstrip(",- ")

            name_part = name_part.strip()
            if not name_part:
                continue
            key = name_part.lower()
            if key in seen:
                continue
            seen.add(key)
            entries.append(CertificationEntry(name=name_part, issuer=issuer, date=date))

        return entries

    _AWARD_LIKE_RE = re.compile(
        r"(?:award|prize|scholarship|fellowship|winner|rank|honor|honours?|"
        r"merit|achievement|recognition|certificate|distinction|gsoc|jee|"
        r"hackathon|olympiad|finalist|selected|recipient|1st|2nd|3rd|"
        r"top\s+\d|air\s+\d|percentile)",
        re.IGNORECASE,
    )

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
                is_award_like = self._AWARD_LIKE_RE.search(stripped)
                has_year_suffix = bool(re.search(r",\s*(?:Fall|Spring|Winter|Summer)?\s*\d{4}\s*$", stripped, re.IGNORECASE))
                has_dash_content = " - " in stripped or " – " in stripped
                if is_award_like or (has_year_suffix and has_dash_content):
                    item = stripped
                else:
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
        stripped = text.strip()
        if not stripped:
            return False
        if stripped[:1].islower() and len(stripped.split()) > 4:
            return False
        if stripped.endswith(".") and len(stripped.split()) > 4:
            return False
        lowered = text.lower()
        return any(
            re.search(r"\b" + re.escape(token) + r"\b", lowered)
            for token in _JOB_TITLE_WORDS
        )

    def _looks_like_experience_header(self, line: str) -> bool:
        stripped = line.strip()
        if self._is_bullet_line(stripped):
            return False
        if self._is_experience_noise_line(stripped):
            return False
        cleaned, date_range = extract_date_range(stripped)
        if self._is_institution_name(cleaned) and not date_range and not self._looks_like_title(cleaned):
            return False
        if date_range or self._looks_like_title(cleaned):
            return True
        if "|" in cleaned or " at " in cleaned.lower():
            return True
        if self._ORG_SUFFIXES.search(cleaned):
            return True
        _SUFFIX_DOT = re.compile(
            r"\b(?:Ltd|Inc|Corp|Co|LLC|LLP|Pvt|PVT|Plc|Llp)\.$", re.IGNORECASE
        )
        effective = _SUFFIX_DOT.sub("", cleaned).rstrip()
        return bool(
            effective[:1].isupper()
            and 1 <= len(cleaned.split()) <= 6
            and len(cleaned) <= 60
            and (not cleaned.endswith(".") or _SUFFIX_DOT.search(cleaned))
            and not self._looks_like_location(cleaned)
            and ":" not in cleaned
        )

    def _is_experience_noise_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return True
        if match_section_heading(stripped):
            return True
        if _EMAIL_RE.search(stripped) or _PHONE_RE.search(stripped) or _URL_RE.search(stripped):
            return True
        if _CONTACT_SIGNAL_RE.search(stripped):
            return True
        if re.search(r"\b(?:cgpa|gpa|score|marks|certifications?|courses?|skills?|strength|weakness)\b", stripped, re.IGNORECASE):
            return True
        return False

    # Action-verb sentence patterns that look like description, not project name
    _ACTION_VERB_START_RE = re.compile(
        r"^(?:Developed|Built|Created|Designed|Implemented|Led|Managed|Improved|Optimized|"
        r"Integrated|Automated|Deployed|Architected|Conceptualized|Guided\s+by|Supervised\s+by|"
        r"Mentored\s+by|Advised\s+by|See|Visit|Click|"
        r"Worked|Used|Applied|Collaborated|Conducted|Analyzed|Supported|Researched|Achieved|"
        r"Streamlined|Engineered|Resolved|Participated|Awarded|Completed)\b",
        re.IGNORECASE,
    )

    def _looks_like_project_header(self, line: str) -> bool:
        stripped = line.strip()
        if self._is_bullet_line(stripped):
            return False
        cleaned, date_range = extract_date_range(stripped)
        if date_range and not cleaned.strip():
            return False
        if date_range:
            # Even with a date, reject if it looks like a description sentence
            if self._ACTION_VERB_START_RE.match(cleaned.strip()):
                return False
            return True
        words = cleaned.split()
        # Stricter: project names are generally <=6 words and don't end in period
        if len(words) > 6:
            return False
        # Reject sentences that start with action verbs (they are description lines)
        if self._ACTION_VERB_START_RE.match(cleaned):
            return False
        return bool(
            cleaned[:1].isupper()
            and len(cleaned) <= 75
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
            previous = merged[-1]
            previous_cleaned, previous_date_range = extract_date_range(previous)
            if self._is_bullet_line(line) or is_new_header(line):
                merged.append(line)
            elif (
                previous_date_range
                and line[:1].isupper()
                and not self._is_bullet_line(line)
            ):
                merged.append(line)
            elif (
                self._is_institution_name(line)
                and self._looks_like_title(previous_cleaned.strip() or previous)
            ):
                merged.append(line)
            elif self._is_bullet_line(merged[-1]) or any(
                merged[-1].lstrip().startswith(ch) for ch in _BULLET_CHARS
            ):
                merged[-1] = f"{merged[-1]} {line}".strip()
            elif line[:1].islower() and not is_new_header(merged[-1]):
                merged[-1] = f"{merged[-1]} {line}".strip()
            else:
                merged[-1] = f"{merged[-1]} {line}".strip()
        return merged
