from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

                                                                               
                   
                                                                               
_DATE_RANGE_RE = re.compile(
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}"
    r"\s*[-–—]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}"
    r"\s*[-–—]\s*(?:Present|Current|Now|ongoing)"
    r"|\b\d{4}\s*[-–—]\s*(?:\d{4}|Present|Current)\b",
    re.IGNORECASE,
)

_SINGLE_DATE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b"
    r"|\b\d{4}\b",
    re.IGNORECASE,
)

_DEGREE_RE = re.compile(
    r"\b(?:B\.?(?:Sc|Tech|E|S|A|Com|Ed)|M\.?(?:Sc|Tech|E|S|A|Com|Ed|B|Phil)|"
    r"Ph\.?D|B\.?B\.?A|M\.?B\.?A|B\.?C\.?A|M\.?C\.?A|"
    r"Bachelor|Master|Doctor|Doctorate|Associate|Diploma|"
    r"B\.Eng|M\.Eng|BE|ME|BTech|MTech|BCA|MCA|BSc|MSc|BBA|MBA|"
    r"High\s+School|Secondary|Intermediate|10th|12th|SSC|HSC|CBSE|ICSE)\b",
    re.IGNORECASE,
)

_GPA_RE = re.compile(
    r"\b(?:GPA|CGPA|Percentage|Score|Grade)\s*[:\-]?\s*[\d.]+",
    re.IGNORECASE,
)

_BULLET_RE = re.compile(r"^[•\-–—►▸●▶✓✔*]\s+")

_EMAIL_RE = re.compile(r"[A-Za-z0-9_.+\-]+@[A-Za-z0-9\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")
_URL_RE = re.compile(r"https?://\S+|(?:www|linkedin|github)\.\S+", re.IGNORECASE)

_LOCATION_PATTERN = re.compile(
    r"\b(?:New York|San Francisco|London|Bangalore|Bengaluru|Mumbai|Delhi|"
    r"Chennai|Hyderabad|Pune|Kolkata|Noida|Gurgaon|Gurugram|"
    r"India|USA|UK|US|United States|United Kingdom|Canada|Australia"
    r"|\b[A-Z][a-z]+,\s*[A-Z]{2}\b"            
    r")\b",
    re.IGNORECASE,
)

                                                                               
                       
                                                                               

                                                    
_TECH_KEYWORDS: frozenset[str] = frozenset({
    "python", "java", "javascript", "typescript", "c++", "c#", "c", "go", "golang",
    "rust", "swift", "kotlin", "scala", "r", "matlab", "perl", "ruby", "php",
    "html", "css", "sql", "nosql", "bash", "shell", "powershell",
    "react", "angular", "vue", "node", "nodejs", "express", "django", "flask",
    "spring", "fastapi", "nestjs", "nextjs", "gatsby", "svelte",
    "tensorflow", "pytorch", "keras", "scikit", "pandas", "numpy", "scipy",
    "matplotlib", "seaborn", "plotly", "tableau", "powerbi", "excel",
    "docker", "kubernetes", "aws", "gcp", "azure", "heroku", "vercel",
    "git", "github", "gitlab", "bitbucket", "jenkins", "travis", "circle",
    "mysql", "postgresql", "postgres", "mongodb", "redis", "sqlite",
    "elasticsearch", "kafka", "rabbitmq", "graphql", "rest", "api",
    "linux", "ubuntu", "windows", "macos", "android", "ios",
    "machine learning", "deep learning", "nlp", "ai", "ml", "data science",
    "opencv", "langchain", "llm", "transformer", "bert", "gpt",
    "agile", "scrum", "jira", "confluence",
    "html5", "css3", "sass", "less", "webpack", "vite",
    "firebase", "supabase", "prisma", "sequelize",
    "spark", "hadoop", "hive", "airflow", "dbt",
    "figma", "sketch", "adobe xd", "photoshop", "illustrator",
    "postman", "swagger", "openapi",
})

                       
_EXPERIENCE_ROLE_WORDS: frozenset[str] = frozenset({
    "intern", "internship", "engineer", "developer", "analyst", "manager",
    "senior", "junior", "associate", "lead", "architect", "consultant",
    "specialist", "coordinator", "director", "officer", "head",
    "executive", "president", "vp", "cto", "ceo", "founder", "co-founder",
    "researcher", "scientist", "professor", "assistant", "teaching",
    "part-time", "full-time", "contract", "freelance", "remote",
    "trainee", "apprentice", "fellow", "staff",
})

_EXPERIENCE_ORG_WORDS: frozenset[str] = frozenset({
    "technologies", "solutions", "systems", "services", "labs", "ltd",
    "limited", "inc", "corporation", "corp", "company", "enterprises",
    "group", "global", "international", "india", "pvt", "private",
    "software", "tech", "digital", "consulting", "research",
})

                      
_EDUCATION_WORDS: frozenset[str] = frozenset({
    "university", "college", "institute", "school", "iit", "nit", "bits",
    "faculty", "department", "campus", "academy", "polytechnic",
    "bachelor", "master", "phd", "doctorate", "diploma", "degree",
    "b.tech", "m.tech", "btech", "mtech", "bca", "mca", "b.sc", "m.sc",
    "bsc", "msc", "bba", "mba", "engineering", "science", "arts",
    "gpa", "cgpa", "percentage", "grade", "marks", "distinction",
    "honours", "honors", "merit", "scholarship",
    "10th", "12th", "ssc", "hsc", "cbse", "icse", "ict",
})

                    
_PROJECT_WORDS: frozenset[str] = frozenset({
    "built", "developed", "created", "implemented", "designed", "deployed",
    "launched", "architected", "engineered", "automated", "integrated",
    "app", "application", "system", "platform", "tool", "library",
    "framework", "bot", "chatbot", "api", "website", "portal",
    "dashboard", "model", "algorithm", "pipeline", "service",
    "github", "deployed", "open source", "repo", "repository",
})

                              
_AWARD_WORDS: frozenset[str] = frozenset({
    "award", "prize", "honor", "honour", "scholarship", "fellowship",
    "merit", "distinction", "achievement", "recognition", "rank",
    "winner", "finalist", "selected", "recipient", "granted",
    "best", "top", "first", "second", "third", "gold", "silver",
    "bronze", "national", "state", "district", "competition",
    "hackathon", "olympiad", "contest", "tournament",
})


                                                                               
                    
                                                                               

@dataclass
class BlockFeatures:
    line_count: int
    bullet_count: int
    date_range_count: int
    single_date_count: int
    degree_pattern_count: int
    gpa_count: int
    email_count: int
    phone_count: int
    url_count: int
    tech_keyword_count: int
    experience_role_count: int
    experience_org_count: int
    education_word_count: int
    project_word_count: int
    award_word_count: int
    has_contact_line: bool
    avg_line_length: float
    short_line_count: int                                                 
    long_line_count: int                                            


def extract_features(lines: list[str]) -> BlockFeatures:
    if not lines:
        return BlockFeatures(
            line_count=0, bullet_count=0, date_range_count=0, single_date_count=0,
            degree_pattern_count=0, gpa_count=0, email_count=0, phone_count=0,
            url_count=0, tech_keyword_count=0, experience_role_count=0,
            experience_org_count=0, education_word_count=0, project_word_count=0,
            award_word_count=0, has_contact_line=False, avg_line_length=0.0,
            short_line_count=0, long_line_count=0,
        )

    bullet_count = 0
    date_range_count = 0
    single_date_count = 0
    degree_count = 0
    gpa_count = 0
    email_count = 0
    phone_count = 0
    url_count = 0
    tech_count = 0
    role_count = 0
    org_count = 0
    edu_word_count = 0
    proj_word_count = 0
    award_word_count = 0
    has_contact = False
    total_length = 0
    short_count = 0
    long_count = 0

    full_text = " ".join(lines).lower()

                                                
    for kw in _TECH_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", full_text):
            tech_count += 1

    for kw in _EXPERIENCE_ROLE_WORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", full_text):
            role_count += 1

    for kw in _EXPERIENCE_ORG_WORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", full_text):
            org_count += 1

    for kw in _EDUCATION_WORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", full_text):
            edu_word_count += 1

    for kw in _PROJECT_WORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", full_text):
            proj_word_count += 1

    for kw in _AWARD_WORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", full_text):
            award_word_count += 1

    for line in lines:
        stripped = line.strip()
        total_length += len(stripped)
        wc = len(stripped.split())

        if wc <= 4:
            short_count += 1
        if wc > 20:
            long_count += 1

        if _BULLET_RE.match(stripped):
            bullet_count += 1

        if _DATE_RANGE_RE.search(stripped):
            date_range_count += 1

        if _SINGLE_DATE_RE.search(stripped):
            single_date_count += 1

        if _DEGREE_RE.search(stripped):
            degree_count += 1

        if _GPA_RE.search(stripped):
            gpa_count += 1

        if _EMAIL_RE.search(stripped):
            email_count += 1
            has_contact = True

        if _PHONE_RE.search(stripped):
            phone_count += 1
            has_contact = True

        if _URL_RE.search(stripped):
            url_count += 1

    avg_len = total_length / len(lines) if lines else 0.0

    return BlockFeatures(
        line_count=len(lines),
        bullet_count=bullet_count,
        date_range_count=date_range_count,
        single_date_count=single_date_count,
        degree_pattern_count=degree_count,
        gpa_count=gpa_count,
        email_count=email_count,
        phone_count=phone_count,
        url_count=url_count,
        tech_keyword_count=tech_count,
        experience_role_count=role_count,
        experience_org_count=org_count,
        education_word_count=edu_word_count,
        project_word_count=proj_word_count,
        award_word_count=award_word_count,
        has_contact_line=has_contact,
        avg_line_length=avg_len,
        short_line_count=short_count,
        long_line_count=long_count,
    )


                                                                               
                 
                                                                               

def _score_sections(f: BlockFeatures) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    n = max(f.line_count, 1)

                                                                              
    if f.tech_keyword_count >= 2:
        scores["skills"] += 0.4 + min(f.tech_keyword_count / 20, 0.4)
    if f.bullet_count == 0 and f.date_range_count == 0 and f.tech_keyword_count >= 3:
        scores["skills"] += 0.15
                                                   
    if f.avg_line_length < 80 and f.bullet_count == 0 and f.tech_keyword_count >= 2:
        scores["skills"] += 0.1

                                                                              
    if f.date_range_count >= 1:
        scores["experience"] += 0.3
    if f.experience_role_count >= 1:
        scores["experience"] += 0.2 + min(f.experience_role_count / 5, 0.2)
    if f.experience_org_count >= 1:
        scores["experience"] += 0.15
    if f.bullet_count >= 2:
        scores["experience"] += 0.2
    if f.date_range_count >= 1 and f.bullet_count >= 1:
        scores["experience"] += 0.15                          

                                                                              
    if f.degree_pattern_count >= 1:
        scores["education"] += 0.5
    if f.gpa_count >= 1:
        scores["education"] += 0.2
    if f.education_word_count >= 2:
        scores["education"] += 0.2 + min(f.education_word_count / 8, 0.2)
    if f.degree_pattern_count >= 1 and f.single_date_count >= 1:
        scores["education"] += 0.1

                                                                              
    if f.project_word_count >= 2:
        scores["projects"] += 0.3 + min(f.project_word_count / 8, 0.3)
    if f.tech_keyword_count >= 1 and f.bullet_count >= 1 and f.date_range_count == 0:
        scores["projects"] += 0.2
    if f.url_count >= 1 and f.bullet_count >= 1:
        scores["projects"] += 0.15

                                                                              
    if f.award_word_count >= 1:
        scores["awards"] += 0.3 + min(f.award_word_count / 5, 0.3)
    if f.bullet_count >= 1 and f.award_word_count >= 1:
        scores["awards"] += 0.15

                                                                              
    if f.bullet_count == 0 and f.date_range_count == 0:
        if f.avg_line_length > 80:
            scores["summary"] += 0.55
        elif f.avg_line_length > 55:
            scores["summary"] += 0.45
        elif f.avg_line_length > 40:
            scores["summary"] += 0.30
        elif f.long_line_count >= 1:
            scores["summary"] += 0.20
    if f.line_count <= 4 and f.avg_line_length > 50 and f.date_range_count == 0 and f.bullet_count == 0:
        scores["summary"] += 0.15

                                                                              
    if f.avg_line_length < 40 and f.bullet_count >= 1 and f.date_range_count == 0:
        scores["interests"] += 0.2
                                                                  
    if f.bullet_count >= 2 and f.tech_keyword_count == 0 and f.date_range_count == 0:
        scores["interests"] += 0.1

                                    
    for key in scores:
        scores[key] = min(scores[key], 1.0)

    return dict(scores)


                                                                               
            
                                                                               

def best_section(lines: list[str]) -> tuple[str | None, float, dict[str, float]]:
    if not lines:
        return None, 0.0, {}

    features = extract_features(lines)
    scores = _score_sections(features)

    if not scores:
        return None, 0.0, {}

    best_key = max(scores, key=lambda k: scores[k])
    best_score = scores[best_key]

    if best_score < 0.25:
        return None, 0.0, scores

    return best_key, best_score, scores


def score_section_signatures(lines: list[str]) -> dict[str, float]:
    if not lines:
        return {}

    features = extract_features(lines)
    scores = _score_sections(features)

                                                     
    for key in ("skills", "experience", "education", "projects", "awards", "summary", "interests"):
        scores.setdefault(key, 0.0)

    return scores


def classify_block(lines: list[str]) -> str | None:
    section, confidence, _ = best_section(lines)
    if confidence >= 0.35:
        return section
    return None

