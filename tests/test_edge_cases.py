"""
test_stress.py — Adversarial, unusual, and boundary-condition tests.
Finds bugs that normal unit tests miss.
"""
import sys
sys.path.insert(0, 'src')

from resume_segmentation.services.text_resume_parser import TextResumeParser
from resume_segmentation.services.section_catalog import match_section_heading
from resume_segmentation.services.date_extractor import extract_date_range
from resume_segmentation.services.skills_normalizer import normalize_skills_list, canonicalize_skills
from resume_segmentation.services.gpa_normalizer import normalize_gpa
from resume_segmentation.services.timeline_validator import TimelineValidator
from resume_segmentation.services.resume_quality_reporter import ResumeQualityReporter, _analyze_bullet
from resume_segmentation.services.pii_anonymizer import PIIAnonymizer, AnonymizeMode
from resume_segmentation.services.career_intelligence import CareerIntelligenceAnalyzer
from resume_segmentation.models.resume import *

GRAND_OK = 0
GRAND_T  = 0
parser   = TextResumeParser()

def suite(name, tests):
    global GRAND_OK, GRAND_T
    ok   = sum(1 for _, g, e in tests if g == e)
    fail = [(l, g, e) for l, g, e in tests if g != e]
    GRAND_OK += ok; GRAND_T += len(tests)
    status = "✓" if not fail else "✗"
    print(f"{status} {name}: {ok}/{len(tests)}")
    for l, g, e in fail:
        print(f"    [{l}] got={g!r} expected={e!r}")


# ── ADVERSARIAL SECTION CATALOG ───────────────────────────────────────────
suite("Section catalog adversarial", [
    # Should NOT match (potential false positives)
    ("sentence with experience word",
     match_section_heading("I gained significant experience working on this project"), None),
    ("date with skills word",
     match_section_heading("Jan 2022 - Present | skills assessment ongoing"), None),
    ("long heading reject",
     match_section_heading("Here is a summary of my professional career and background"), None),
    ("numeric only",
     match_section_heading("2022"), None),
    ("single char",
     match_section_heading("A"), None),
    ("comma separated",
     match_section_heading("Python, JavaScript, React"), None),
    ("pipe separated",
     match_section_heading("Python | Java | C++"), None),
    ("url",
     match_section_heading("github.com/johndoe"), None),
    # Should MATCH
    ("WORK EXP caps",       match_section_heading("WORK EXPERIENCE"),       "experience"),
    ("career obj",          match_section_heading("Career Objective"),       "summary"),
    ("key projects",        match_section_heading("Key Projects"),           "projects"),
    ("academic proj",       match_section_heading("Academic Projects"),      "projects"),
    ("cert with s",         match_section_heading("Certifications"),         "certifications"),
    ("languages",           match_section_heading("Languages"),              "languages"),
    ("publications",        match_section_heading("Publications"),           "publications"),
    ("volunteer",           match_section_heading("Volunteer Work"),         "volunteer"),
    ("references",          match_section_heading("References"),             "references"),
    ("courses",             match_section_heading("Relevant Coursework"),    "courses"),
    ("activities",          match_section_heading("Extracurricular Activities"), "interests"),
    ("memberships",         match_section_heading("Professional Memberships"), "activities"),
])


# ── ADVERSARIAL DATE PARSING ──────────────────────────────────────────────
date_cases = [
    # Normal - should work
    ("Jan 2022 – Present",   "Jan 2022", None,       True),
    ("2020-2023",             "2020",     "2023",     False),
    ("Jun 2018 - Dec 2019",  "Jun 2018", "Dec 2019", False),
    # Edge cases
    ("May 2024",              "May 2024", None,       False),  # single date
    ("2024",                  "2024",     None,       False),  # year only
    # Should NOT extract date (no date pattern)
    ("Software Engineer",     None,       None,       False),
    ("Google Inc.",           None,       None,       False),
]
date_results = []
for text, exp_start, exp_end, exp_curr in date_cases:
    _, dr = extract_date_range(text)
    got_start = dr.start if dr else None
    got_end   = dr.end   if dr else None
    got_curr  = dr.is_current if dr else False
    date_results.append((text[:30], got_start == exp_start, True))
    date_results.append((f"{text[:25]}_end", got_end == exp_end, True))
suite("Date parsing accuracy", date_results)


# ── SKILL NORMALIZER STRESS ───────────────────────────────────────────────
suite("Skill normalizer stress", [
    # Unusual casing
    ("PYTHON",          normalize_skills_list(["PYTHON"])[0].canonical,      "Python"),
    ("javascript",      normalize_skills_list(["javascript"])[0].canonical,  "JavaScript"),
    ("TENSORFLOW",      normalize_skills_list(["TENSORFLOW"])[0].canonical,  "TensorFlow"),
    # Multi-word aliases
    ("apache kafka",    normalize_skills_list(["apache kafka"])[0].canonical, "Kafka"),
    ("spring boot",     normalize_skills_list(["spring boot"])[0].canonical,  "Spring Boot"),
    ("react native",    normalize_skills_list(["react native"])[0].canonical, "React Native"),
    # With whitespace
    (" Python ",        normalize_skills_list([" Python "])[0].canonical,    "Python"),
    # Duplicates deduplicated
    ("py+python dedup", len(canonicalize_skills(["Python","python","PYTHON","py"])), 1),
    ("react dedup",     len(canonicalize_skills(["React","ReactJS","react.js","React 18"])), 1),
    # Empty/junk not included
    ("empty skipped",   len(normalize_skills_list(["", "  ", None])), 0),
    # Level extraction
    ("Go (Expert) level", normalize_skills_list(["Go (Expert)"])[0].level,   "Expert"),
    ("Java (Beginner)",   normalize_skills_list(["Java (Beginner)"])[0].level, "Beginner"),
])


# ── GPA NORMALIZER STRESS ─────────────────────────────────────────────────
suite("GPA normalizer stress", [
    # Standard cases
    ("9.2/10 valid",      normalize_gpa("9.2/10").is_valid,      True),
    ("3.8/4 valid",       normalize_gpa("3.8/4").is_valid,       True),
    ("85% valid",         normalize_gpa("85%").is_valid,         True),
    ("A+ valid",          normalize_gpa("A+").is_valid,          True),
    ("Distinction valid", normalize_gpa("Distinction").is_valid, True),
    # Edge extremes
    ("0/10 pct",          normalize_gpa("0/10").percentage,      0.0),
    ("10/10 valid",       normalize_gpa("10/10").is_valid,       True),
    ("100% valid",        normalize_gpa("100%").is_valid,        True),
    # Invalids
    ("empty invalid",     normalize_gpa("").is_valid,            False),
    ("garbage invalid",   normalize_gpa("xyz").is_valid,         False),
    ("alpha invalid",     normalize_gpa("abc def").is_valid,     False),
    # Scale detection
    ("9.2/10 scale",      normalize_gpa("9.2/10").scale,        "cgpa_10"),
    ("3.8/4.0 scale",     normalize_gpa("3.8/4.0").scale,       "gpa_4"),
    ("87% scale",         normalize_gpa("87%").scale,            "percentage"),
    ("A scale",           normalize_gpa("A").scale,              "letter"),
    ("First Class scale", normalize_gpa("First Class").scale,    "class"),
    # Tri-scale consistency (gpa_4 → pct → cgpa_10 should be consistent)
    ("3.8/4 has pct",     normalize_gpa("3.8/4.0").percentage is not None, True),
    ("3.8/4 has cgpa",    normalize_gpa("3.8/4.0").cgpa_10 is not None,   True),
    ("9.2/10 has gpa4",   normalize_gpa("9.2/10").gpa_4 is not None,      True),
])


# ── TIMELINE VALIDATOR STRESS ─────────────────────────────────────────────
tv = TimelineValidator()

def tv_ok(exp, notes=""):
    r = tv.validate(exp)
    return r.is_consistent

def tv_errors(exp):
    r = tv.validate(exp)
    return len(r.errors)

# Profiles for timeline tests
prof_future = ResumeProfile(personal_info=PersonalInfo(),
    experience=[ExperienceEntry(company="X", title="Y",
                               date_range=DateRange(start="Jan 2035", is_current=True))])
prof_reversed = ResumeProfile(personal_info=PersonalInfo(),
    experience=[ExperienceEntry(company="X", title="Y",
                               date_range=DateRange(start="Jan 2023", end="Jan 2020"))])
prof_valid = ResumeProfile(personal_info=PersonalInfo(),
    experience=[ExperienceEntry(company="G", title="E",
                               date_range=DateRange(start="Jan 2020", is_current=True))])
prof_empty = ResumeProfile(personal_info=PersonalInfo())

suite("Timeline validator stress", [
    ("future start is error",       tv_errors(prof_future) > 0,   True),
    ("future not consistent",       tv_ok(prof_future),           False),
    ("reversed dates error",        tv_errors(prof_reversed) > 0, True),
    ("reversed not consistent",     tv_ok(prof_reversed),         False),
    ("valid dates consistent",      tv_ok(prof_valid),            True),
    ("empty profile consistent",    tv_ok(prof_empty),            True),
])


# ── BULLET QUALITY STRESS ─────────────────────────────────────────────────
suite("Bullet quality stress", [
    # Strong bullets
    ("architected+metric strong",
     _analyze_bullet("Architected distributed cache reducing latency by 60% for 10M users").score > 0.7, True),
    ("built+number strong",
     _analyze_bullet("Built REST API serving 2M+ requests/day with 99.9% uptime").score > 0.6, True),
    ("led+number strong",
     _analyze_bullet("Led team of 12 engineers delivering product 3 months ahead of schedule").score > 0.5, True),
    # Weak bullets
    ("responsible for weak",
     _analyze_bullet("Responsible for backend development tasks").score < 0.4, True),
    ("helped with weak",
     _analyze_bullet("Helped with code reviews and testing").score < 0.4, True),
    # Short bullet is weak
    ("too short weak",
     _analyze_bullet("Python development").score < 0.4, True),
    # Action verb detection
    ("architected has action",      _analyze_bullet("Architected microservices on AWS").has_action_verb, True),
    ("developed has action",        _analyze_bullet("Developed React dashboard").has_action_verb,        True),
    ("responsible no action",       _analyze_bullet("Responsible for testing").has_action_verb,          False),
    # Metric detection
    ("percent has metric",          _analyze_bullet("Reduced errors by 40%").has_metric,                True),
    ("dollar has metric",           _analyze_bullet("Saved $2M in infrastructure costs").has_metric,    True),
    ("million has metric",          _analyze_bullet("Serves 50M daily users").has_metric,               True),
    ("no metric",                   _analyze_bullet("Built authentication system").has_metric,           False),
])


# ── PII ANONYMIZER STRESS ─────────────────────────────────────────────────
anon = PIIAnonymizer()

def make_profile(name=None, email=None, phone=None):
    return ResumeProfile(personal_info=PersonalInfo(name=name, email=email, phone=phone))

suite("PII anonymizer stress", [
    # MASK mode
    ("mask name",      anon.anonymize(make_profile("John Smith")).profile.personal_info.name,   "[NAME]"),
    ("mask email",     anon.anonymize(make_profile(email="j@g.com")).profile.personal_info.email, "[EMAIL]"),
    ("mask phone",     anon.anonymize(make_profile(phone="+91-9876")).profile.personal_info.phone, "[PHONE]"),
    # PSEUDONYM mode
    ("pseudo 2-part",  anon.anonymize(make_profile("John Smith"), AnonymizeMode.PSEUDONYM).profile.personal_info.name, "J.S."),
    ("pseudo 3-part",  anon.anonymize(make_profile("Rahul Kumar Sharma"), AnonymizeMode.PSEUDONYM).profile.personal_info.name, "R.K.S."),
    # PARTIAL mode
    ("partial has star", "*" in (anon.anonymize(make_profile("Rahul Sharma"), AnonymizeMode.PARTIAL).profile.personal_info.name or ""), True),
    ("partial keeps R",  anon.anonymize(make_profile("Rahul Sharma"), AnonymizeMode.PARTIAL).profile.personal_info.name[0], "R"),
    # None fields not crashed
    ("none name ok",   anon.anonymize(make_profile()).profile.personal_info.name,   None),
    ("none email ok",  anon.anonymize(make_profile()).profile.personal_info.email,  None),
    # Fields masked list
    ("masked fields",  "name" in anon.anonymize(make_profile("A B")).fields_masked, True),
    # Redact mode
    ("redact name",    anon.anonymize(make_profile("John Smith"), AnonymizeMode.REDACT).profile.personal_info.name, "***"),
])


# ── EXTREME RESUME FORMATS ────────────────────────────────────────────────
# Format: skills only, no experience
R_SKILLS_ONLY = parser.parse([
    'Alice Chen',
    'alice@gmail.com',
    'Technical Skills',
    'Python, TensorFlow, PyTorch, scikit-learn',
    'Docker, Kubernetes, AWS',
    'PostgreSQL, MongoDB, Redis',
], [])
suite("Skills-only profile", [
    ("name",        R_SKILLS_ONLY.personal_info.name,  "Alice Chen"),
    ("email",       R_SKILLS_ONLY.personal_info.email, "alice@gmail.com"),
    ("skills>=8",   len(R_SKILLS_ONLY.skills) >= 8,    True),
    ("no exp",      len(R_SKILLS_ONLY.experience),     0),
    ("no edu",      len(R_SKILLS_ONLY.education),      0),
])

# Format: education heavy (PhD student)
R_PHD = parser.parse([
    'Arjun Patel',
    'arjun@mit.edu | +1-617-555-0142 | Cambridge, MA',
    'EDUCATION',
    'Massachusetts Institute of Technology',
    'Ph.D. in Computer Science',
    '2020 - Present',
    'GPA: 4.0 / 4.0',
    'Thesis: Efficient attention mechanisms for long-context transformers',
    'Indian Institute of Technology Bombay',
    'B.Tech in Computer Science and Engineering',
    '2016 - 2020',
    'CGPA: 9.8 / 10',
    'RESEARCH EXPERIENCE',
    'MIT CSAIL',
    'Research Assistant',
    'Jan 2020 - Present',
    '- Developed novel attention architecture achieving SOTA on 5 benchmarks',
    '- Published 2 papers at NeurIPS 2022 and ICLR 2023',
    'SKILLS',
    'Python, PyTorch, JAX, CUDA, C++, Transformers, BERT, GPT',
    'PUBLICATIONS',
    '- Efficient Long-Context Attention - NeurIPS 2022',
    '- Sparse Transformers for NLP - ICLR 2023',
], ['https://arjun.mit.edu'])
suite("PhD student profile", [
    ("name",         R_PHD.personal_info.name,                    "Arjun Patel"),
    ("email",        R_PHD.personal_info.email,                   "arjun@mit.edu"),
    ("location",     R_PHD.personal_info.location,                "Cambridge, MA"),
    ("edu_count",    len(R_PHD.education),                        2),
    ("edu1_inst",    R_PHD.education[0].institution,              "Massachusetts Institute of Technology"),
    ("edu1_degree",  R_PHD.education[0].degree,                   "Ph.D."),
    ("edu1_fos",     R_PHD.education[0].field_of_study,           "Computer Science"),
    ("edu1_gpa",     R_PHD.education[0].gpa,                      "4.0 / 4.0"),
    ("edu2_inst",    R_PHD.education[1].institution,              "Indian Institute of Technology Bombay"),
    ("edu2_gpa",     R_PHD.education[1].gpa,                      "9.8 / 10"),
    ("exp_count",    len(R_PHD.experience),                       1),
    ("exp_co",       R_PHD.experience[0].company,                 "MIT CSAIL"),
    ("exp_bullets",  len(R_PHD.experience[0].bullets),            2),
    ("skills>=5",    len(R_PHD.skills) >= 5,                      True),
    ("pubs>=2",      len(R_PHD.awards) >= 2,                      True),
])

# Format: no personal info at all (skills + projects only)
R_ANON = parser.parse([
    'TECHNICAL SKILLS',
    'Languages: Python, Java, Go',
    'Frameworks: FastAPI, Django, Spring Boot',
    'PROJECTS',
    'Smart Cache System',
    'Jan 2024 - Mar 2024',
    '• LRU cache with O(1) operations, benchmarked 3x faster than Redis',
    'ML Pipeline',
    '• End-to-end training pipeline for text classification',
], [])
suite("Anonymous profile (no PII)", [
    ("no name",      R_ANON.personal_info.name,  None),
    ("no email",     R_ANON.personal_info.email, None),
    ("skills>=5",    len(R_ANON.skills) >= 5,    True),
    ("proj_count",   len(R_ANON.projects),       2),
    ("proj1_name",   R_ANON.projects[0].name,    "Smart Cache System"),
])

# Format: Unicode heavy (accented names, special chars)
R_UNICODE = parser.parse([
    'José García López',
    'jose.garcia@universidad.es',
    '+34 612 345 678',
    'Madrid, España',
    'EXPERIENCIA',
    'Google España',
    'Ingeniero de Software Senior',
    'Enero 2021 - Presente',
    '• Desarrolló sistema de recomendaciones mejorando CTR en 25%',
    'EDUCACIÓN',
    'Universidad Politécnica de Madrid',
    'Grado en Ingeniería Informática',
    '2014 - 2018',
    'HABILIDADES',
    'Python, JavaScript, React, Docker, Kubernetes, AWS',
], [])
suite("Unicode/Spanish profile", [
    ("name",         R_UNICODE.personal_info.name,  "José García López"),
    ("email",        R_UNICODE.personal_info.email, "jose.garcia@universidad.es"),
    ("skills>=5",    len(R_UNICODE.skills) >= 5,    True),
    ("exp_count",    len(R_UNICODE.experience),     1),
    ("edu_count",    len(R_UNICODE.education),      1),
])


# ── CAREER INTELLIGENCE STRESS ────────────────────────────────────────────
from resume_segmentation.services.career_intelligence import CareerLevel, TechDomain
ci_analyzer = CareerIntelligenceAnalyzer()

def make_exp_profile(title, company, years_ago, is_current=True):
    from datetime import date
    start_year = date.today().year - years_ago
    return ResumeProfile(
        personal_info=PersonalInfo(),
        skills=["Python", "AWS"],
        experience=[ExperienceEntry(company=company, title=title,
                                   date_range=DateRange(start=f"Jan {start_year}", is_current=is_current))]
    )

suite("Career level detection", [
    ("intern level",      ci_analyzer.analyze(make_exp_profile("Software Intern", "TCS", 0)).career_level, CareerLevel.FRESHER),
    ("junior level",      ci_analyzer.analyze(make_exp_profile("Junior Developer", "Infosys", 2)).career_level, CareerLevel.JUNIOR),
    ("senior level",      ci_analyzer.analyze(make_exp_profile("Senior Engineer", "Google", 7)).career_level, CareerLevel.SENIOR),
    ("principal level",   ci_analyzer.analyze(make_exp_profile("Principal Engineer", "Amazon", 11)).career_level, CareerLevel.PRINCIPAL),
    ("director level",    ci_analyzer.analyze(make_exp_profile("Engineering Director", "Meta", 16)).career_level, CareerLevel.EXECUTIVE),
])


# ── FINAL SUMMARY ──────────────────────────────────────────────────────────
print()
pct = 100 * GRAND_OK // GRAND_T
bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
print("══════════════════════════════════════════")
print(f"  STRESS TESTS: {GRAND_OK}/{GRAND_T}  ({pct}%)")
print(f"  [{bar}]")
print("══════════════════════════════════════════")
