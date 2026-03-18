"""
personal_info_extractor.py — Dedicated personal information extractor.

Extracts with high precision:
  - Full name (heuristic: first clean line, 2-4 capitalized words, no digits)
  - Email address (RFC-5321 compliant regex)
  - Phone number (international formats: +91, +1, (xxx), xxx-xxx-xxxx etc.)
  - Location (City, State / City, Country patterns)
  - Headline / job title (short descriptive phrase below the name)
  - LinkedIn URL
  - GitHub URL
  - Portfolio / personal website URL
"""
from __future__ import annotations

import re
from typing import Optional


                                                                               
                   
                                                                               

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.+\-]*@[A-Za-z0-9][A-Za-z0-9\-]*\.[A-Za-z]{2,}(?:\.[A-Za-z]{2,})?",
)

_PHONE_RE = re.compile(
    r"(?:"
    r"\+\d{1,3}[\s.\-]?\(?\d{1,4}\)?[\s.\-]?\d{2,4}[\s.\-]?\d{2,4}[\s.\-]?\d{0,4}"                 
    r"|\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}"                   
    r"|\d{5}[\s.\-]\d{5}"                                          
    r"|\d{10,12}"                                                      
    r")"
)

_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub|profile)/[A-Za-z0-9\-_.%+]+/?",
    re.IGNORECASE,
)

_GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9\-_.]+/?",
    re.IGNORECASE,
)

_PORTFOLIO_RE = re.compile(
    r"https?://[A-Za-z0-9\-._~:/?#[\]@!$&'()*+,;=%]+",
    re.IGNORECASE,
)

_URL_PATTERN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:linkedin\.com/[^\s]+|github\.com/[^\s]+|[A-Za-z0-9\-]+\.(?:dev|io|me|com|net|org|co)/[^\s]*)",
    re.IGNORECASE,
)

                                                         
_SEPARATOR_RE = re.compile(r"\s*[|•·/,]\s*")

                                   
_NOISE_CHARS = re.compile(r"[#*§◆●►▸]")

                                                              
_CITY_RE = re.compile(
    r"\b(?:"
    r"Mumbai|Delhi|Bangalore|Bengaluru|Chennai|Hyderabad|Pune|Kolkata|"
    r"Noida|Gurgaon|Gurugram|Ahmedabad|Jaipur|Lucknow|Kanpur|Nagpur|"
    r"Indore|Bhopal|Patna|Surat|Vadodara|Chandigarh|Kochi|Thiruvananthapuram|"
    r"Coimbatore|Vizag|Visakhapatnam|Bhubaneswar|Dehradun|Ranchi|"
    r"New York|Los Angeles|Chicago|Houston|San Francisco|Seattle|Austin|"
    r"Boston|Washington|London|Toronto|Vancouver|Sydney|Singapore|Dubai|"
    r"Berlin|Paris|Amsterdam|Tokyo|Melbourne|Zurich|"
    r"[A-Z][a-z]+\s*,\s*(?:[A-Z]{2}|[A-Z][a-z]+)"                             
    r")\b",
    re.IGNORECASE,
)

_STATE_ABBR_RE = re.compile(r"\b[A-Z]{2}\b")

                                                  
_NOT_NAME_PATTERNS = [
    re.compile(r"[A-Za-z0-9_.+\-]+@"),                      
    re.compile(r"https?://"),                           
    re.compile(r"\d{7,}"),                                              
    re.compile(r"[•|/\\]"),                                    
    re.compile(r"(?:resume|cv|curriculum|page)", re.I),               
    re.compile(r"\b(?:pvt|ltd|inc|corp|llc|llp|plc|gmbh|bv|co\.)\b", re.I),                
    re.compile(r"\b(?:b\.tech|m\.tech|btech|mtech|b\.sc|m\.sc|bsc|msc|phd|mba|bba)\b", re.I),           
    re.compile(r"\b(?:technologies|solutions|systems|services|enterprises|consulting)\b", re.I),             
    re.compile(r"\b(?:engineer|developer|analyst|intern|manager|designer|scientist|"
               r"researcher|consultant|specialist|architect|coordinator|director)\b", re.I),              
]

_COMMON_NAME_WORDS = frozenset({
    "dr", "mr", "mrs", "ms", "prof", "professor",
})


                                                                               
                
                                                                               

def looks_like_name(text: str) -> bool:
    if not text:
        return False

    stripped = text.strip()

    if len(stripped) > 55 or len(stripped) < 4:
        return False

    if any(pat.search(stripped) for pat in _NOT_NAME_PATTERNS):
        return False

    if any(c.isdigit() for c in stripped):
        return False

    words = stripped.split()
    if not 2 <= len(words) <= 5:
        return False

    lowercase_connectors = {"de", "van", "von", "den", "bin", "binte", "al", "el", "ul", "o"}
    for word in words:
        clean_word = word.strip(".,")
        if clean_word.lower() in lowercase_connectors:
            continue
        if clean_word.lower() in _COMMON_NAME_WORDS:
            continue
        if not clean_word[0].isupper():
            return False

    return True


def looks_like_headline(text: str) -> bool:
    if not text:
        return False

    stripped = text.strip()
    if len(stripped) > 120 or len(stripped) < 5:
        return False

                                     
    if _EMAIL_RE.search(stripped) or _PHONE_RE.search(stripped):
        return False

    word_count = len(stripped.split())
    if not 2 <= word_count <= 12:
        return False

                                                  
    if re.search(r"\d{10}", stripped):
        return False

    return True


                                                                               
                    
                                                                               

def extract_location(lines: list[str]) -> Optional[str]:
    for line in lines:
                                               
        cleaned = _EMAIL_RE.sub("", line)
        cleaned = _PHONE_RE.sub("", cleaned)
        cleaned = _URL_PATTERN_RE.sub("", cleaned)
        cleaned = _NOISE_CHARS.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

                                                                            
                                                                                  
        city_match = re.search(
            r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)"                     
            r"\s*,\s*"
            r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?|[A-Z]{2})"                                                
            r"\b",
            cleaned,
        )
        if city_match:
            return city_match.group(0).strip()

                            
        city_known = _CITY_RE.search(cleaned)
        if city_known and len(cleaned) <= 60:
            return cleaned.strip()

    return None


                                                                               
                
                                                                               

def _canonicalize_url(url: str) -> str:
    url = url.strip().rstrip("/.,")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def extract_links(lines: list[str], pdf_urls: list[str]) -> list[dict[str, str]]:
    collected: list[dict] = []
    seen: set[str] = set()

    def _add(url: str, label: str) -> None:
        canon = _canonicalize_url(url).lower()
        if canon not in seen:
            seen.add(canon)
            collected.append({"label": label, "url": _canonicalize_url(url)})

                                            
    for url in pdf_urls:
        if "linkedin.com" in url.lower():
            _add(url, "LinkedIn")
        elif "github.com" in url.lower():
            _add(url, "GitHub")
        else:
            _add(url, "Portfolio")

                     
    combined = " ".join(lines)
    for m in _LINKEDIN_RE.finditer(combined):
        _add(m.group(0), "LinkedIn")

    for m in _GITHUB_RE.finditer(combined):
        _add(m.group(0), "GitHub")

                                                      
    for m in _URL_PATTERN_RE.finditer(combined):
        url = m.group(0)
        if "linkedin.com" in url.lower() or "github.com" in url.lower():
            continue
        _add(url, "Portfolio")

    return collected


                                                                               
                     
                                                                               

def normalize_phone(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip())


                                                                               
                
                                                                               

def extract_personal_info(
    header_lines: list[str],
    pdf_urls: list[str],
) -> dict:
    result = {
        "name": None,
        "email": None,
        "phone": None,
        "location": None,
        "headline": None,
    }
    links: list[dict] = []

    if not header_lines:
        return result

    combined = " ".join(header_lines)

                                                                               
    email_match = _EMAIL_RE.search(combined)
    if email_match:
        result["email"] = email_match.group(0).lower()

                                                                               
                                                                  
    for line in header_lines:
        clean_for_phone = _EMAIL_RE.sub("", line)
        clean_for_phone = _URL_PATTERN_RE.sub("", clean_for_phone)
        phone_match = _PHONE_RE.search(clean_for_phone)
        if phone_match:
            phone_raw = phone_match.group(0).strip()
                                          
            digit_count = sum(c.isdigit() for c in phone_raw)
            if digit_count >= 10:
                result["phone"] = normalize_phone(phone_raw)
                break

                                                                               
                       
    for line in header_lines[:3]:
        cleaned = _EMAIL_RE.sub("", line)
        cleaned = _PHONE_RE.sub("", cleaned)
        cleaned = _URL_PATTERN_RE.sub("", cleaned)
        cleaned = _NOISE_CHARS.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if looks_like_name(cleaned):
            result["name"] = cleaned
            break

                                                                               
                                                           
    name_found = result["name"]
    for i, line in enumerate(header_lines[1:4], 1):
        if name_found and line.strip() == name_found:
            continue
        cleaned = _EMAIL_RE.sub("", line)
        cleaned = _PHONE_RE.sub("", cleaned)
        cleaned = _URL_PATTERN_RE.sub("", cleaned)
        cleaned = _NOISE_CHARS.sub("", cleaned).strip()
        if looks_like_headline(cleaned):
            result["headline"] = cleaned
            break

                                                                               
    result["location"] = extract_location(header_lines)

                                                                                
    links = extract_links(header_lines, pdf_urls)

    return {**result, "links": links}
