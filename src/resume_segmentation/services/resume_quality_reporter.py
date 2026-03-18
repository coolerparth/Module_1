"""
resume_quality_reporter.py — Resume quality scoring & actionable feedback.

Produces:
  1. ATS Compatibility Score (0–100): how well ATS systems will parse this
  2. Completeness Score (0–100): how many best-practice fields are filled
  3. Bullet Quality Score (0–100): STAR method, action verbs, quantification
  4. Actionable Suggestions: concrete "do this" advice ranked by impact
  5. Missing Fields: explicitly lists what's absent

ATS (Applicant Tracking System) compatibility criteria:
  - Has name, email, phone                    → required
  - Has standard section headings             → required
  - No tables / columns (detected via layout) → required
  - Skills section present                    → strong
  - Date ranges in standard format            → strong
  - No graphics-heavy layout                  → recommended
  - LinkedIn URL present                      → recommended

Bullet quality criteria (based on Google / McKinsey resume advice):
  - Starts with strong action verb (achieved, built, reduced, led…)
  - Contains a number/metric (improved by 40%, served 2M users)
  - Is not too short (<6 words) or too long (>40 words)
  - Does not start with "Responsible for" or "Helped with"
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..models.resume import ExperienceEntry, ResumeProfile


                                                                               
              
                                                                               

_STRONG_ACTION_VERBS: frozenset[str] = frozenset([
                             
    "architected", "automated", "built", "configured", "containerized",
    "debugged", "deployed", "designed", "developed", "engineered",
    "implemented", "integrated", "launched", "migrated", "modeled",
    "optimized", "programmed", "refactored", "scaled", "shipped",
                             
    "coached", "coordinated", "delivered", "directed", "drove",
    "established", "executed", "facilitated", "founded", "grew",
    "guided", "hired", "led", "managed", "mentored", "oversaw",
    "pioneered", "spearheaded", "supervised", "transformed",
                          
    "achieved", "advanced", "analyzed", "created", "decreased",
    "enhanced", "evaluated", "expanded", "identified", "improved",
    "increased", "initiated", "introduced", "investigated", "maximized",
    "minimized", "produced", "reduced", "resolved", "restructured",
    "revamped", "solved", "streamlined", "strengthened",
                   
    "authored", "collaborated", "communicated", "contributed", "defined",
    "documented", "negotiated", "partnered", "presented", "published",
    "trained",
])

_WEAK_OPENINGS: frozenset[str] = frozenset([
    "responsible for", "helped with", "assisted with", "worked on",
    "involved in", "helped to", "tasked with", "duties included",
    "job was to", "worked with team", "part of team",
])

_NUMBER_RE    = re.compile(r"\d")
_PERCENT_RE   = re.compile(r"\d+%|\d+\s*percent", re.IGNORECASE)
_METRIC_RE    = re.compile(
    r"\$[\d,.]+|\d+[kKmMbB]\+?|\d+\s*(?:million|billion|thousand|users|"
    r"customers|requests|transactions|lines|repos|servers|teams?|"
    r"engineers?|countries|markets?)\b",
    re.IGNORECASE,
)
_FIRST_WORD_RE = re.compile(r"^([A-Za-z]+)")


                                                                               
               
                                                                               

@dataclass
class BulletAnalysis:
    text: str
    has_action_verb: bool
    has_metric: bool
    has_number: bool
    is_weak_opening: bool
    word_count: int
    score: float               

    @property
    def feedback(self) -> list[str]:
        tips: list[str] = []
        if self.is_weak_opening:
            tips.append("Start with a strong action verb instead of 'Responsible for'")
        elif not self.has_action_verb:
            tips.append("Begin with an action verb (Built, Led, Reduced, Achieved…)")
        if not self.has_metric:
            tips.append("Add a metric or number to quantify impact")
        if self.word_count < 6:
            tips.append("Too brief — expand with context and impact")
        if self.word_count > 40:
            tips.append("Too long — trim to 1–2 lines max")
        return tips


@dataclass
class Suggestion:
    priority: int                              
    category: str
    message: str
    example: str = ""


@dataclass
class QualityReport:
    ats_score: float                 
    completeness_score: float        
    bullet_score: float              
    overall_score: float                        

    ats_grade: str
    overall_grade: str

    missing_fields: list[str]
    suggestions: list[Suggestion]
    bullet_analyses: list[BulletAnalysis]
    top_bullets: list[str]                    
    weak_bullets: list[str]                                        

    def to_dict(self) -> dict:
        return {
            "scores": {
                "ats": self.ats_score,
                "completeness": self.completeness_score,
                "bullets": self.bullet_score,
                "overall": self.overall_score,
            },
            "grades": {
                "ats": self.ats_grade,
                "overall": self.overall_grade,
            },
            "missing_fields": self.missing_fields,
            "suggestions": [
                {"priority": s.priority, "category": s.category,
                 "message": s.message, "example": s.example}
                for s in sorted(self.suggestions, key=lambda x: x.priority)
            ],
            "bullet_quality": {
                "top_bullets": self.top_bullets,
                "weak_bullets": self.weak_bullets,
            },
        }


                                                                               
          
                                                                               

class ResumeQualityReporter:

    def analyze(
        self,
        profile: ResumeProfile,
        layout: str = "single_column",
    ) -> QualityReport:
        missing_fields: list[str] = []
        suggestions: list[Suggestion] = []

        ats_score = self._ats_score(profile, layout, missing_fields, suggestions)
        completeness_score = self._completeness_score(profile, missing_fields, suggestions)
        bullet_analyses, bullet_score = self._bullet_score(profile, suggestions)

        overall = round(
            ats_score * 0.35 + completeness_score * 0.35 + bullet_score * 0.30,
            1,
        )

                                      
        suggestions.sort(key=lambda s: s.priority)

                          
        scored = sorted(bullet_analyses, key=lambda b: b.score, reverse=True)
        top_bullets  = [b.text for b in scored[:3] if b.score >= 0.6]
        weak_bullets = [b.text for b in scored if b.score < 0.4][:3]

        return QualityReport(
            ats_score=ats_score,
            completeness_score=completeness_score,
            bullet_score=bullet_score,
            overall_score=overall,
            ats_grade=_score_to_grade(ats_score),
            overall_grade=_score_to_grade(overall),
            missing_fields=missing_fields,
            suggestions=suggestions,
            bullet_analyses=bullet_analyses,
            top_bullets=top_bullets,
            weak_bullets=weak_bullets,
        )

                                                                            

    def _ats_score(
        self,
        profile: ResumeProfile,
        layout: str,
        missing: list[str],
        suggestions: list[Suggestion],
    ) -> float:
        score = 0.0

                         
        if profile.personal_info.name:
            score += 15
        else:
            missing.append("Name")
            suggestions.append(Suggestion(1, "ATS", "Add your full name at the top of the resume"))

                          
        if profile.personal_info.email:
            score += 15
        else:
            missing.append("Email")
            suggestions.append(Suggestion(1, "ATS", "Add a professional email address"))

                          
        if profile.personal_info.phone:
            score += 10
        else:
            missing.append("Phone")
            suggestions.append(Suggestion(2, "ATS", "Add your phone number in international format (+91 XXXXX XXXXX)"))

                        
        if profile.skills:
            score += 15
        else:
            missing.append("Skills section")
            suggestions.append(Suggestion(2, "ATS",
                "Add a 'Technical Skills' section — ATS systems scan for keywords here",
                "Skills: Python, React, AWS, Docker, PostgreSQL"))

                               
        if profile.experience:
            has_dates = any(e.date_range and e.date_range.start for e in profile.experience)
            score += 15 if has_dates else 8
            if not has_dates:
                suggestions.append(Suggestion(2, "ATS",
                    "Add date ranges to experience entries",
                    "Jan 2022 – Present"))

                   
        if profile.education:
            score += 10
        else:
            missing.append("Education")

                                                     
        if layout == "two_column":
            score -= 10
            suggestions.append(Suggestion(3, "ATS",
                "Two-column layouts often confuse ATS systems — consider a single-column format"))

                  
        if any("linkedin" in (lnk.url or "").lower() for lnk in profile.links):
            score += 10
        else:
            suggestions.append(Suggestion(4, "ATS",
                "Add your LinkedIn profile URL",
                "linkedin.com/in/yourname"))

                           
        if profile.summary:
            score += 10
        else:
            suggestions.append(Suggestion(5, "Completeness",
                "Add a 2–3 line professional summary at the top"))

        return min(max(score, 0), 100)

                                                                            

    def _completeness_score(
        self,
        profile: ResumeProfile,
        missing: list[str],
        suggestions: list[Suggestion],
    ) -> float:
        checks: list[tuple[bool, int, str]] = [
            (bool(profile.personal_info.name),     10, "Name"),
            (bool(profile.personal_info.email),    10, "Email"),
            (bool(profile.personal_info.phone),     8, "Phone"),
            (bool(profile.personal_info.location),  5, "Location"),
            (bool(profile.personal_info.headline),  5, "Headline"),
            (bool(profile.links),                   7, "Links"),
            (bool(profile.summary),                 8, "Summary"),
            (bool(profile.skills),                 12, "Skills"),
            (bool(profile.experience),             15, "Experience"),
            (bool(profile.education),              12, "Education"),
            (bool(profile.projects),                8, "Projects"),
        ]
        total_weight = sum(w for _, w, _ in checks)
        earned = sum(w for ok, w, _ in checks if ok)
        return round(earned / total_weight * 100, 1)

                                                                            

    def _bullet_score(
        self,
        profile: ResumeProfile,
        suggestions: list[Suggestion],
    ) -> tuple[list[BulletAnalysis], float]:
        all_bullets: list[str] = []
        for entry in profile.experience:
            all_bullets.extend(entry.bullets)
        for proj in profile.projects:
            if proj.description:
                                                               
                for sent in re.split(r"[.;]", proj.description):
                    sent = sent.strip()
                    if sent and len(sent) > 10:
                        all_bullets.append(sent)

        if not all_bullets:
            suggestions.append(Suggestion(3, "Bullets",
                "Add bullet points to experience/project entries describing your contributions",
                "• Reduced API latency by 40% by implementing Redis caching"))
            return [], 0.0

        analyses: list[BulletAnalysis] = [_analyze_bullet(b) for b in all_bullets]
        avg_score = sum(a.score for a in analyses) / len(analyses)

                                            
        weak = [a for a in analyses if a.score < 0.4 and a.feedback]
        if weak:
            example_fb = weak[0].feedback[0]
            suggestions.append(Suggestion(3, "Bullets",
                f"Strengthen weak bullet points: {example_fb}",
                "• Architected payment API processing $2M/day, reducing fraud by 30%"))

        no_metrics = sum(1 for a in analyses if not a.has_metric)
        if no_metrics > len(analyses) * 0.5:
            suggestions.append(Suggestion(4, "Bullets",
                f"{no_metrics}/{len(analyses)} bullets lack metrics — add numbers to show impact",
                "Before: 'Improved performance'  →  After: 'Reduced load time by 60%'"))

        return analyses, round(avg_score * 100, 1)


def _analyze_bullet(text: str) -> BulletAnalysis:
    stripped = text.strip().lstrip("•-–—►▸●▶✓✔* ")
    words = stripped.split()
    word_count = len(words)
    first_word = words[0].lower() if words else ""

    has_action = first_word in _STRONG_ACTION_VERBS
    has_metric = bool(_METRIC_RE.search(stripped) or _PERCENT_RE.search(stripped))
    has_number = bool(_NUMBER_RE.search(stripped))
    is_weak = any(stripped.lower().startswith(w) for w in _WEAK_OPENINGS)

    score = 0.0
    if has_action:   score += 0.35
    if has_metric:   score += 0.35
    elif has_number: score += 0.15
    if 8 <= word_count <= 30: score += 0.20
    elif 6 <= word_count < 8: score += 0.10
    if is_weak:      score -= 0.20

    return BulletAnalysis(
        text=stripped, has_action_verb=has_action,
        has_metric=has_metric, has_number=has_number,
        is_weak_opening=is_weak, word_count=word_count,
        score=round(max(0.0, min(score, 1.0)), 3),
    )


def _score_to_grade(score: float) -> str:
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 55: return "C"
    if score >= 40: return "D"
    return "F"
