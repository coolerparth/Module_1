"""
test_world_class.py — Tests for all new world-class modules.
Run: cd resume_final && python3 tests/test_world_class.py
"""
import sys
sys.path.insert(0, 'src')

from resume_segmentation.services.skills_normalizer import (
    normalize_skill, normalize_skills_list, group_skills_by_category,
    get_tech_stack_score, canonicalize_skills, SkillCategory,
)
from resume_segmentation.services.multilang_catalog import match_multilang_heading
from resume_segmentation.services.section_catalog import match_section_heading
from resume_segmentation.services.career_intelligence import (
    CareerIntelligenceAnalyzer, CareerLevel, TechDomain,
)
from resume_segmentation.services.confidence_engine import ConfidenceEngine
from resume_segmentation.services.document_evidence import DocumentEvidence
from resume_segmentation.models.resume import (
    ResumeProfile, PersonalInfo, ExperienceEntry, EducationEntry,
    ProjectEntry, DateRange, LinkItem,
)

GRAND_OK = 0
GRAND_T  = 0

def run_suite(name, tests):
    global GRAND_OK, GRAND_T
    ok   = sum(1 for _, g, e in tests if g == e)
    fail = [(l, g, e) for l, g, e in tests if g != e]
    GRAND_OK += ok
    GRAND_T  += len(tests)
    status = "✓ PASS" if not fail else "✗ FAIL"
    print(f"{status}  {name}  ({ok}/{len(tests)})")
    for l, g, e in fail:
        print(f"       [{l}] got={g!r}  expected={e!r}")


# ─── Skills Normalizer ────────────────────────────────────────────────────────
run_suite("Skill variant normalization", [
    ("ReactJS",        normalize_skill("ReactJS").canonical,        "React"),
    ("react.js",       normalize_skill("react.js").canonical,       "React"),
    ("react 18",       normalize_skill("react 18").canonical,       "React"),
    ("k8s",            normalize_skill("k8s").canonical,            "Kubernetes"),
    ("golang",         normalize_skill("golang").canonical,         "Go"),
    ("postgres",       normalize_skill("postgres").canonical,       "PostgreSQL"),
    ("pyspark",        normalize_skill("pyspark").canonical,        "Apache Spark"),
    ("sklearn",        normalize_skill("sklearn").canonical,        "scikit-learn"),
    ("tensorflow 2",   normalize_skill("tensorflow 2").canonical,   "TensorFlow"),
    ("nodejs",         normalize_skill("nodejs").canonical,         "Node.js"),
    ("angularjs",      normalize_skill("angularjs").canonical,      "Angular"),
    ("vuejs",          normalize_skill("vuejs").canonical,          "Vue.js"),
    ("docker compose", normalize_skill("docker compose").canonical, "Docker"),
    ("kafka streams",  normalize_skill("kafka streams").canonical,  "Kafka"),
    ("drf",            normalize_skill("drf").canonical,            "Django"),
    ("gh actions",     normalize_skill("gh actions").canonical,     "GitHub Actions"),
    ("t-sql",          normalize_skill("t-sql").canonical,          "SQL"),
    ("huggingface",    normalize_skill("huggingface").canonical,    "Hugging Face"),
    ("tailwindcss",    normalize_skill("tailwindcss").canonical,    "Tailwind CSS"),
    ("dynamodb",       normalize_skill("dynamodb").canonical,       "DynamoDB"),
])

run_suite("Skill level detection", [
    ("Python level",   normalize_skill("Python (Advanced)").level,  "Expert"),
    ("Java level",     normalize_skill("Java (Beginner)").level,    "Beginner"),
    ("Go level",       normalize_skill("Go - Proficient").level,    "Proficient"),
    ("no level",       normalize_skill("React").level,              None),
])

run_suite("Skill categories", [
    ("React category",   normalize_skill("React").category,         SkillCategory.FRONTEND),
    ("Python category",  normalize_skill("Python").category,        SkillCategory.LANGUAGE),
    ("Docker category",  normalize_skill("Docker").category,        SkillCategory.CLOUD),
    ("PyTorch category", normalize_skill("PyTorch").category,       SkillCategory.ML_AI),
    ("Spark category",   normalize_skill("Apache Spark").category,  SkillCategory.DATA),
    ("Flutter category", normalize_skill("Flutter").category,       SkillCategory.MOBILE),
    ("Pytest category",  normalize_skill("Pytest").category,        SkillCategory.TESTING),
    ("MySQL category",   normalize_skill("MySQL").category,         SkillCategory.DATABASE),
])

# Deduplication test
skills_raw = ["React", "ReactJS", "react.js", "Python", "python3", "k8s", "Kubernetes"]
canonical = canonicalize_skills(skills_raw)
run_suite("Skill deduplication", [
    ("react deduped",      canonical.count("React"),      1),
    ("python deduped",     canonical.count("Python"),     1),
    ("k8s deduped",        canonical.count("Kubernetes"), 1),
    ("total after dedup",  len(canonical),                3),
])

# Tech stack score
strong_stack = ["Python", "TensorFlow", "PyTorch", "Docker", "AWS", "PostgreSQL",
                "React", "Node.js", "Kafka", "Kubernetes", "GraphQL"]
weak_stack = ["MS Office", "Email", "Communication", "Teamwork"]
run_suite("Tech stack scoring", [
    ("strong stack > 0.7", get_tech_stack_score(strong_stack) > 0.7, True),
    ("weak stack < 0.4",   get_tech_stack_score(weak_stack) < 0.4,   True),
    ("empty stack = 0",    get_tech_stack_score([]),                   0.0),
])

# ─── Multilingual Catalog ─────────────────────────────────────────────────────
run_suite("Multilingual section headings", [
    ("Hindi Devanagari exp",  match_section_heading("अनुभव"),                    "experience"),
    ("Hindi Devanagari edu",  match_section_heading("शिक्षा"),                    "education"),
    ("Hindi Devanagari skills",match_section_heading("कौशल"),                     "skills"),
    ("Hindi Devanagari proj", match_section_heading("परियोजनाएं"),               "projects"),
    ("Hindi romanized edu",   match_section_heading("shiksha"),                  "education"),
    ("Spanish exp",           match_section_heading("Experiencia profesional"),   "experience"),
    ("Spanish skills",        match_section_heading("Habilidades técnicas"),      "skills"),
    ("Spanish edu",           match_section_heading("Educación"),                 "education"),
    ("Spanish proj",          match_section_heading("Proyectos"),                 "projects"),
    ("Spanish lang",          match_section_heading("Idiomas"),                   "languages"),
    ("French exp",            match_section_heading("Expérience professionnelle"),"experience"),
    ("French skills",         match_section_heading("Compétences techniques"),    "skills"),
    ("French edu",            match_section_heading("Formation"),                 "education"),
    ("German exp",            match_section_heading("Berufserfahrung"),           "experience"),
    ("German edu",            match_section_heading("Ausbildung"),                "education"),
    ("German skills",         match_section_heading("Kenntnisse"),                "skills"),
    ("Portuguese exp",        match_section_heading("Experiência profissional"),  "experience"),
    ("Portuguese skills",     match_section_heading("Competências"),              "skills"),
])

# ─── Career Intelligence ─────────────────────────────────────────────────────
analyzer = CareerIntelligenceAnalyzer()

senior_profile = ResumeProfile(
    personal_info=PersonalInfo(name="Vikram Singh"),
    skills=["Python", "TensorFlow", "PyTorch", "pandas", "NLP", "Docker", "AWS"],
    experience=[
        ExperienceEntry(company="Google", title="Senior ML Engineer",
                        date_range=DateRange(start="Jan 2020", is_current=True)),
        ExperienceEntry(company="Amazon", title="Software Engineer",
                        date_range=DateRange(start="Jul 2017", end="Dec 2019")),
    ],
    education=[EducationEntry(institution="IIT Bombay", degree="M.Tech CS")],
)
ci_senior = analyzer.analyze(senior_profile)

fresher_profile = ResumeProfile(
    personal_info=PersonalInfo(name="Ankit Kumar"),
    skills=["Python", "HTML", "CSS", "JavaScript"],
    experience=[
        ExperienceEntry(company="TechCorp", title="Software Intern",
                        date_range=DateRange(start="Jun 2024", end="Aug 2024")),
    ],
    education=[EducationEntry(institution="NIT Warangal", degree="B.Tech CS",
                               date_range=DateRange(start="2020", end="2024"))],
)
ci_fresher = analyzer.analyze(fresher_profile)

run_suite("Career intelligence", [
    ("senior level",       ci_senior.career_level,              CareerLevel.SENIOR),
    ("senior years > 6",   ci_senior.total_years_experience > 6, True),
    ("senior domain ML",   ci_senior.primary_domain,            TechDomain.ML_AI),
    ("google notable",     "Google" in ci_senior.notable_companies, True),
    ("iit notable",        "IIT Bombay" in ci_senior.notable_universities, True),
    ("senior score > 0.5", ci_senior.seniority_score > 0.5,    True),
    ("fresher level",      ci_fresher.career_level,             CareerLevel.FRESHER),
    ("fresher is_fresher", ci_fresher.is_fresher,               True),
    ("fresher years < 1",  ci_fresher.total_years_experience < 1, True),
])

# ─── Confidence Engine ───────────────────────────────────────────────────────
engine = ConfidenceEngine()
complete_profile = ResumeProfile(
    personal_info=PersonalInfo(
        name="Jane Doe", email="jane@example.com",
        phone="+1-415-555-0192", location="San Francisco, CA",
    ),
    links=[LinkItem(label="LinkedIn", url="https://linkedin.com/in/janedoe"),
           LinkItem(label="GitHub", url="https://github.com/janedoe")],
    skills=["Python", "TensorFlow", "Docker", "AWS", "PostgreSQL", "React"],
    experience=[ExperienceEntry(
        company="Stripe", title="Senior Engineer",
        date_range=DateRange(start="Jan 2021", is_current=True),
        bullets=["Built payment APIs", "Led team of 5", "Reduced latency by 40%"],
    )],
    education=[EducationEntry(institution="Stanford University",
                               degree="B.S. Computer Science",
                               date_range=DateRange(start="2014", end="2018"))],
    projects=[ProjectEntry(name="ML Pipeline", description="Production ML system",
                            technologies=["Python", "TensorFlow"])],
)
evidence_full = DocumentEvidence(
    present_sections={"experience", "education", "skills", "projects", "links"}
)
from resume_segmentation.services.profile_consensus import StrategyResult
mock_results = [
    StrategyResult("s1", complete_profile, {"personal_info": 0.9}, 0.88),
    StrategyResult("s2", complete_profile, {"personal_info": 0.85}, 0.85),
    StrategyResult("s3", complete_profile, {"personal_info": 0.87}, 0.82),
]
conf = engine.score(complete_profile, mock_results, evidence_full)

run_suite("Confidence engine", [
    ("overall > 0.7",          conf.overall > 0.7,                  True),
    ("grade A or B",           conf.grade in {"A", "B"},             True),
    ("personal_info A/B",      conf.fields["personal_info"].grade in {"A","B"}, True),
    ("skills confidence > 0.6",conf.fields["skills"].score > 0.6,   True),
    ("links confidence > 0.8", conf.fields["links"].score > 0.8,    True),
    ("strategy agreement > 0", conf.strategy_agreement > 0,         True),
    ("completeness > 0.8",     conf.completeness > 0.8,             True),
])

# ─── Final Summary ────────────────────────────────────────────────────────────
print()
pct = 100 * GRAND_OK // GRAND_T
bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
print("══════════════════════════════════════════")
print(f"  WORLD-CLASS MODULES: {GRAND_OK}/{GRAND_T}  ({pct}%)")
print(f"  [{bar}]")
print("══════════════════════════════════════════")
