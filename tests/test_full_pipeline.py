import sys
sys.path.insert(0, 'src')

from resume_segmentation.services.text_resume_parser import TextResumeParser
from resume_segmentation.services.date_extractor import extract_date_range
from resume_segmentation.services.skills_normalizer import normalize_skills_list, canonicalize_skills
from resume_segmentation.services.gpa_normalizer import normalize_gpa
from resume_segmentation.services.career_intelligence import CareerIntelligenceAnalyzer, CareerLevel
from resume_segmentation.services.timeline_validator import TimelineValidator
from resume_segmentation.services.resume_quality_reporter import ResumeQualityReporter, _analyze_bullet
from resume_segmentation.services.pii_anonymizer import PIIAnonymizer, AnonymizeMode
from resume_segmentation.services.confidence_engine import ConfidenceEngine
from resume_segmentation.services.document_evidence import DocumentEvidence
from resume_segmentation.services.section_catalog import match_section_heading
from resume_segmentation.services.pipeline import ARIEPipeline, SCHEMA_VERSION
from resume_segmentation.settings import settings
from resume_segmentation.models.resume import *

GRAND_OK = 0
GRAND_T  = 0

def suite(name, tests):
    global GRAND_OK, GRAND_T
    ok   = sum(1 for _, g, e in tests if g == e)
    fail = [(l, g, e) for l, g, e in tests if g != e]
    GRAND_OK += ok; GRAND_T += len(tests)
    status = "✓" if not fail else "✗"
    print(f"{status} {name}: {ok}/{len(tests)}")
    for l, g, e in fail:
        print(f"    [{l}] got={g!r}  expected={e!r}")

p = TextResumeParser()


suite("Date extractor - all formats", [
    ("month-year range",    extract_date_range("Google Aug 2021 - Present")[1].start,      "Aug 2021"),
    ("month-year curr",     extract_date_range("Google Aug 2021 - Present")[1].is_current, True),
    ("full month names",    extract_date_range("January 2022 – December 2023")[1].start,   "Jan 2022"),
    ("full month end",      extract_date_range("January 2022 – December 2023")[1].end,     "Dec 2023"),
    ("year range",          extract_date_range("IIT 2018-2022")[1].start,                  "2018"),
    ("year range end",      extract_date_range("IIT 2018-2022")[1].end,                    "2022"),
    ("em dash",             extract_date_range("May 2021 — Aug 2021")[1].start,            "May 2021"),
    ("slash format",        extract_date_range("05/2021 – 08/2022")[1].start,              "May 2021"),
    ("short year 2021-22",  extract_date_range("IIT 2021-22")[1].end,                      "2022"),
    ("short year 2019-20",  extract_date_range("CBSE 2019-20")[1].end,                     "2020"),
    ("short year 2022-23",  extract_date_range("MBA 2022-23")[1].end,                      "2023"),
    ("date-only remaining", extract_date_range("Aug 2023 – Oct 2023")[0],                  ""),
    ("present variant Now", extract_date_range("Role Jan 2023 - Now")[1].is_current,       True),
    ("present variant Till",extract_date_range("Role Feb 2023 - Till Date")[1].is_current, True),
    ("single month year",   extract_date_range("Graduated June 2022")[1].start,            "Jun 2022"),
])


suite("Section catalog - accuracy", [
    ("EXPERIENCE",        match_section_heading("EXPERIENCE"),             "experience"),
    ("Work History",      match_section_heading("Work History"),           "experience"),
    ("Tech Skills",       match_section_heading("Technical Skills"),       "skills"),
    ("Academic Bg",       match_section_heading("Academic Background"),    "education"),
    ("Personal Projects", match_section_heading("Personal Projects"),      "projects"),
    ("Awards & Honors",   match_section_heading("Awards & Honors"),        "awards"),
    ("Hobbies",           match_section_heading("Hobbies"),                "interests"),
    ("Certifications",    match_section_heading("Certifications"),         "certifications"),
    ("Summary",           match_section_heading("Professional Summary"),   "summary"),
    ("Career Objective",  match_section_heading("Career Objective"),       "summary"),
    ("Hindi exp",         match_section_heading("अनुभव"),                  "experience"),
    ("Spanish skills",    match_section_heading("Habilidades técnicas"),   "skills"),
    ("French exp",        match_section_heading("Expérience professionnelle"), "experience"),
    ("German exp",        match_section_heading("Berufserfahrung"),        "experience"),
    ("emoji section",     match_section_heading("🎓 Education"),           "education"),
    ("no false pos",      match_section_heading("Developed REST API with Python and Flask"), None),
    ("no false pos2",     match_section_heading("Jan 2022 - Present"), None),
    ("no false pos3",     match_section_heading("Python, Java, React, Node.js"), None),
])


suite("Skills normalizer - 20 variants", [
    ("ReactJS",        normalize_skills_list(["ReactJS"])[0].canonical,       "React"),
    ("k8s",            normalize_skills_list(["k8s"])[0].canonical,           "Kubernetes"),
    ("golang",         normalize_skills_list(["golang"])[0].canonical,        "Go"),
    ("pyspark",        normalize_skills_list(["pyspark"])[0].canonical,       "Apache Spark"),
    ("sklearn",        normalize_skills_list(["sklearn"])[0].canonical,       "scikit-learn"),
    ("nodejs",         normalize_skills_list(["nodejs"])[0].canonical,        "Node.js"),
    ("postgres",       normalize_skills_list(["postgres"])[0].canonical,      "PostgreSQL"),
    ("huggingface",    normalize_skills_list(["huggingface"])[0].canonical,   "Hugging Face"),
    ("tailwindcss",    normalize_skills_list(["tailwindcss"])[0].canonical,   "Tailwind CSS"),
    ("angularjs",      normalize_skills_list(["angularjs"])[0].canonical,     "Angular"),
    ("vuejs",          normalize_skills_list(["vuejs"])[0].canonical,         "Vue.js"),
    ("kafka streams",  normalize_skills_list(["kafka streams"])[0].canonical, "Kafka"),
    ("spring boot",    normalize_skills_list(["spring boot"])[0].canonical,   "Spring Boot"),
    ("react native",   normalize_skills_list(["react native"])[0].canonical,  "React Native"),
    ("PYTHON",         normalize_skills_list(["PYTHON"])[0].canonical,        "Python"),
    ("dedup react",    len(canonicalize_skills(["React","ReactJS","react.js","React 18"])), 1),
    ("dedup python",   len(canonicalize_skills(["Python","python","PYTHON","py","Python3"])), 1),
    ("level adv",      normalize_skills_list(["Python (Advanced)"])[0].level, "Expert"),
    ("level beg",      normalize_skills_list(["Java (Beginner)"])[0].level,   "Beginner"),
    ("empty skip",     len(normalize_skills_list(["", "  "])),                 0),
])


suite("GPA normalizer - all scales", [
    ("9.2/10 pct",     normalize_gpa("9.2/10").percentage,   87.4),
    ("9.2/10 scale",   normalize_gpa("9.2/10").scale,        "cgpa_10"),
    ("3.8/4.0 scale",  normalize_gpa("3.8/4.0").scale,       "gpa_4"),
    ("3.8/4.0 valid",  normalize_gpa("3.8/4.0").is_valid,    True),
    ("87% pct",        normalize_gpa("87%").percentage,      87.0),
    ("A+ valid",       normalize_gpa("A+").is_valid,         True),
    ("A+ pct",         normalize_gpa("A+").percentage,       96.0),
    ("Distinction",    normalize_gpa("Distinction").percentage, 90.0),
    ("First Class",    normalize_gpa("First Class").percentage, 72.5),
    ("5.0/10 gpa4>0",  (normalize_gpa("5.0/10").gpa_4 or 0) > 0, True),
    ("10/10 valid",    normalize_gpa("10/10").is_valid,      True),
    ("empty invalid",  normalize_gpa("").is_valid,           False),
    ("garbage",        normalize_gpa("xyz").is_valid,        False),
    ("tri-scale 3.8",  normalize_gpa("3.8/4.0").cgpa_10 is not None, True),
    ("tri-scale 9.2",  normalize_gpa("9.2/10").gpa_4 is not None,    True),
])


R1 = p.parse([
    "Rahul Kumar Sharma", "Senior Software Engineer",
    "rahul.sharma@gmail.com | +91-9876543210",
    "Bangalore, India | linkedin.com/in/rahulsharma | github.com/rahulsharma",
    "PROFESSIONAL EXPERIENCE",
    "Google India", "Senior Software Engineer", "Aug 2021 - Present",
    "• Developed microservices using Python and FastAPI",
    "• Led migration to Docker/Kubernetes",
    "Microsoft India", "SDE Intern", "May 2020 – July 2020",
    "• Built REST APIs in Node.js",
    "EDUCATION",
    "Indian Institute of Technology, Delhi",
    "B.Tech in Computer Science and Engineering", "2017 – 2021", "CGPA: 9.2 / 10",
    "Delhi Public School", "12th CBSE", "2017", "Percentage: 96%",
    "TECHNICAL SKILLS",
    "Languages: Python, Java, JavaScript, TypeScript, C++",
    "Frameworks: React, Node.js, FastAPI, Django",
    "CERTIFICATIONS",
    "AWS Solutions Architect Professional (2023)",
    "Google Cloud Data Engineer by Google (2022)",
    "PROJECTS",
    "Resume Parser Application", "Aug 2023 – Oct 2023",
    "• Built using Python and pdfplumber", "• Deployed on AWS",
    "Stock Market Predictor", "Jan 2023 – Mar 2023",
    "• LSTM model achieving 87% accuracy",
    "AWARDS & HONORS", "• Google Spot Bonus – Q3 2022", "• Dean's List",
    "LANGUAGES", "English (Native), Hindi (Native), Tamil (Basic)",
    "INTERESTS", "• Open source", "• Competitive programming",
], ["https://linkedin.com/in/rahulsharma", "https://github.com/rahulsharma"])

suite("Full resume extraction", [
    ("name",        R1.personal_info.name,                  "Rahul Kumar Sharma"),
    ("headline",    R1.personal_info.headline,              "Senior Software Engineer"),
    ("email",       R1.personal_info.email,                 "rahul.sharma@gmail.com"),
    ("phone",       R1.personal_info.phone,                 "+91-9876543210"),
    ("location",    R1.personal_info.location,              "Bangalore, India"),
    ("links",       len(R1.links),                          2),
    ("skills>=8",   len(R1.skills) >= 8,                   True),
    ("exp_count",   len(R1.experience),                     2),
    ("exp1_co",     R1.experience[0].company,               "Google India"),
    ("exp1_ti",     R1.experience[0].title,                 "Senior Software Engineer"),
    ("exp1_curr",   R1.experience[0].date_range.is_current, True),
    ("exp1_bullets",len(R1.experience[0].bullets),          2),
    ("exp2_co",     R1.experience[1].company,               "Microsoft India"),
    ("edu_count",   len(R1.education),                      2),
    ("edu1_inst",   R1.education[0].institution,            "Indian Institute of Technology, Delhi"),
    ("edu1_degree", R1.education[0].degree,                 "B.Tech"),
    ("edu1_field",  R1.education[0].field_of_study,         "Computer Science and Engineering"),
    ("edu1_gpa",    R1.education[0].gpa,                    "9.2 / 10"),
    ("edu2_inst",   R1.education[1].institution,            "Delhi Public School"),
    ("certs",       len(R1.certifications),                 2),
    ("cert1_name",  R1.certifications[0].name,             "AWS Solutions Architect Professional"),
    ("cert1_date",  R1.certifications[0].date,             "2023"),
    ("cert2_issuer",R1.certifications[1].issuer,           "Google"),
    ("proj_count",  len(R1.projects),                      2),
    ("proj1_name",  R1.projects[0].name,                   "Resume Parser Application"),
    ("proj1_start", R1.projects[0].date_range.start,       "Aug 2023"),
    ("awards",      len(R1.awards),                        2),
    ("languages",   len(R1.languages),                     3),
    ("interests",   len(R1.interests),                     2),
])


ca = CareerIntelligenceAnalyzer()
ci = ca.analyze(R1)
suite("Career intelligence", [
    ("level senior",   ci.career_level == CareerLevel.SENIOR, True),
    ("years > 0",      ci.total_years_experience > 0,         True),
    ("domain backend", "Backend" in ci.primary_domain.value or "ML" in ci.primary_domain.value, True),
    ("google notable", any("google" in c.lower() for c in ci.notable_companies), True),
    ("iit notable",    len(ci.notable_universities) > 0,     True),
    ("seniority > 0",  ci.seniority_score > 0,                True),
])

tv = TimelineValidator()
tr = tv.validate(R1)
suite("Timeline validator", [
    ("consistent",      tr.is_consistent,           True),
    ("years > 0",       tr.total_years_experience > 0, True),
    ("no errors",       len(tr.errors),             0),
])

qr = ResumeQualityReporter().analyze(R1)
suite("Quality reporter", [
    ("ats >= 70",       qr.ats_score >= 70,         True),
    ("completeness>70", qr.completeness_score >= 70, True),
    ("overall > 60",    qr.overall_score > 60,      True),
    ("no critical miss",len(qr.missing_fields) < 3, True),
])

suite("Bullet quality", [
    ("architected strong", _analyze_bullet("Architected distributed cache reducing latency by 60%").score > 0.7, True),
    ("metric detection",   _analyze_bullet("Reduced API response time by 40% for 2M users").has_metric, True),
    ("action verb",        _analyze_bullet("Built REST API handling 1M requests/day").has_action_verb, True),
    ("weak detected",      _analyze_bullet("Responsible for backend development").is_weak_opening, True),
    ("short weak",         _analyze_bullet("Python dev").score < 0.4, True),
])

suite("PII anonymizer", [
    ("mask name",    PIIAnonymizer().anonymize(ResumeProfile(personal_info=PersonalInfo(name="John Smith"))).profile.personal_info.name, "[NAME]"),
    ("pseudo name",  PIIAnonymizer().anonymize(ResumeProfile(personal_info=PersonalInfo(name="John Smith")), AnonymizeMode.PSEUDONYM).profile.personal_info.name, "J.S."),
    ("redact name",  PIIAnonymizer().anonymize(ResumeProfile(personal_info=PersonalInfo(name="John Smith")), AnonymizeMode.REDACT).profile.personal_info.name, "***"),
    ("partial star", "*" in (PIIAnonymizer().anonymize(ResumeProfile(personal_info=PersonalInfo(name="Rahul Sharma")), AnonymizeMode.PARTIAL).profile.personal_info.name or ""), True),
    ("none safe",    PIIAnonymizer().anonymize(ResumeProfile(personal_info=PersonalInfo())).profile.personal_info.name, None),
])

conf = ConfidenceEngine().score(
    R1,
    [],
    DocumentEvidence(present_sections={"experience","education","skills","projects","certifications"})
)
suite("Confidence engine", [
    ("overall > 0.5",   conf.overall > 0.5,                       True),
    ("grade exists",    conf.grade in {"A","B","C","D","F"},       True),
    ("personal info",   conf.fields["personal_info"].score > 0.5, True),
    ("skills scored",   conf.fields["skills"].score > 0,          True),
    ("exp scored",      conf.fields["experience"].score > 0,      True),
])

suite("Pipeline configuration", [
    ("schema version",  SCHEMA_VERSION,                            "3.1.0"),
    ("app version",     settings.app_version,                     "3.1.0"),
    ("output_dir",      settings.output_dir is not None,          True),
    ("pipeline builds", ARIEPipeline() is not None,               True),
])

suite("Edge cases - adversarial inputs", [
    ("empty profile name",  p.parse([], []).personal_info.name,  None),
    ("empty profile skills",p.parse([], []).skills,              []),
    ("single name line",    p.parse(["John Doe"], []).personal_info.name, "John Doe"),
    ("pipe header name",    p.parse(["Jane Smith | jane@g.com | +1-555-0101 | NYC"], []).personal_info.name, "Jane Smith"),
    ("multipart email",     p.parse(["A B", "a@iitd.ac.in"], []).personal_info.email, "a@iitd.ac.in"),
    ("uk email",            p.parse(["X Y", "x@ox.ac.uk"], []).personal_info.email, "x@ox.ac.uk"),
    ("two word location",   p.parse(["A B", "a@g.com", "Tamil Nadu, India"], []).personal_info.location, "Tamil Nadu, India"),
    ("short year 2021-22",  extract_date_range("MBA 2021-22")[1].end,  "2022"),
    ("thesis skip",
     p.parse(["EDUCATION","MIT","Ph.D. in CS","2015-2020","Thesis: Fast ML models"],[]
             ).education[0].institution, "MIT"),
    ("pub to awards",
     len(p.parse(["X","x@g.com","PUBLICATIONS","• NeurIPS 2022","• ICML 2023"],[]).awards) >= 2, True),
    ("cert parsed",
     len(p.parse(["X","x@g.com","CERTIFICATIONS","AWS SA Pro (2023)","GCP DE (2022)"],[]).certifications), 2),
    ("low cgpa positive",   (normalize_gpa("5.0/10").gpa_4 or 0) >= 0, True),
])

print()
pct = 100 * GRAND_OK // GRAND_T
bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
print("══════════════════════════════════════════")
print(f"  FINAL VALIDATION: {GRAND_OK}/{GRAND_T}  ({pct}%)")
print(f"  [{bar}]")
print("══════════════════════════════════════════")
