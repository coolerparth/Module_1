"""Integration tests for the full pipeline."""
import sys
sys.path.insert(0, 'src')

from resume_segmentation.services.text_resume_parser import TextResumeParser
from resume_segmentation.services.career_intelligence import CareerIntelligenceAnalyzer, CareerLevel
from resume_segmentation.services.gpa_normalizer import normalize_gpa
from resume_segmentation.services.timeline_validator import TimelineValidator
from resume_segmentation.services.resume_quality_reporter import ResumeQualityReporter
from resume_segmentation.models.resume import *

parser     = TextResumeParser()
ci_analyzer = CareerIntelligenceAnalyzer()
tv         = TimelineValidator()
bugs       = []

def chk(label, got, expected):
    if got != expected:
        bugs.append(f'  [{label}] got={got!r} expected={expected!r}')

# ── FORMAT 6: Research scientist ─────────────────────────────────────────
R6 = parser.parse([
    'Dr. Meera Krishnan',
    'meera.krishnan@iitm.ac.in | +91-9988112233',
    'Chennai, Tamil Nadu | linkedin.com/in/meerak | github.com/meerak',
    'PROFESSIONAL SUMMARY',
    'Research scientist with 9 years in NLP and ML systems.',
    'TECHNICAL SKILLS',
    'Languages: Python, R, Java, C++, Julia',
    'ML/AI: TensorFlow, PyTorch, scikit-learn, HuggingFace, LangChain',
    'Data: Pandas, NumPy, Apache Spark, Airflow, dbt',
    'Cloud: AWS, GCP, Docker, Kubernetes, Terraform',
    'Databases: PostgreSQL, MongoDB, Elasticsearch, Redis',
    'WORK EXPERIENCE',
    'DeepMind (Google)',
    'Senior Research Scientist',
    'April 2020 - Present',
    '- Developed transformer models reducing inference latency by 45%',
    '- Authored 3 papers at NeurIPS 2022 and ICML 2023',
    '- Led team of 6 research engineers across London and Bangalore',
    'Microsoft Research India',
    'Research Scientist',
    'July 2017 - March 2020',
    '- Built multilingual NLP pipeline for 12 Indian languages',
    '- Reduced training cost by 30% via mixed-precision training',
    'Zoho Corporation',
    'Software Engineer',
    'June 2015 - June 2017',
    '- Developed RESTful APIs serving 500K daily users',
    '- Improved database query performance by 60% via indexing',
    'EDUCATION',
    'IIT Madras',
    'Ph.D. Computer Science',
    '2010 - 2015',
    'CGPA: 9.6 / 10',
    'Anna University',
    'B.E. Computer Science and Engineering',
    '2006 - 2010',
    'CGPA: 8.9 / 10',
    'PROJECTS',
    'Multilingual Document Parser',
    'Jan 2023 - Jun 2023',
    '- Parsed resumes in 8 languages with 94% accuracy',
    '- Open-sourced on GitHub with 2.3k stars',
    'Real-time Fraud Detection System',
    'Aug 2022 - Dec 2022',
    '- Detected 99.2% of fraud cases in real time using LSTM',
    'AWARDS',
    '- Google Research Award 2022',
    '- Best Paper Award at NeurIPS 2022',
    "- President's Gold Medal - IIT Madras 2015",
    'LANGUAGES',
    'English (Native), Tamil (Native), Hindi (Proficient), French (Basic)',
    'INTERESTS',
    '- Classical music, Chess, Open-source contributions',
], ['https://linkedin.com/in/meerak', 'https://github.com/meerak'])

tests = [
    ('name',          R6.personal_info.name,                  'Dr. Meera Krishnan'),
    ('email',         R6.personal_info.email,                  'meera.krishnan@iitm.ac.in'),
    ('phone',         R6.personal_info.phone,                  '+91-9988112233'),
    ('location',      R6.personal_info.location,               'Chennai, Tamil Nadu'),
    ('links',         len(R6.links),                           2),
    ('summary',       bool(R6.summary),                        True),
    ('skills>=15',    len(R6.skills) >= 15,                   True),
    ('exp_count',     len(R6.experience),                     3),
    ('exp1_co',       R6.experience[0].company,                'DeepMind (Google)'),
    ('exp1_ti',       R6.experience[0].title,                  'Senior Research Scientist'),
    ('exp1_curr',     R6.experience[0].date_range.is_current,  True),
    ('exp1_bullets',  len(R6.experience[0].bullets),           3),
    ('exp2_co',       R6.experience[1].company,                'Microsoft Research India'),
    ('exp3_co',       R6.experience[2].company,                'Zoho Corporation'),
    ('edu_count',     len(R6.education),                      2),
    ('edu1_inst',     R6.education[0].institution,             'IIT Madras'),
    ('edu1_degree',   R6.education[0].degree,                  'Ph.D. Computer Science'),
    ('edu1_gpa',      R6.education[0].gpa,                     '9.6 / 10'),
    ('edu2_inst',     R6.education[1].institution,             'Anna University'),
    ('proj_count',    len(R6.projects),                       2),
    ('proj1_name',    R6.projects[0].name,                     'Multilingual Document Parser'),
    ('awards>=3',     len(R6.awards) >= 3,                    True),
    ('languages>=1',  len(R6.languages) >= 1,                 True),
    ('interests>=1',  len(R6.interests) >= 1,                 True),
]

ok = sum(1 for l,g,e in tests if g==e)
fail = [(l,g,e) for l,g,e in tests if g!=e]
print(f'Research scientist resume: {ok}/{len(tests)}')
for l,g,e in fail: print(f'  FAIL [{l}]: {g!r} != {e!r}')

# Career intelligence
ci = ci_analyzer.analyze(R6)
print(f'Career: level={ci.career_level.value} years={ci.total_years_experience:.1f} domain={ci.primary_domain.value}')
print(f'  notable_companies={ci.notable_companies}')
print(f'  notable_universities={ci.notable_universities}')
print(f'  has_mgmt={ci.has_management_experience} seniority={ci.seniority_score}')

# GPA
for raw, exp in [('9.6 / 10', 91.2), ('8.9 / 10', 84.5)]:
    r = normalize_gpa(raw)
    diff = abs((r.percentage or 0) - exp)
    status = 'OK' if diff < 2 else f'FAIL (got {r.percentage})'
    print(f'GPA {raw} => {r.display} [{status}]')

# Timeline
t = tv.validate(R6)
print(f'Timeline: consistent={t.is_consistent} years={t.total_years_experience}')
if t.warnings: print(f'  Warnings: {[w.message for w in t.warnings]}')

# Quality
qr = ResumeQualityReporter().analyze(R6)
print(f'Quality: ATS={qr.ats_score:.0f} completeness={qr.completeness_score:.0f} bullets={qr.bullet_score:.0f} overall={qr.overall_score:.0f}')

if bugs:
    print(f'\nBUGS: {bugs}')
else:
    print('\nAll integration tests PASSED ✓')
