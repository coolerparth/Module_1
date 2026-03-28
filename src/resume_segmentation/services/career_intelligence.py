from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

from ..models.resume import ExperienceEntry, ResumeProfile


                                                                               
                   
                                                                               

class CareerLevel(str, Enum):
    FRESHER    = "Fresher (0–1 yrs)"
    JUNIOR     = "Junior (1–3 yrs)"
    MID        = "Mid-level (3–6 yrs)"
    SENIOR     = "Senior (6–10 yrs)"
    PRINCIPAL  = "Principal / Staff (10–15 yrs)"
    EXECUTIVE  = "Executive / Director (15+ yrs)"
    UNKNOWN    = "Unknown"


class TechDomain(str, Enum):
    BACKEND     = "Backend / Full-stack"
    FRONTEND    = "Frontend"
    DATA        = "Data Engineering / Analytics"
    ML_AI       = "ML / AI / Data Science"
    MOBILE      = "Mobile Development"
    DEVOPS      = "DevOps / Cloud / Infrastructure"
    SECURITY    = "Security / Networking"
    EMBEDDED    = "Embedded / Systems"
    GENERAL     = "General Software"
    UNKNOWN     = "Unknown"


                                                                               
                               
                                                                               

_TITLE_LEVEL_MAP: list[tuple[re.Pattern, CareerLevel]] = [
    (re.compile(r"\b(cto|ceo|vp|vice\s+president|chief|director|head\s+of)\b",        re.I), CareerLevel.EXECUTIVE),
    (re.compile(r"\b(principal|staff|distinguished|fellow|architect)\b",               re.I), CareerLevel.PRINCIPAL),
    (re.compile(r"\b(senior|sr\.?|lead|manager|tech\s+lead|team\s+lead)\b",            re.I), CareerLevel.SENIOR),
    (re.compile(r"\b(mid|ii|2|associate)\b",                                           re.I), CareerLevel.MID),
    (re.compile(r"\b(junior|jr\.?|i\b|entry\s+level|entry-level)\b",                  re.I), CareerLevel.JUNIOR),
    (re.compile(r"\b(intern|trainee|apprentice|graduate\s+trainee|fresher)\b",         re.I), CareerLevel.FRESHER),
]


                                                                               
                        
                                                                               

_DOMAIN_KEYWORDS: dict[TechDomain, frozenset[str]] = {
    TechDomain.ML_AI: frozenset([
        "machine learning", "deep learning", "neural", "nlp", "tensorflow", "pytorch",
        "scikit", "pandas", "numpy", "data science", "ai", "llm", "gpt", "bert",
        "computer vision", "opencv", "kaggle", "model training", "hugging face",
        "langchain", "rag", "generative ai",
    ]),
    TechDomain.DATA: frozenset([
        "spark", "hadoop", "kafka", "airflow", "dbt", "data warehouse", "etl",
        "data pipeline", "bigquery", "snowflake", "hive", "flink", "data engineer",
        "data analyst", "tableau", "power bi", "looker", "databricks",
    ]),
    TechDomain.DEVOPS: frozenset([
        "kubernetes", "k8s", "docker", "terraform", "ansible", "jenkins", "ci/cd",
        "cloud", "aws", "gcp", "azure", "devops", "infrastructure", "sre",
        "prometheus", "grafana", "helm", "argocd", "platform engineer",
    ]),
    TechDomain.FRONTEND: frozenset([
        "react", "angular", "vue", "next.js", "svelte", "frontend", "ui developer",
        "html", "css", "sass", "tailwind", "redux", "d3.js", "three.js",
        "figma", "ux", "web developer", "ui/ux",
    ]),
    TechDomain.MOBILE: frozenset([
        "android", "ios", "react native", "flutter", "swift", "kotlin",
        "mobile developer", "xcode", "expo", "jetpack", "swiftui",
    ]),
    TechDomain.BACKEND: frozenset([
        "backend", "api", "rest", "grpc", "microservices", "django", "flask",
        "fastapi", "spring", "node.js", "express", "database", "server",
        "java", "golang", "postgresql", "redis", "kafka", "graphql",
    ]),
    TechDomain.SECURITY: frozenset([
        "security", "cybersecurity", "penetration", "pentest", "soc",
        "firewall", "encryption", "oauth", "siem", "network security", "cve",
    ]),
    TechDomain.EMBEDDED: frozenset([
        "embedded", "firmware", "rtos", "arduino", "raspberry pi", "fpga",
        "c++", "assembly", "microcontroller", "iot", "hardware",
    ]),
}


                                                                               
                                   
                                                                               

_MONTH_MAP: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date_approx(text: str | None) -> Optional[date]:
    if not text:
        return None
    text = text.strip()

                                  
    m = re.match(r"([A-Za-z]{3,})\s+(\d{4})", text)
    if m:
        month_str = m.group(1)[:3].lower()
        year = int(m.group(2))
        month = _MONTH_MAP.get(month_str, 1)
        return date(year, month, 1)

                  
    m = re.match(r"^(\d{4})$", text)
    if m:
        return date(int(m.group(1)), 1, 1)

               
    m = re.match(r"(\d{1,2})/(\d{4})", text)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)

    return None


def _experience_duration_years(entry: ExperienceEntry) -> float:
    if not entry.date_range:
        return 0.0

    dr = entry.date_range
    start = _parse_date_approx(dr.start)
    if not start:
        return 0.0

    if dr.is_current or not dr.end:
        end = date.today()
    else:
        end = _parse_date_approx(dr.end) or date.today()

    days = (end - start).days
    return max(days / 365.25, 0.0)


                                                                               
                  
                                                                               

_TIER1_COMPANIES: frozenset[str] = frozenset([
    "google", "microsoft", "apple", "amazon", "meta", "netflix", "linkedin",
    "twitter", "x corp", "uber", "airbnb", "stripe", "palantir", "openai",
    "anthropic", "deepmind", "salesforce", "adobe", "nvidia", "intel", "amd",
    "oracle", "sap", "ibm", "cisco", "vmware", "atlassian", "shopify",
    "spotify", "netflix", "bytedance", "tiktok", "pinterest", "snap", "zoom",
    "slack", "figma", "notion", "airtable", "databricks", "snowflake",
    "flipkart", "ola", "swiggy", "zomato", "paytm", "phonepe", "razorpay",
    "freshworks", "zoho", "infosys", "tcs", "wipro", "hcl", "cognizant",
    "accenture", "deloitte", "mckinsey", "goldman sachs", "jpmorgan",
    "morgan stanley", "bloomberg", "citadel", "two sigma", "jane street",
    "samsung", "lg", "sony", "toyota", "tesla", "spacex",
])

_TIER1_UNIVERSITIES: frozenset[str] = frozenset([
    "iit", "iim", "nit", "bits pilani", "iiit",
    "indian institute of technology",
    "indian institute of management",
    "national institute of technology",
    "mit", "massachusetts institute of technology",
    "stanford", "harvard", "caltech", "carnegie mellon", "cmu",
    "berkeley", "uc berkeley", "oxford", "cambridge", "eth zurich",
    "imperial college", "nyu", "columbia", "yale", "princeton", "cornell",
    "georgia tech", "university of michigan", "university of toronto",
    "national university of singapore", "nus", "nanyang", "ntu",
    "delhi university", "du", "mumbai university", "vit", "srm",
    "anna university", "jadavpur", "osmania", "hyderabad central",
])


                                                                               
                            
                                                                               

@dataclass
class CareerIntelligence:
    career_level: CareerLevel
    total_years_experience: float
    primary_domain: TechDomain
    domain_scores: dict[str, float]
    title_from_experience: Optional[str]
    current_employer: Optional[str]
    notable_companies: list[str]
    notable_universities: list[str]
    career_gaps: list[dict]                                      
    is_fresher: bool
    has_management_experience: bool
    tech_stack_summary: dict[str, list[str]]                          
    seniority_score: float                     


                                                                               
               
                                                                               

class CareerIntelligenceAnalyzer:

    def analyze(self, profile: ResumeProfile) -> CareerIntelligence:
        total_years = self._compute_total_experience(profile)
        career_level = self._infer_career_level(profile, total_years)
        domain, domain_scores = self._infer_domain(profile)
        title, employer = self._current_position(profile)
        notable_companies = self._find_notable_companies(profile)
        notable_universities = self._find_notable_universities(profile)
        gaps = self._detect_career_gaps(profile)
        has_mgmt = self._has_management_experience(profile)
        tech_summary = self._tech_stack_summary(profile)
        seniority = self._seniority_score(total_years, career_level, notable_companies, has_mgmt)

        return CareerIntelligence(
            career_level=career_level,
            total_years_experience=round(total_years, 1),
            primary_domain=domain,
            domain_scores={k.value: round(v, 3) for k, v in domain_scores.items()},
            title_from_experience=title,
            current_employer=employer,
            notable_companies=notable_companies,
            notable_universities=notable_universities,
            career_gaps=gaps,
            is_fresher=(career_level in {CareerLevel.FRESHER, CareerLevel.JUNIOR} and total_years < 1),
            has_management_experience=has_mgmt,
            tech_stack_summary=tech_summary,
            seniority_score=seniority,
        )

    def _compute_total_experience(self, profile: ResumeProfile) -> float:
        if not profile.experience:
            return 0.0

                                                     
        intervals: list[tuple[date, date]] = []
        for entry in profile.experience:
            if not entry.date_range:
                continue
            start = _parse_date_approx(entry.date_range.start)
            if not start:
                continue
            if entry.date_range.is_current or not entry.date_range.end:
                end = date.today()
            else:
                end = _parse_date_approx(entry.date_range.end) or date.today()
            if end >= start:
                intervals.append((start, end))

        if not intervals:
            return 0.0

                                     
        intervals.sort()
        merged: list[tuple[date, date]] = [intervals[0]]
        for s, e in intervals[1:]:
            prev_s, prev_e = merged[-1]
            if s <= prev_e:
                merged[-1] = (prev_s, max(prev_e, e))
            else:
                merged.append((s, e))

        total_days = sum((e - s).days for s, e in merged)
        return total_days / 365.25

    def _infer_career_level(self, profile: ResumeProfile, total_years: float) -> CareerLevel:
                                                
        for entry in profile.experience:
            title = (entry.title or "").lower()
            for pat, level in _TITLE_LEVEL_MAP:
                if pat.search(title):
                    return level

                              
        if total_years == 0:
            return CareerLevel.FRESHER
        if total_years < 1:
            return CareerLevel.FRESHER
        if total_years < 3:
            return CareerLevel.JUNIOR
        if total_years < 6:
            return CareerLevel.MID
        if total_years < 10:
            return CareerLevel.SENIOR
        if total_years < 15:
            return CareerLevel.PRINCIPAL
        return CareerLevel.EXECUTIVE

    def _infer_domain(self, profile: ResumeProfile) -> tuple[TechDomain, dict[TechDomain, float]]:
        full_text = " ".join([
            " ".join(profile.skills),
            " ".join(e.title or "" for e in profile.experience),
            " ".join(b for e in profile.experience for b in e.bullets),
            " ".join(p.description or "" for p in profile.projects),
        ]).lower()

        scores: dict[TechDomain, float] = {}
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in full_text)
            if score > 0:
                scores[domain] = score / len(keywords)

        if not scores:
            return TechDomain.GENERAL, {}

        best = max(scores, key=lambda d: scores[d])
        return best, scores

    def _current_position(self, profile: ResumeProfile) -> tuple[Optional[str], Optional[str]]:
        for entry in profile.experience:
            if entry.date_range and entry.date_range.is_current:
                return entry.title, entry.company
        if profile.experience:
            first = profile.experience[0]
            return first.title, first.company
        return None, None

    def _find_notable_companies(self, profile: ResumeProfile) -> list[str]:
        notable: list[str] = []
        for entry in profile.experience:
            company = (entry.company or "").lower()
            if any(t1 in company for t1 in _TIER1_COMPANIES):
                notable.append(entry.company)
        return list(dict.fromkeys(notable))                         

    def _find_notable_universities(self, profile: ResumeProfile) -> list[str]:
        import re as _re
        notable: list[str] = []
        for entry in profile.education:
            inst = (entry.institution or "").lower()
            matched = False
            for t1 in _TIER1_UNIVERSITIES:
                if len(t1) <= 4:
                    if _re.search(r'\b' + _re.escape(t1) + r'\b', inst):
                        matched = True
                        break
                else:
                    if t1 in inst:
                        matched = True
                        break
            if matched:
                notable.append(entry.institution)
        return list(dict.fromkeys(notable))

    def _detect_career_gaps(self, profile: ResumeProfile) -> list[dict]:
        if len(profile.experience) < 2:
            return []

        gaps: list[dict] = []
        dated = []
        for entry in profile.experience:
            if not entry.date_range:
                continue
            start = _parse_date_approx(entry.date_range.start)
            if entry.date_range.is_current or not entry.date_range.end:
                end = date.today()
            else:
                end = _parse_date_approx(entry.date_range.end) or date.today()
            if start:
                dated.append((start, end, entry.company or ""))

        dated.sort(key=lambda x: x[0])
        for i in range(1, len(dated)):
            prev_end = dated[i - 1][1]
            curr_start = dated[i][0]
            gap_days = (curr_start - prev_end).days
            if gap_days > 90:
                gaps.append({
                    "gap_months": round(gap_days / 30.4, 1),
                    "after_company": dated[i - 1][2],
                    "before_company": dated[i][2],
                })

        return gaps

    def _has_management_experience(self, profile: ResumeProfile) -> bool:
        _MGT_WORDS = re.compile(
            r"\b(manag|led|lead|mentor|coach|team of|direct report|hire|recruit|"
            r"grow|build team|head of|vp|director|chief|officer|president)\b",
            re.I,
        )
        for entry in profile.experience:
            if _MGT_WORDS.search(entry.title or ""):
                return True
            for bullet in entry.bullets:
                if _MGT_WORDS.search(bullet):
                    return True
        return False

    def _tech_stack_summary(self, profile: ResumeProfile) -> dict[str, list[str]]:
        from .skills_normalizer import normalize_skills_list, SkillCategory
        normalized = normalize_skills_list(profile.skills)
        groups: dict[str, list[str]] = {}
        for ns in normalized:
            cat = ns.category.value
            groups.setdefault(cat, [])
            if len(groups[cat]) < 5:
                groups[cat].append(ns.canonical)
        return {k: v for k, v in groups.items() if v}

    def _seniority_score(
        self,
        total_years: float,
        level: CareerLevel,
        notable_companies: list[str],
        has_mgmt: bool,
    ) -> float:
        score = 0.0
                                 
        score += min(total_years / 20, 0.5)
                                 
        level_scores = {
            CareerLevel.FRESHER: 0.0, CareerLevel.JUNIOR: 0.05,
            CareerLevel.MID: 0.1,    CareerLevel.SENIOR: 0.2,
            CareerLevel.PRINCIPAL: 0.25, CareerLevel.EXECUTIVE: 0.3,
            CareerLevel.UNKNOWN: 0.0,
        }
        score += level_scores.get(level, 0.0)
                                        
        score += min(len(notable_companies) * 0.05, 0.15)
                                   
        if has_mgmt:
            score += 0.05
        return round(min(score, 1.0), 3)

