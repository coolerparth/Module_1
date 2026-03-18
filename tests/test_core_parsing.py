"""
master_test_suite.py — Full regression test across 5 resume formats.
Run with: cd resume_segmentation_v2 && python /home/claude/master_test_suite.py
"""
import sys
sys.path.insert(0, 'src')

from resume_segmentation.services.text_resume_parser import TextResumeParser
from resume_segmentation.services.section_catalog import match_section_heading
from resume_segmentation.services.date_extractor import extract_date_range
from resume_segmentation.services.personal_info_extractor import looks_like_name
from resume_segmentation.services.entry_signatures import best_section

parser = TextResumeParser()
GRAND_OK = 0
GRAND_T  = 0

def run_suite(name, profile, tests):
    global GRAND_OK, GRAND_T
    ok   = sum(1 for _, g, e in tests if g == e)
    fail = [(l, g, e) for l, g, e in tests if g != e]
    GRAND_OK += ok
    GRAND_T  += len(tests)
    sc = parser.score(profile)
    status = "✓ PASS" if not fail else "✗ FAIL"
    print(f"{status}  {name}  ({ok}/{len(tests)})  score={sc}/18")
    for l, g, e in fail:
        print(f"       [{l}] got={g!r}  expected={e!r}")


# ─── Section catalog: 43 headings ───────────────────────────────────────────
cat_tests = [
    ("EXPERIENCE", "experience"), ("Work Experience", "experience"),
    ("Employment History", "experience"), ("Career History", "experience"),
    ("Professional Experience", "experience"),
    ("TECHNICAL SKILLS", "skills"), ("Skills & Technologies", "skills"),
    ("Core Competencies", "skills"), ("Areas of Expertise", "skills"),
    ("Academic Background", "education"), ("EDUCATIONAL QUALIFICATIONS", "education"),
    ("PERSONAL PROJECTS", "projects"), ("Academic Projects", "projects"),
    ("AWARDS & HONORS", "awards"), ("Achievements", "awards"), ("Scholarships", "awards"),
    ("Hobbies & Interests", "interests"), ("Extracurricular Activities", "interests"),
    ("CERTIFICATIONS", "certifications"), ("Professional Summary", "summary"),
    ("Career Objective", "summary"), ("About Me", "summary"),
    ("🎯 Professional Summary", "summary"), ("💼 Work Experience", "experience"),
    ("🛠️ Skills", "skills"), ("🎓 Education", "education"),
    ("Experience:", "experience"), ("Education:", "education"), ("Skills:", "skills"),
    ("PROJECTS", "projects"), ("EDUCATION", "education"), ("AWARDS", "awards"),
    ("LANGUAGES", "languages"), ("PUBLICATIONS", "publications"),
    ("VOLUNTEER", "volunteer"), ("REFERENCES", "references"),
    # Should NOT match
    ("I am a software engineer with 5 years of experience", None),
    ("Python, JavaScript, React, Node.js", None),
    ("rahul@gmail.com | +91-9876543210", None),
    ("Jan 2022 - Present", None),
    ("• Developed REST APIs using FastAPI", None),
    ("Google Inc., Bangalore", None),
    ("Built recommendation engine improving CTR by 18%", None),
    ("NLP model with 92% accuracy using BERT fine-tuning", None),
]
cat_ok  = sum(1 for t, e in cat_tests if match_section_heading(t) == e)
cat_fail = [(t, match_section_heading(t), e) for t, e in cat_tests if match_section_heading(t) != e]
GRAND_OK += cat_ok; GRAND_T += len(cat_tests)
print(f"{'✓ PASS' if not cat_fail else '✗ FAIL'}  Section catalog  ({cat_ok}/{len(cat_tests)})")
for t, g, e in cat_fail: print(f"       [{t!r}] got={g!r} expected={e!r}")


# ─── Date extractor: 15 formats ─────────────────────────────────────────────
date_tests = [
    ("Google Aug 2021 - Present",       "Aug 2021", None,       True),
    ("Developer Jan 2022 – December 2023","Jan 2022","Dec 2023", False),
    ("IIT Delhi 2018-2022",             "2018",    "2022",      False),
    ("Google 2020 – 2023",              "2020",    "2023",      False),
    ("Intern May 2021 — Aug 2021",      "May 2021","Aug 2021",  False),
    ("Sept 2021 - May 2022",            "Sep 2021","May 2022",  False),
    ("Sep. 2021 – May 2022",            "Sep 2021","May 2022",  False),
    ("September 2021 – May 2022",       "Sep 2021","May 2022",  False),
    ("Project 05/2021 – 08/2022",       "May 2021","Aug 2022",  False),
    ("Graduated June 2022",             "Jun 2022", None,       False),
    ("Delhi Public School 2017",        "2017",    None,        False),
    ("Google May 2022 - Current",       "May 2022", None,       True),
    ("Intern Jan 2023 - Now",           "Jan 2023", None,       True),
    ("Role Feb 2023 - Till Date",       "Feb 2023", None,       True),
    ("July 2022 – Present",             "Jul 2022", None,       True),
]
dt_ok = 0
for text, exp_s, exp_e, exp_c in date_tests:
    _, dr = extract_date_range(text)
    if dr and dr.start == exp_s and dr.end == exp_e and dr.is_current == exp_c:
        dt_ok += 1
    else:
        print(f"  DATE FAIL [{text!r}] → {dr}  expected start={exp_s!r} end={exp_e!r} curr={exp_c}")
GRAND_OK += dt_ok; GRAND_T += len(date_tests)
print(f"{'✓ PASS' if dt_ok==len(date_tests) else '✗ FAIL'}  Date extractor  ({dt_ok}/{len(date_tests)})")


# ─── Name detection: 7 cases ────────────────────────────────────────────────
name_tests = [
    ("Rahul Kumar Sharma", True), ("John Smith", True), ("Dr. Anjali Verma", True),
    ("python@gmail.com", False), ("Software Engineer", False),
    ("123456789", False), ("A", False),
]
nm_ok = sum(1 for n, e in name_tests if looks_like_name(n) == e)
GRAND_OK += nm_ok; GRAND_T += len(name_tests)
print(f"{'✓ PASS' if nm_ok==len(name_tests) else '✗ FAIL'}  Name detection  ({nm_ok}/{len(name_tests)})")


# ─── Entry signatures: 4 block types ────────────────────────────────────────
sig_tests = [
    (["Python", "JavaScript", "React", "Node.js", "Docker", "AWS", "MySQL"], "skills"),
    (["Google Inc.", "Software Engineer", "Jan 2022 – Present", "• Developed APIs", "• Led team"], "experience"),
    (["IIT Delhi", "B.Tech Computer Science", "2018-2022", "CGPA: 9.0"], "education"),
    (["Resume Parser", "• Built using Python and PyMuPDF", "• Deployed on AWS"], "projects"),
]
sig_ok = sum(1 for lines, exp in sig_tests if best_section(lines)[0] == exp)
GRAND_OK += sig_ok; GRAND_T += len(sig_tests)
print(f"{'✓ PASS' if sig_ok==len(sig_tests) else '✗ FAIL'}  Entry signatures  ({sig_ok}/{len(sig_tests)})")

print()


# ─── Resume 1: Standard bulleted (experienced engineer) ─────────────────────
R1 = parser.parse([
    "Rahul Kumar Sharma", "rahul.sharma@gmail.com | +91-9876543210",
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
    "PROJECTS",
    "Resume Parser Application", "Aug 2023 – Oct 2023",
    "• Built using Python and pdfplumber", "• Deployed on AWS",
    "Stock Market Predictor", "Jan 2023 – Mar 2023",
    "• LSTM model achieving 87% accuracy",
    "AWARDS & HONORS", "• Google Spot Bonus – Q3 2022", "• Dean's List",
    "INTERESTS", "• Open source", "• Competitive programming",
], ["https://linkedin.com/in/rahulsharma", "https://github.com/rahulsharma"])

run_suite("Bulleted experienced", R1, [
    ("name",    R1.personal_info.name, "Rahul Kumar Sharma"),
    ("email",   R1.personal_info.email, "rahul.sharma@gmail.com"),
    ("phone",   R1.personal_info.phone, "+91-9876543210"),
    ("loc",     R1.personal_info.location, "Bangalore, India"),
    ("links",   len(R1.links), 2),
    ("skills",  len(R1.skills) >= 8, True),
    ("exp",     len(R1.experience), 2),
    ("exp1_co", R1.experience[0].company, "Google India"),
    ("exp1_ti", R1.experience[0].title, "Senior Software Engineer"),
    ("exp1_cu", R1.experience[0].date_range.is_current, True),
    ("exp1_bt", len(R1.experience[0].bullets), 2),
    ("exp2_co", R1.experience[1].company, "Microsoft India"),
    ("edu",     len(R1.education), 2),
    ("edu1_in", R1.education[0].institution, "Indian Institute of Technology, Delhi"),
    ("edu1_dg", R1.education[0].degree, "B.Tech"),
    ("edu1_fi", R1.education[0].field_of_study, "Computer Science and Engineering"),
    ("edu1_gpa",R1.education[0].gpa, "9.2 / 10"),
    ("edu2_in", R1.education[1].institution, "Delhi Public School"),
    ("proj",    len(R1.projects), 2),
    ("proj1",   R1.projects[0].name, "Resume Parser Application"),
    ("proj1_dt",R1.projects[0].date_range.start, "Aug 2023"),
    ("proj2",   R1.projects[1].name, "Stock Market Predictor"),
    ("awards",  len(R1.awards), 2),
    ("intsts",  len(R1.interests), 2),
])


# ─── Resume 2: Compact, pipe-separated skills, no bullets ───────────────────
R2 = parser.parse([
    "Priya Nair", "priya.nair@outlook.com", "+91 8765432109", "Kochi, Kerala",
    "Skills",
    "Python | R | TensorFlow | PyTorch | Pandas | NumPy | Scikit-Learn",
    "SQL | MySQL | PostgreSQL | MongoDB", "AWS | GCP | Docker | Kubernetes | Git",
    "Education",
    "National Institute of Technology, Calicut", "M.Tech Data Science",
    "2020 – 2022", "CGPA: 8.9",
    "University of Kerala", "B.Sc Mathematics", "2017 – 2020", "CGPA: 9.1",
    "Experience",
    "Amazon India", "Data Scientist", "July 2022 – Present",
    "Built recommendation engine improving CTR by 18%",
    "Projects",
    "Fake News Detector", "January 2022 – April 2022",
    "NLP model with 92% accuracy using BERT fine-tuning",
    "Awards", "Best Thesis Award – NIT Calicut 2022", "Hackathon – 2nd Place 2021",
], [])

run_suite("Compact no-bullets", R2, [
    ("name",  R2.personal_info.name, "Priya Nair"),
    ("email", R2.personal_info.email, "priya.nair@outlook.com"),
    ("phone", R2.personal_info.phone, "+91 8765432109"),
    ("loc",   R2.personal_info.location, "Kochi, Kerala"),
    ("sk",    len(R2.skills) >= 10, True),
    ("exp",   len(R2.experience), 1),
    ("exp_co",R2.experience[0].company, "Amazon India"),
    ("exp_ti",R2.experience[0].title, "Data Scientist"),
    ("exp_cu",R2.experience[0].date_range.is_current, True),
    ("edu",   len(R2.education), 2),
    ("edu1",  R2.education[0].institution, "National Institute of Technology, Calicut"),
    ("dg1",   R2.education[0].degree, "M.Tech Data Science"),
    ("gpa1",  R2.education[0].gpa, "8.9"),
    ("edu2",  R2.education[1].institution, "University of Kerala"),
    ("proj",  len(R2.projects), 1),
    ("pnm",   R2.projects[0].name, "Fake News Detector"),
    ("pdt",   R2.projects[0].date_range.start, "Jan 2022"),
    ("pdesc", "NLP" in (R2.projects[0].description or ""), True),
    ("awrds", len(R2.awards), 2),
])


# ─── Resume 3: Fresher / student ────────────────────────────────────────────
R3 = parser.parse([
    "Ankit Gupta", "ankit.gupta2001@gmail.com | 9988776655",
    "github.com/ankitg | Noida, UP",
    "Technical Skills",
    "Languages: C, C++, Python, Java",
    "Web: HTML, CSS, JavaScript, React",
    "Database: MySQL, MongoDB",
    "Academic Projects",
    "E-Commerce Website", "Aug 2023 – Nov 2023",
    "• Full-stack app using React, Node.js and MongoDB",
    "• Implemented JWT authentication and payment gateway",
    "Attendance Tracker App", "Jan 2023 – Mar 2023",
    "• Android app built with Java and Firebase",
    "Chat Application",
    "• Real-time messaging with WebSocket and Node.js",
    "Academic Background",
    "Jaypee Institute of Information Technology, Noida",
    "B.Tech Computer Science", "2019 – 2023", "CGPA: 8.1 / 10",
    "Bal Vidya Niketan, Noida", "12th PCM, CBSE", "2019", "Percentage: 89%",
    "Achievements",
    "• Smart India Hackathon 2022 – Finalist",
    "• CodeChef Long Challenge – Top 500",
    "• Academic Excellence Award 2021",
    "Hobbies",
    "• Competitive programming", "• Open source", "• Cricket",
], ["https://github.com/ankitg"])

run_suite("Fresher/student", R3, [
    ("name",  R3.personal_info.name, "Ankit Gupta"),
    ("email", R3.personal_info.email, "ankit.gupta2001@gmail.com"),
    ("loc",   R3.personal_info.location, "Noida, UP"),
    ("sk",    len(R3.skills) >= 10, True),
    ("exp",   len(R3.experience), 0),
    ("proj",  len(R3.projects), 3),
    ("proj1", R3.projects[0].name, "E-Commerce Website"),
    ("proj1d",R3.projects[0].date_range.start, "Aug 2023"),
    ("proj2", R3.projects[1].name, "Attendance Tracker App"),
    ("proj3", R3.projects[2].name, "Chat Application"),
    ("proj3d",bool(R3.projects[2].description), True),
    ("edu",   len(R3.education), 2),
    ("edu1",  R3.education[0].institution, "Jaypee Institute of Information Technology, Noida"),
    ("dg1",   R3.education[0].degree, "B.Tech Computer Science"),
    ("gpa1",  R3.education[0].gpa, "8.1 / 10"),
    ("edu2",  R3.education[1].institution, "Bal Vidya Niketan, Noida"),
    ("dg2",   R3.education[1].degree, "12th PCM, CBSE"),
    ("gpa2",  R3.education[1].gpa, "89%"),
    ("awrds", len(R3.awards) >= 3, True),
    ("hbbs",  len(R3.interests) >= 3, True),
])


# ─── Resume 4: Western / US style ───────────────────────────────────────────
R4 = parser.parse([
    "JANE DOE",
    "jane.doe@example.com  |  (415) 555-0192  |  San Francisco, CA",
    "linkedin.com/in/janedoe  |  github.com/janedoe",
    "SUMMARY",
    "Full-stack engineer with 6 years of experience building scalable web apps.",
    "WORK EXPERIENCE",
    "Stripe, Inc.",
    "Senior Software Engineer",
    "March 2021 - Present  |  San Francisco, CA",
    "- Architected payment processing service handling $2B/year in transactions",
    "- Reduced API latency by 40% through caching strategy redesign",
    "- Led migration from Ruby monolith to Go microservices",
    "Airbnb",
    "Software Engineer",
    "June 2018 - February 2021",
    "- Built search ranking algorithm improving booking conversion by 12%",
    "- Designed real-time notification system serving 50M+ users",
    "EDUCATION",
    "Stanford University",
    "B.S. Computer Science",
    "2014 - 2018",
    "GPA: 3.9 / 4.0",
    "SKILLS",
    "Go, Python, Ruby, JavaScript, TypeScript, SQL",
    "React, Node.js, gRPC, GraphQL, Kafka, Redis",
    "AWS, GCP, Terraform, Kubernetes, Docker",
    "PROJECTS",
    "Open-Source GraphQL Client",
    "May 2022",
    "- Lightweight GraphQL client with 1.2k GitHub stars",
    "AWARDS",
    "Grace Hopper Conference Scholarship 2020",
    "Stripe Engineering Excellence Award Q2 2022",
], ["https://linkedin.com/in/janedoe", "https://github.com/janedoe"])

run_suite("Western/US style", R4, [
    ("name",   R4.personal_info.name, "JANE DOE"),
    ("email",  R4.personal_info.email, "jane.doe@example.com"),
    ("loc",    R4.personal_info.location, "San Francisco, CA"),
    ("links",  len(R4.links), 2),
    ("sumry",  bool(R4.summary), True),
    ("sk",     len(R4.skills) >= 12, True),
    ("exp",    len(R4.experience), 2),
    ("exp1_co",R4.experience[0].company, "Stripe, Inc."),
    ("exp1_ti",R4.experience[0].title, "Senior Software Engineer"),
    ("exp1_cu",R4.experience[0].date_range.is_current, True),
    ("exp1_bt",len(R4.experience[0].bullets), 3),
    ("exp2_co",R4.experience[1].company, "Airbnb"),
    ("edu",    len(R4.education), 1),
    ("edu_in", R4.education[0].institution, "Stanford University"),
    ("edu_dg", R4.education[0].degree, "B.S. Computer Science"),
    ("edu_gpa",R4.education[0].gpa, "3.9 / 4.0"),
    ("proj",   len(R4.projects) >= 1, True),
    ("awrds",  len(R4.awards) >= 2, True),
])


# ─── Resume 5: Senior principal engineer, 3 companies, dense ────────────────
R5 = parser.parse([
    "Vikram Singh  |  vikram.singh@example.com  |  +91-9871234567",
    "Gurgaon, Haryana  |  linkedin.com/in/vikramsingh",
    "Professional Summary",
    "Principal Engineer with 12 years building distributed systems at scale.",
    "Skills & Expertise",
    "Core: Java, Python, Scala, Go, C++",
    "Big Data: Apache Spark, Kafka, Hadoop, Hive, Flink",
    "Cloud: AWS, GCP, Azure, Terraform, Kubernetes, Docker",
    "Databases: PostgreSQL, MySQL, Cassandra, DynamoDB, Neo4j",
    "Frameworks: Spring Boot, FastAPI, Django, gRPC, GraphQL",
    "Professional Experience",
    "Flipkart Internet Pvt. Ltd.",
    "Principal Software Engineer",
    "Jan 2019 - Present",
    "- Designed distributed inventory system processing 10M+ transactions/day",
    "- Led team of 12 engineers across 3 time zones",
    "- Reduced infrastructure cost by 35% via Spark optimization",
    "Walmart Labs India",
    "Senior Software Engineer",
    "Aug 2015 - Dec 2018",
    "- Built real-time pricing engine using Kafka and Flink",
    "- Architected multi-region data replication pipeline",
    "Infosys Ltd.",
    "Software Engineer",
    "Jul 2012 - Jul 2015",
    "- Developed ETL pipelines for banking client processing 500GB/day",
    "- Implemented rule-based fraud detection system",
    "Education",
    "IIT Bombay",
    "M.Tech Computer Science", "2010 - 2012", "CGPA: 9.4",
    "NIT Warangal",
    "B.Tech Computer Science", "2006 - 2010", "CGPA: 8.8",
    "Key Projects",
    "Distributed Cache System",
    "In-memory distributed cache with consistent hashing, 2x faster than Redis",
    "Real-time Recommendation Engine",
    "ML-based product recommendation serving 50M users, CTR improved by 23%",
    "Certifications",
    "AWS Solutions Architect - Professional (2022)",
    "Google Cloud Professional Data Engineer (2021)",
    "Interests",
    "- Distributed systems research", "- Open source", "- Badminton",
], ["https://linkedin.com/in/vikramsingh"])

run_suite("Senior engineer dense", R5, [
    ("name",   R5.personal_info.name, "Vikram Singh"),
    ("email",  R5.personal_info.email, "vikram.singh@example.com"),
    ("phone",  R5.personal_info.phone, "+91-9871234567"),
    ("loc",    R5.personal_info.location, "Gurgaon, Haryana"),
    ("links",  len(R5.links), 1),
    ("sumry",  bool(R5.summary), True),
    ("sk>=15", len(R5.skills) >= 15, True),
    ("exp",    len(R5.experience), 3),
    ("exp1_co",R5.experience[0].company, "Flipkart Internet Pvt. Ltd."),
    ("exp1_ti",R5.experience[0].title, "Principal Software Engineer"),
    ("exp1_cu",R5.experience[0].date_range.is_current, True),
    ("exp1_bt",len(R5.experience[0].bullets), 3),
    ("exp2_co",R5.experience[1].company, "Walmart Labs India"),
    ("exp3_co",R5.experience[2].company, "Infosys Ltd."),
    ("edu",    len(R5.education), 2),
    ("edu1",   R5.education[0].institution, "IIT Bombay"),
    ("dg1",    R5.education[0].degree, "M.Tech Computer Science"),
    ("gpa1",   R5.education[0].gpa, "9.4"),
    ("edu2",   R5.education[1].institution, "NIT Warangal"),
    ("proj",   len(R5.projects) >= 2, True),
    ("intsts", len(R5.interests) >= 3, True),
])


# ─── Summary ─────────────────────────────────────────────────────────────────
print()
pct = 100 * GRAND_OK // GRAND_T
bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
print(f"══════════════════════════════════════════")
print(f"  GRAND TOTAL : {GRAND_OK}/{GRAND_T}  ({pct}%)")
print(f"  [{bar}]")
print(f"══════════════════════════════════════════")
