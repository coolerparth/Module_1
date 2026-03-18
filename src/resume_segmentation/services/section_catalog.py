"""
section_catalog.py — Ultra-comprehensive resume section heading detector.

Architecture:
  1. Exact-match lookup (fastest, highest precision)
  2. Prefix/suffix stripped match (handles trailing colons, dashes, numbering)
  3. Subsequence / token-overlap fuzzy match (handles typos, extra words)
  4. Structural heuristics (ALL CAPS short line, emoji-prefixed line)

Returns a canonical section key or None.
"""
from __future__ import annotations

import re
import unicodedata

                                                                               
                                                                           
                                                                               
CANONICAL_SECTIONS = {
    "header", "summary", "skills", "experience", "education",
    "projects", "certifications", "awards", "interests", "languages",
    "publications", "volunteer", "references", "courses", "activities",
}

                                                                               
                                                                 
                                                                               
_CATALOG: dict[str, list[str]] = {
    "summary": [
        "summary", "professional summary", "executive summary", "career summary",
        "about me", "about", "profile", "professional profile", "career profile",
        "career objective", "objective", "professional objective", "career goal",
        "goals", "overview", "professional overview", "background",
        "personal statement", "statement of purpose", "bio", "biography",
        "introduction", "intro", "highlights", "career highlights",
        "key highlights", "professional background", "who am i",
        "about myself", "cover summary", "resume summary",
        "self summary", "professional bio", "career overview",
        "value proposition", "professional introduction",
    ],
    "skills": [
        "skills", "technical skills", "core skills", "key skills",
        "professional skills", "skill set", "skillset", "skill summary",
        "areas of expertise", "expertise", "competencies", "core competencies",
        "technical competencies", "technical expertise", "technologies",
        "technology", "tech stack", "tools", "tools & technologies",
        "tools and technologies", "programming languages", "languages & tools",
        "languages and tools", "software", "software skills", "software proficiency",
        "hard skills", "soft skills", "technical knowledge", "knowledge",
        "proficiencies", "proficiency", "abilities", "technical abilities",
        "frameworks", "frameworks & libraries", "platforms", "development skills",
        "programming skills", "coding skills", "it skills", "computer skills",
        "skills & technologies", "skills and technologies", "skills & tools",
        "skills and tools", "relevant skills", "additional skills",
        "key technical skills", "areas of knowledge", "technical proficiency",
        "software tools", "technical tools", "digital skills", "data skills",
        "skills summary", "skill highlights", "core technical skills",
        "languages, frameworks & tools", "tech skills", "engineering skills",
        "skills & expertise", "skills and expertise", "capabilities",
        "technical capabilities", "core capabilities", "key capabilities",
        "specializations", "specialisation", "technical specialization",
        "domain expertise", "domain skills",
    ],
    "experience": [
        "experience", "work experience", "professional experience",
        "employment", "employment history", "work history",
        "career history", "professional history", "professional background",
        "relevant experience", "industry experience", "technical experience",
        "internship", "internships", "internship experience",
        "research experience", "teaching experience",
        "positions", "positions held", "job experience",
        "professional activities", "work", "professional work",
        "career experience", "job history", "relevant work experience",
        "experience & employment", "professional work experience",
        "industry work experience", "applied experience",
        "engineering experience", "software experience",
        "it experience", "development experience",
        "organizational experience", "work & internship experience",
        "work and internship", "training & experience",
        "training and experience", "practical experience",
    ],
    "education": [
        "education", "educational background", "educational qualifications",
        "academic background", "academic qualifications", "academic history",
        "qualifications", "degrees", "degree", "schooling",
        "training", "training & education", "education & training",
        "academic credentials", "credentials", "academic profile",
        "educational history", "educational details", "academic details",
        "studies", "study", "academic record", "educational record",
        "university", "universities", "college", "colleges",
        "schools", "school", "academic education", "formal education",
        "academic achievements", "academic experience",
    ],
    "projects": [
        "projects", "personal projects", "academic projects",
        "project work", "project experience", "notable projects",
        "side projects", "open source projects", "key projects",
        "technical projects", "relevant projects", "project portfolio",
        "portfolio", "engineering projects", "research projects",
        "selected projects", "featured projects", "capstone projects",
        "major projects", "mini projects", "application projects",
        "live projects", "significant projects", "project highlights",
        "project details", "software projects", "projects & portfolio",
    ],
    "certifications": [
        "certifications", "certification", "certified", "licenses",
        "license", "licences", "credentials", "professional certifications",
        "technical certifications", "accreditations", "accreditation",
        "badges", "online courses", "mooc", "moocs", "courses & certifications",
        "certificates", "certificate", "professional certificates",
        "industry certifications", "certifications & licenses",
        "certifications and licenses", "digital certificates",
        "continuing education", "professional development courses",
    ],
    "awards": [
        "awards", "honors", "honours", "achievements", "achievement",
        "accomplishments", "accomplishment", "recognition", "recognitions",
        "awards & honors", "honors & awards", "awards and honors",
        "prizes", "distinctions", "merits", "accolades",
        "scholarships", "scholarship", "fellowships", "fellowship",
        "grants", "grant", "academic awards", "professional awards",
        "industry awards", "notable achievements", "key achievements",
        "achievements & awards", "awards & achievements",
        "achievements and awards", "honors and awards",
        "awards and achievements", "recognitions & achievements",
        "honor roll", "dean's list", "merit awards",
    ],
    "interests": [
        "interests", "hobbies", "hobbies & interests", "interests & hobbies",
        "personal interests", "activities", "extracurricular", "extracurricular activities",
        "outside interests", "leisure", "recreational activities", "passions",
        "other interests", "personal activities", "hobby", "leisure activities",
        "co-curricular activities", "co curricular", "cocurricular",
        "personal hobbies", "outside of work", "fun facts",
    ],
    "languages": [
        "languages", "language skills", "language proficiency",
        "spoken languages", "foreign languages", "linguistic skills",
        "human languages", "language knowledge", "communication languages",
        "multilingual", "natural languages",
    ],
    "publications": [
        "publications", "research publications", "papers", "journal papers",
        "conference papers", "articles", "research articles", "research papers",
        "books", "authored works", "research work", "research",
        "papers published", "published works", "peer reviewed papers",
        "scientific publications", "academic publications",
    ],
    "volunteer": [
        "volunteer", "volunteering", "volunteer experience", "volunteer work",
        "community service", "social work", "non-profit", "nonprofit",
        "outreach", "community involvement", "service", "civic involvement",
        "community activities", "volunteer activities", "social service",
        "community engagement", "social engagement",
    ],
    "references": [
        "references", "reference", "referees", "referee",
        "professional references", "character references",
        "available upon request", "references available",
    ],
    "courses": [
        "courses", "coursework", "relevant courses", "relevant coursework",
        "online courses", "training courses", "academic courses",
        "key courses", "selected coursework", "notable coursework",
        "course highlights", "completed courses",
    ],
    "activities": [
        "activities", "campus activities",
        "student activities", "club activities", "leadership activities",
        "organizational activities", "social activities",
        "professional activities", "academic activities",
        "positions of responsibility", "clubs & organizations",
        "clubs and organizations", "student organizations",
        "clubs", "organization", "organizations",
        "memberships", "membership", "affiliations", "affiliation",
        "professional memberships", "professional associations",
        "associations", "association",
    ],
}

                                                                               
                                                       
                                                                               
def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^\w\s&+]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


_LOOKUP: dict[str, str] = {}

for _canonical, _variants in _CATALOG.items():
    for _variant in _variants:
        _LOOKUP[_normalize(_variant)] = _canonical

                                                                               
                                                   
                                                                               
_STRIP_PREFIX_RE = re.compile(
    r"^(?:"
    r"\d+[\.\)]\s*"                                      
    r"|[●•▶►▸‣◆◇→\-–—]+\s*"                      
    r"|[★☆✓✔✗✘]\s*"                         
    r"|#\s*"                                 
    r")+",
    re.UNICODE,
)

_STRIP_SUFFIX_RE = re.compile(
    r"[\s:.\-–—\/|]+$"
)

                                                                           
_EMOJI_RE = re.compile(
    r"^[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F000-\U0001F02F"
    r"\U00002600-\U000026FF\u2764\u2665\u2666\u2663\u2660\u2602\u2601"
    r"\U0001F100-\U0001F1FF\U00002100-\U0000214F\U0001FA00-\U0001FA6F]+\s*",
    re.UNICODE,
)


def _clean_heading_text(text: str) -> str:
    text = text.strip()
    text = _EMOJI_RE.sub("", text)
    text = _STRIP_PREFIX_RE.sub("", text)
    text = _STRIP_SUFFIX_RE.sub("", text)
    return text.strip()


                                                                               
                           
                                                                               
def _token_set(text: str) -> frozenset[str]:
    return frozenset(t for t in _normalize(text).split() if len(t) > 2)


def _best_fuzzy_match(normalized_text: str) -> str | None:
    tokens = _token_set(normalized_text)
    if not tokens:
        return None

                                                                          
                                                                              
    if len(tokens) >= 5:
        return None

    best_key: str | None = None
    best_score = 0.0

    for variant, canonical in _LOOKUP.items():
        vtokens = _token_set(variant)
        if not vtokens:
            continue
        overlap = len(tokens & vtokens)
        if overlap == 0:
            continue
                                                             
        if overlap < len(tokens):
            continue
        score = overlap / max(len(vtokens), len(tokens))
        if score > best_score:
            best_score = score
            best_key = canonical

                                                                           
    if best_score >= 0.75:
        return best_key
    return None


                                                                               
                       
                                                                               
_NON_HEADING_PATTERNS = [
    re.compile(r"[A-Za-z0-9_.+\-]+@[A-Za-z0-9\-]+\.[A-Za-z]{2,}"),         
    re.compile(r"https?://"),                                                
    re.compile(r"\d{10,}"),                                                        
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}", re.I),        
    re.compile(r"\d{4}\s*[-–—]\s*(?:\d{4}|present)", re.I),                      
    re.compile(r"•|\|"),                                                                  
]


def _is_structural_heading(text: str) -> bool:
    stripped = text.strip()
    word_count = len(stripped.split())

    if word_count < 1 or word_count > 5:
        return False

                                          
    for pat in _NON_HEADING_PATTERNS:
        if pat.search(stripped):
            return False

                                               
    if stripped.isupper() and word_count >= 1:
        return True

                                                                 
    words = stripped.split()
    if all(w[0].isupper() for w in words if w) and word_count <= 4:
        return True

    return False


                                                                               
            
                                                                               
def match_section_heading(text: str) -> str | None:
    if not text:
        return None

                   
    cleaned = _clean_heading_text(text)
    if not cleaned:
        return None

                                                                       
    word_count = len(cleaned.split())
    if word_count > 7:
        return None

                                     
    normalized = _normalize(cleaned)
    if normalized in _LOOKUP:
        return _LOOKUP[normalized]

                                        
    stripped_colon = re.sub(r"\s*:\s*$", "", cleaned)
    if stripped_colon != cleaned:
        n = _normalize(stripped_colon)
        if n in _LOOKUP:
            return _LOOKUP[n]

                                                     
    if cleaned.isupper():
        lower_cleaned = cleaned.lower()
        n = _normalize(lower_cleaned)
        if n in _LOOKUP:
            return _LOOKUP[n]

                         
    fuzzy = _best_fuzzy_match(normalized)
    if fuzzy:
        return fuzzy

                                                                     
    n_raw = _normalize(text.strip())
    if n_raw in _LOOKUP:
        return _LOOKUP[n_raw]

                                                                     
    try:
        from .multilang_catalog import match_multilang_heading
        multilang = match_multilang_heading(text)
        if multilang:
            return multilang
    except ImportError:
        pass

    return None


def get_all_section_keys() -> set[str]:
    return set(_CATALOG.keys())


def is_likely_heading(text: str, font_size: float | None = None, median_font: float | None = None) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

                      
    if font_size and median_font and font_size >= median_font * 1.08:
        if len(stripped.split()) <= 6:
            return True

                         
    if stripped.isupper() and 1 <= len(stripped.split()) <= 5:
        return True

                           
    if match_section_heading(stripped) is not None:
        return True

    return False
