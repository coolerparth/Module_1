from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from ..models.resume import EducationEntry, ExperienceEntry, LinkItem, ProjectEntry, ResumeProfile
from .gpa_normalizer import normalize_gpa
from .skills_normalizer import normalize_skill

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.+\-]*@[A-Za-z0-9][A-Za-z0-9\-]*"
    r"(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$"
)
_DIGIT_RE = re.compile(r"\d")
_NAME_CHARS_RE = re.compile(r"[^A-Za-z\s\-'.]")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_ACTION_VERBS = frozenset({
    "achieved", "architected", "automated", "built", "collaborated", "conducted",
    "created", "designed", "developed", "engineered", "evaluated", "executed",
    "implemented", "improved", "increased", "integrated", "launched", "led",
    "maintained", "managed", "optimized", "published", "reduced", "researched",
    "resolved", "scaled", "shipped", "streamlined", "supported", "tested",
    "trained", "transformed",
})
_KNOWN_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "icloud.com", "protonmail.com", "proton.me", "live.com", "rediffmail.com",
})
_SUSPICIOUS_SKILL_PREFIXES = (
    "awarded", "completed", "participated", "actively", "conceptualized",
    "playing", "exploring", "affiliated", "achieving", "and ",
)
_SUSPICIOUS_SKILL_WORDS = frozenset({
    "deep", "machine", "demonstrating", "engineered", "conceptualized",
    "participated", "completed", "awarded", "actively",
})


@dataclass
class ValidationNode:
    path: str
    data: Any | None = None
    note: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "data": self.data,
            "note": self.note,
            "error": self.error,
        }


@dataclass
class ValidationSummary:
    total_checks: int
    validated_count: int
    invalid_count: int
    grey_area_count: int
    pass_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_checks": self.total_checks,
            "validated_count": self.validated_count,
            "invalid_count": self.invalid_count,
            "grey_area_count": self.grey_area_count,
            "pass_rate": self.pass_rate,
        }


@dataclass
class ATSScore:
    total: int
    grade: str
    breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    max_score: int = 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "ats_score": self.total,
            "ats_grade": self.grade,
            "max_score": self.max_score,
            "breakdown": self.breakdown,
        }


@dataclass
class ResumeValidationReport:
    summary: ValidationSummary
    validated_sections: dict[str, ValidationNode]
    invalid_sections: dict[str, ValidationNode]
    grey_area: dict[str, ValidationNode]
    ats: ATSScore

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "validated_sections": {
                key: value.to_dict() for key, value in self.validated_sections.items()
            },
            "invalid_sections": {
                key: value.to_dict() for key, value in self.invalid_sections.items()
            },
            "grey_area": {
                key: value.to_dict() for key, value in self.grey_area.items()
            },
            "ats": self.ats.to_dict(),
        }


class ResumeValidator:
    def validate(self, profile: ResumeProfile) -> ResumeValidationReport:
        validated: dict[str, ValidationNode] = {}
        invalid: dict[str, ValidationNode] = {}
        grey: dict[str, ValidationNode] = {}
        section_stats: dict[str, dict[str, int]] = {}

        def record(
            bucket: str,
            path: str,
            data: Any,
            message: str,
            section: str,
        ) -> None:
            stats = section_stats.setdefault(section, {"valid": 0, "grey": 0, "invalid": 0})
            if bucket == "valid":
                validated[path] = ValidationNode(path=path, data=data, note=message)
                stats["valid"] += 1
            elif bucket == "grey":
                grey[path] = ValidationNode(path=path, data=data, note=message)
                stats["grey"] += 1
            else:
                invalid[path] = ValidationNode(path=path, data=data, error=message)
                stats["invalid"] += 1

        self._validate_personal_info(profile, record)
        self._validate_links(profile.links, record)
        self._validate_skills(profile.skills, record)
        self._validate_experience(profile.experience, record)
        self._validate_education(profile.education, record)
        self._validate_projects(profile.projects, record)
        self._validate_simple_list(profile.awards, "awards", record)
        self._validate_simple_list(profile.interests, "interests", record)

        total_checks = len(validated) + len(invalid) + len(grey)
        summary = ValidationSummary(
            total_checks=total_checks,
            validated_count=len(validated),
            invalid_count=len(invalid),
            grey_area_count=len(grey),
            pass_rate=round((len(validated) / total_checks) * 100, 1) if total_checks else 0.0,
        )
        ats = self._compute_ats(section_stats)
        return ResumeValidationReport(
            summary=summary,
            validated_sections=validated,
            invalid_sections=invalid,
            grey_area=grey,
            ats=ats,
        )

    def _validate_personal_info(self, profile: ResumeProfile, record) -> None:
        info = profile.personal_info

        if not info.name or not info.name.strip():
            record("invalid", "personal_info.name", info.name, "Name is missing.", "contact")
        else:
            name = info.name.strip()
            words = name.split()
            if _DIGIT_RE.search(name):
                record("invalid", "personal_info.name", name, "Name contains digits.", "contact")
            elif _NAME_CHARS_RE.search(name):
                record("grey", "personal_info.name", name, "Name contains unusual characters; verify manually.", "contact")
            elif len(words) < 2:
                record("grey", "personal_info.name", name, "Single-word name detected; full name is preferred.", "contact")
            else:
                record("valid", "personal_info.name", name, "Name looks valid.", "contact")

        if not info.email:
            record("invalid", "personal_info.email", info.email, "Email is missing.", "contact")
        elif not _EMAIL_RE.match(info.email):
            record("invalid", "personal_info.email", info.email, "Email format is invalid.", "contact")
        else:
            domain = info.email.split("@", 1)[1].lower()
            suggestion = None if domain in _KNOWN_EMAIL_DOMAINS else self._suggest_domain(domain)
            if suggestion:
                record("grey", "personal_info.email", info.email, f"Email domain may be a typo; did you mean '{suggestion}'?", "contact")
            else:
                record("valid", "personal_info.email", info.email, "Email looks valid.", "contact")

        if not info.phone:
            record("invalid", "personal_info.phone", info.phone, "Phone number is missing.", "contact")
        else:
            digits = re.sub(r"\D", "", info.phone)
            if len(digits) < 10 or len(digits) > 15:
                record("invalid", "personal_info.phone", info.phone, "Phone number has an invalid digit count.", "contact")
            else:
                record("valid", "personal_info.phone", info.phone, "Phone number looks structurally valid.", "contact")

        if info.location:
            if len(info.location.split()) >= 2:
                record("valid", "personal_info.location", info.location, "Location detected.", "contact")
            else:
                record("grey", "personal_info.location", info.location, "Location is unusually short.", "contact")
        else:
            record("grey", "personal_info.location", info.location, "Location is missing.", "contact")

        if info.headline:
            if info.location and info.headline.strip().lower() == info.location.strip().lower():
                record("grey", "personal_info.headline", info.headline, "Headline duplicates location.", "contact")
            else:
                record("valid", "personal_info.headline", info.headline, "Headline present.", "contact")
        else:
            record("grey", "personal_info.headline", info.headline, "Headline is missing.", "contact")

    def _validate_links(self, links: list[LinkItem], record) -> None:
        if not links:
            record("grey", "links", None, "No professional links provided.", "contact")
            return

        seen: set[str] = set()
        for idx, link in enumerate(links):
            path = f"links[{idx}]"
            url = (link.url or "").strip()
            label = (link.label or "").strip() or "Link"
            if not url:
                record("invalid", f"{path}.url", url, f"{label} URL is empty.", "contact")
                continue

            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                record("invalid", f"{path}.url", url, f"{label} URL is malformed.", "contact")
                continue

            normalized = url.rstrip("/").lower()
            if normalized in seen:
                record("grey", f"{path}.url", url, f"{label} duplicates another link.", "contact")
                continue
            seen.add(normalized)

            domain = parsed.netloc.lower()
            if label.lower() == "linkedin" and "linkedin.com" not in domain:
                record("invalid", f"{path}.url", url, "LinkedIn label does not point to linkedin.com.", "contact")
            elif label.lower() == "github" and "github.com" not in domain:
                record("invalid", f"{path}.url", url, "GitHub label does not point to github.com.", "contact")
            else:
                record("valid", f"{path}.url", url, f"{label} URL looks valid.", "contact")

    def _validate_skills(self, skills: list[str], record) -> None:
        if not skills:
            record("invalid", "skills", None, "Skills section is missing or empty.", "skills")
            return

        seen: set[str] = set()
        clean_count = 0
        for idx, skill in enumerate(skills):
            text = (skill or "").strip()
            path = f"skills[{idx}]"
            if not text:
                record("grey", path, skill, "Empty skill entry.", "skills")
                continue

            key = text.lower()
            if key in seen:
                record("grey", path, text, "Duplicate skill.", "skills")
                continue
            seen.add(key)

            normalized = normalize_skill(text)
            if (
                len(text) > 45
                or text.endswith(".")
                or text.lower().startswith(_SUSPICIOUS_SKILL_PREFIXES)
                or len(text.split()) > 5
                or text.lower() in _ACTION_VERBS
                or text.lower() in _SUSPICIOUS_SKILL_WORDS
                or text.lower().startswith("machine (")
                or (
                    normalized.category.value == "Other"
                    and len(text.split()) == 1
                    and not re.fullmatch(r"[A-Z0-9+#./-]{2,12}", text)
                )
            ):
                record("grey", path, text, "This skill looks noisy or sentence-like.", "skills")
            else:
                record("valid", path, text, "Skill looks usable.", "skills")
                clean_count += 1

        if clean_count < 3:
            record("grey", "skills.summary", clean_count, "Very few clean skills were found.", "skills")

    def _validate_experience(self, experience: list[ExperienceEntry], record) -> None:
        if not experience:
            record("grey", "experience", None, "No experience entries found.", "experience")
            return

        ranges: list[tuple[int, int, int]] = []
        for idx, entry in enumerate(experience):
            base = f"experience[{idx}]"

            if not entry.company:
                record("invalid", f"{base}.company", entry.company, "Company is missing.", "experience")
            elif self._looks_like_sentence(entry.company):
                record("grey", f"{base}.company", entry.company, "Company looks sentence-like; verify extraction.", "experience")
            else:
                record("valid", f"{base}.company", entry.company, "Company looks valid.", "experience")

            if not entry.title:
                record("grey", f"{base}.title", entry.title, "Job title is missing.", "experience")
            elif self._looks_like_sentence(entry.title):
                record("grey", f"{base}.title", entry.title, "Job title looks sentence-like; verify extraction.", "experience")
            else:
                record("valid", f"{base}.title", entry.title, "Job title looks valid.", "experience")

            self._record_date_range(entry.date_range.start if entry.date_range else None, entry.date_range.end if entry.date_range else None, entry.date_range.is_current if entry.date_range else False, f"{base}.date_range", "Experience timeline", "experience", record, ranges, idx)

            if not entry.bullets:
                record("grey", f"{base}.bullets", None, "No experience bullets provided.", "experience")
            else:
                for bullet_idx, bullet in enumerate(entry.bullets):
                    self._validate_bullet(bullet, f"{base}.bullets[{bullet_idx}]", "experience", record)

        for first, second, _ in self._overlapping_ranges(ranges):
            record("grey", f"experience[{first}].timeline_overlap", {"with": second}, f"Timeline overlaps with experience[{second}]; verify dates manually.", "experience")

    def _validate_education(self, education: list[EducationEntry], record) -> None:
        if not education:
            record("grey", "education", None, "No education entries found.", "education")
            return

        for idx, entry in enumerate(education):
            base = f"education[{idx}]"
            if entry.institution:
                record("valid", f"{base}.institution", entry.institution, "Institution present.", "education")
            else:
                record("invalid", f"{base}.institution", entry.institution, "Institution is missing.", "education")

            if entry.degree:
                record("valid", f"{base}.degree", entry.degree, "Degree present.", "education")
            else:
                record("grey", f"{base}.degree", entry.degree, "Degree is missing.", "education")

            self._record_date_range(entry.date_range.start if entry.date_range else None, entry.date_range.end if entry.date_range else None, entry.date_range.is_current if entry.date_range else False, f"{base}.date_range", "Education timeline", "education", record)

            if entry.gpa:
                normalized = normalize_gpa(entry.gpa)
                if normalized.is_valid:
                    record("valid", f"{base}.gpa", entry.gpa, f"GPA/grade parsed successfully ({normalized.display}).", "education")
                else:
                    record("grey", f"{base}.gpa", entry.gpa, "GPA/grade could not be normalized cleanly.", "education")
            else:
                record("grey", f"{base}.gpa", entry.gpa, "GPA/grade missing.", "education")

    def _validate_projects(self, projects: list[ProjectEntry], record) -> None:
        if not projects:
            record("grey", "projects", None, "No project entries found.", "projects")
            return

        for idx, entry in enumerate(projects):
            base = f"projects[{idx}]"
            if entry.name and not self._looks_like_sentence(entry.name):
                record("valid", f"{base}.name", entry.name, "Project name looks valid.", "projects")
            elif entry.name:
                record("grey", f"{base}.name", entry.name, "Project name looks sentence-like.", "projects")
            else:
                record("invalid", f"{base}.name", entry.name, "Project name is missing.", "projects")

            self._record_date_range(entry.date_range.start if entry.date_range else None, entry.date_range.end if entry.date_range else None, entry.date_range.is_current if entry.date_range else False, f"{base}.date_range", "Project timeline", "projects", record)

            if entry.url:
                parsed = urlparse(entry.url)
                if parsed.scheme in {"http", "https"} and parsed.netloc:
                    record("valid", f"{base}.url", entry.url, "Project URL looks valid.", "projects")
                else:
                    record("grey", f"{base}.url", entry.url, "Project URL is malformed.", "projects")
            else:
                record("grey", f"{base}.url", entry.url, "Project URL missing.", "projects")

            if entry.description:
                self._validate_bullet(entry.description, f"{base}.description", "projects", record)
            else:
                record("grey", f"{base}.description", entry.description, "Project description missing.", "projects")

            if entry.technologies:
                record("valid", f"{base}.technologies", entry.technologies, f"{len(entry.technologies)} technologies listed.", "projects")
            else:
                record("grey", f"{base}.technologies", entry.technologies, "No technologies listed.", "projects")

    def _validate_simple_list(self, values: list[str], section: str, record) -> None:
        if not values:
            record("grey", section, None, f"No {section} listed.", section)
            return

        seen: set[str] = set()
        for idx, value in enumerate(values):
            text = (value or "").strip()
            path = f"{section}[{idx}]"
            if not text:
                record("grey", path, value, f"Empty {section} entry.", section)
                continue
            key = text.lower()
            if key in seen:
                record("grey", path, text, f"Duplicate {section} entry.", section)
                continue
            seen.add(key)
            if len(text.split()) < 2:
                record("grey", path, text, f"{section.title()} entry is too short.", section)
            else:
                record("valid", path, text, f"{section.title()} entry looks usable.", section)

    def _validate_bullet(self, bullet: str, path: str, section: str, record) -> None:
        text = (bullet or "").strip()
        if not text:
            record("grey", path, bullet, "Bullet is empty.", section)
            return

        words = text.split()
        first = words[0].lower().strip(".,;:()") if words else ""
        has_action = first in _ACTION_VERBS
        has_number = bool(re.search(r"\d", text))

        if len(words) < 5:
            record("grey", path, text, "Bullet is too short.", section)
        elif has_action and has_number:
            record("valid", path, text, "Bullet has action + measurable detail.", section)
        elif has_action:
            record("valid", path, text, "Bullet starts with a strong action verb.", section)
        else:
            record("grey", path, text, "Bullet could be stronger with an action verb and metric.", section)

    def _record_date_range(self, start: str | None, end: str | None, is_current: bool, path: str, label: str, section: str, record, ranges: list[tuple[int, int, int]] | None = None, idx: int | None = None) -> None:
        if not start and not end:
            record("grey", path, None, f"{label} is missing.", section)
            return

        start_year = self._extract_year(start)
        end_year = None if is_current else self._extract_year(end)

        if start and start_year is None:
            record("grey", path, {"start": start, "end": end}, f"{label} start could not be parsed cleanly.", section)
            return
        if end and not is_current and end_year is None:
            record("grey", path, {"start": start, "end": end}, f"{label} end could not be parsed cleanly.", section)
            return
        if start_year is not None and end_year is not None and end_year < start_year:
            record("invalid", path, {"start": start, "end": end}, f"{label} has an impossible date order.", section)
            return

        if start_year is not None and end_year is not None and ranges is not None and idx is not None:
            ranges.append((start_year, end_year, idx))

        if start_year is not None and start_year > 2035:
            record("grey", path, {"start": start, "end": end}, f"{label} starts unusually far in the future.", section)
        else:
            record("valid", path, {"start": start, "end": end or ("Present" if is_current else None)}, f"{label} looks plausible.", section)

    def _extract_year(self, value: str | None) -> int | None:
        if not value:
            return None
        match = _YEAR_RE.search(value)
        return int(match.group(0)) if match else None

    def _looks_like_sentence(self, value: str) -> bool:
        stripped = value.strip()
        return stripped.endswith(".") or (stripped[:1].islower() and len(stripped.split()) > 4)

    def _suggest_domain(self, domain: str) -> str | None:
        matches = difflib.get_close_matches(domain, _KNOWN_EMAIL_DOMAINS, n=1, cutoff=0.82)
        return matches[0] if matches else None

    def _overlapping_ranges(self, ranges: list[tuple[int, int, int]]) -> list[tuple[int, int, tuple[int, int, int]]]:
        overlaps: list[tuple[int, int, tuple[int, int, int]]] = []
        for a in range(len(ranges)):
            s1, e1, i1 = ranges[a]
            for b in range(a + 1, len(ranges)):
                s2, e2, i2 = ranges[b]
                if s1 <= e2 and s2 <= e1:
                    overlaps.append((i1, i2, ranges[b]))
        return overlaps

    def _compute_ats(self, section_stats: dict[str, dict[str, int]]) -> ATSScore:
        weights = {
            "contact": 20,
            "skills": 20,
            "experience": 25,
            "projects": 20,
            "education": 15,
        }
        total = 0
        breakdown: dict[str, dict[str, Any]] = {}

        for section, weight in weights.items():
            stats = section_stats.get(section, {"valid": 0, "grey": 0, "invalid": 0})
            checks = stats["valid"] + stats["grey"] + stats["invalid"]
            ratio = ((stats["valid"] + stats["grey"] * 0.5) / checks) if checks else 0.0
            earned = round(ratio * weight)
            total += earned
            breakdown[section] = {
                "score": earned,
                "max": weight,
                "detail": f"{stats['valid']} valid, {stats['grey']} grey, {stats['invalid']} invalid",
            }

        total = max(0, min(100, total))
        return ATSScore(total=total, grade=self._grade_for_score(total), breakdown=breakdown)

    def _grade_for_score(self, score: int) -> str:
        if score >= 90:
            return "A+ (Excellent)"
        if score >= 80:
            return "A (Very Good)"
        if score >= 70:
            return "B+ (Good)"
        if score >= 60:
            return "B (Above Average)"
        if score >= 50:
            return "C (Average)"
        return "D (Needs Improvement)"
