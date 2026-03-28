from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional

from ..models.resume import EducationEntry, ExperienceEntry, ResumeProfile


class Severity(str, Enum):
    ERROR   = "error"                                           
    WARNING = "warning"                             
    INFO    = "info"                                 


@dataclass
class ValidationIssue:
    severity: Severity
    field: str
    message: str
    context: str = ""


@dataclass
class TimelineReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    total_years_experience: float = 0.0
    earliest_start: Optional[str] = None
    is_consistent: bool = True

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    def to_dict(self) -> dict:
        return {
            "is_consistent": self.is_consistent,
            "total_years_experience": self.total_years_experience,
            "earliest_start": self.earliest_start,
            "errors": [{"field": i.field, "message": i.message, "context": i.context}
                       for i in self.errors],
            "warnings": [{"field": i.field, "message": i.message, "context": i.context}
                         for i in self.warnings],
        }


                                                                               
_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

def _parse_date(text: str | None) -> Optional[date]:
    if not text:
        return None
    text = text.strip()
    m = re.match(r"([A-Za-z]{3,})\s+(\d{4})", text)
    if m:
        month = _MONTH_MAP.get(m.group(1)[:3].lower(), 1)
        return date(int(m.group(2)), month, 1)
    m = re.match(r"^(\d{4})$", text)
    if m:
        return date(int(m.group(1)), 6, 1)
    m = re.match(r"(\d{1,2})/(\d{4})", text)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)
    return None


class TimelineValidator:

    MIN_REASONABLE_YEAR = 1950
    MAX_REASONABLE_YEAR_OFFSET = 2                                                     
    MAX_SINGLE_TENURE_YEARS = 25
    MIN_WORKING_AGE_YEARS = 14
    MIN_GRAD_AGE_YEARS = 16

    def validate(self, profile: ResumeProfile) -> TimelineReport:
        report = TimelineReport()
        today = date.today()
        max_year = today.year + self.MAX_REASONABLE_YEAR_OFFSET

                                 
        exp_dates: list[tuple[date, Optional[date], str]] = []
        edu_dates: list[tuple[date, Optional[date], str]] = []

                                                                            
        for entry in profile.experience:
            dr = entry.date_range
            if not dr:
                continue

            label = f"{entry.company or ''} / {entry.title or ''}".strip(" /")
            start = _parse_date(dr.start)
            end   = _parse_date(dr.end) if not dr.is_current else today

            if start:
                if start.year < self.MIN_REASONABLE_YEAR:
                    report.issues.append(ValidationIssue(
                        Severity.ERROR, "experience",
                        f"Start year {start.year} is unrealistically early",
                        label,
                    ))
                if start.year > max_year:
                    report.issues.append(ValidationIssue(
                        Severity.ERROR, "experience",
                        f"Start year {start.year} is in the future",
                        label,
                    ))

            if end and not dr.is_current:
                if end.year > max_year:
                    report.issues.append(ValidationIssue(
                        Severity.ERROR, "experience",
                        f"End year {end.year} is in the future",
                        label,
                    ))

            if start and end and end < start:
                report.issues.append(ValidationIssue(
                    Severity.ERROR, "experience",
                    f"End date ({dr.end}) is before start date ({dr.start})",
                    label,
                ))

            if start and end and end >= start:
                tenure_years = (end - start).days / 365.25
                if tenure_years > self.MAX_SINGLE_TENURE_YEARS:
                    report.issues.append(ValidationIssue(
                        Severity.WARNING, "experience",
                        f"Tenure of {tenure_years:.0f} years seems unusually long",
                        label,
                    ))
                exp_dates.append((start, end, label))

                                                                            
        latest_edu_end: Optional[date] = None
        for entry in profile.education:
            dr = entry.date_range
            if not dr:
                continue

            label = f"{entry.institution or ''} / {entry.degree or ''}".strip(" /")
            start = _parse_date(dr.start)
            end   = _parse_date(dr.end)

            if start and start.year < self.MIN_REASONABLE_YEAR:
                report.issues.append(ValidationIssue(
                    Severity.ERROR, "education",
                    f"Start year {start.year} is unrealistically early",
                    label,
                ))

            if end and end.year > max_year:
                report.issues.append(ValidationIssue(
                    Severity.WARNING, "education",
                    f"Graduation year {end.year} is in the future",
                    label,
                ))

            if start and end and end < start:
                report.issues.append(ValidationIssue(
                    Severity.ERROR, "education",
                    f"Graduation ({dr.end}) is before enrollment ({dr.start})",
                    label,
                ))

            if end:
                if not latest_edu_end or end > latest_edu_end:
                    latest_edu_end = end
                edu_dates.append((start or end, end, label))

                                                                            
        if latest_edu_end and exp_dates:
            very_early = [
                (s, e, lbl) for s, e, lbl in exp_dates
                if s < latest_edu_end - __import__("datetime").timedelta(days=365)
                and "intern" not in lbl.lower()
            ]
            for s, e, lbl in very_early:
                report.issues.append(ValidationIssue(
                    Severity.WARNING, "experience",
                    f"Job started {s.year}, but education ends {latest_edu_end.year} "
                    f"— is this an internship?",
                    lbl,
                ))

                                                                            
        if len(exp_dates) >= 2:
            for i in range(len(exp_dates)):
                for j in range(i + 1, len(exp_dates)):
                    s1, e1, l1 = exp_dates[i]
                    s2, e2, l2 = exp_dates[j]
                                                            
                    overlap_start = max(s1, s2)
                    overlap_end   = min(e1, e2)
                    if overlap_end > overlap_start:
                        overlap_months = (overlap_end - overlap_start).days / 30
                        if overlap_months > 3:
                            report.issues.append(ValidationIssue(
                                Severity.INFO, "experience",
                                f"{overlap_months:.0f}-month overlap with another job "
                                f"(possible dual employment or data error)",
                                f"{l1} ↔ {l2}",
                            ))

                                                                            
        if exp_dates:
            all_starts = [s for s, _, _ in exp_dates]
            report.earliest_start = str(min(all_starts).year)

                                   
            intervals = sorted([(s, e) for s, e, _ in exp_dates])
            merged = [intervals[0]]
            for s, e in intervals[1:]:
                ps, pe = merged[-1]
                if s <= pe:
                    merged[-1] = (ps, max(pe, e))
                else:
                    merged.append((s, e))
            total_days = sum((e - s).days for s, e in merged)
            report.total_years_experience = round(total_days / 365.25, 1)

        report.is_consistent = len(report.errors) == 0
        return report

