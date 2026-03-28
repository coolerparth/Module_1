from __future__ import annotations

import re
from typing import Optional
from .spacy_ner_extractor import extract_ner_from_header, ner_available


                                                                               
                   
                                                                               

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
    r"(?:https?://)?(?:www\.)?"
    r"(?:linkedin\.com(?:/[^\s]*)?"
    r"|github\.com(?:/[^\s]*)?"
    r"|gitlab\.com(?:/[^\s]*)?"
    r"|bitbucket\.org(?:/[^\s]*)?"
    r"|leetcode\.com(?:/[^\s]*)?"
    r"|kaggle\.com(?:/[^\s]*)?"
    r"|medium\.com(?:/[^\s]*)?"
    r"|behance\.net(?:/[^\s]*)?"
    r"|dribbble\.com(?:/[^\s]*)?"
    r"|stackoverflow\.com(?:/[^\s]*)?"
    r"|[A-Za-z0-9][A-Za-z0-9\-]*\.(?:dev|io|me|app|site|tech|codes?|works?|studio)(?:/[^\s]*)?"
    r"|[A-Za-z0-9][A-Za-z0-9\-]*\.(?:vercel|netlify|pages|web)\.app(?:/[^\s]*)?"
    r"|[A-Za-z0-9][A-Za-z0-9\-]*\.(?:com|net|org|co)(?:/[^\s]*)?)",
    re.IGNORECASE,
)

_EMAIL_PROVIDER_DOMAINS = frozenset({
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
    "aol.com",
})

                                                         
_SEPARATOR_RE = re.compile(r"\s*[|•·/,]\s*")

                                   
_NOISE_CHARS = re.compile(r"[#*§◆●►▸]")

                                                              
_CITY_RE = re.compile(
    r"\b(?:"
    r"Mumbai|Delhi|Bangalore|Bengaluru|Chennai|Hyderabad|Pune|Kolkata|"
    r"Noida|Gurgaon|Gurugram|Ahmedabad|Jaipur|Lucknow|Kanpur|Nagpur|"
    r"Indore|Bhopal|Patna|Surat|Vadodara|Chandigarh|Kochi|Thiruvananthapuram|"
    r"Coimbatore|Vizag|Visakhapatnam|Bhubaneswar|Dehradun|Ranchi|"
    r"Mangalore|Mangaluru|Mysore|Mysuru|Thane|Ghaziabad|Meerut|Agra|"
    r"Varanasi|Vellore|Madurai|Vijayawada|Navi Mumbai|Raipur|Guwahati|"
    r"Jammu|Srinagar|Shimla|Rishikesh|Haridwar|"
    r"Prayagraj|Allahabad|Aligarh|Gorakhpur|Moradabad|Bareilly|Mathura|"
    r"Jodhpur|Udaipur|Kota|Ajmer|Bikaner|Sikar|"
    r"Amritsar|Ludhiana|Jalandhar|Patiala|Bathinda|"
    r"Nashik|Aurangabad|Solapur|Kolhapur|Nanded|Akola|"
    r"Rajkot|Bhavnagar|Jamnagar|Gandhinagar|"
    r"Faridabad|Sonipat|Panipat|Rohtak|Hisar|"
    r"Roorkee|Mussoorie|Nainital|Haldwani|"
    r"Raipur|Bhilai|Bilaspur|Durg|"
    r"Bhopal|Gwalior|Jabalpur|Ujjain|"
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
    if not 2 <= len(words) <= 4:
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
            prefix = city_match.group(1).strip().lower()
            if not re.search(
                r"\b(?:university|institute|college|school|academy|department|faculty|technology|engineering)\b",
                prefix,
            ):
                return city_match.group(0).strip()

                            
        city_known = _CITY_RE.search(cleaned)
        if (
            city_known
            and len(cleaned) <= 60
            and not re.search(
                r"\b(?:university|institute|college|school|academy|department|faculty|technology|engineering)\b",
                cleaned,
                re.IGNORECASE,
            )
        ):
            return city_known.group(0).strip()

    return None


                                                                               
                
                                                                               

def _canonicalize_url(url: str) -> str:
    url = url.strip().rstrip("/.,")
    if not url.startswith("http"):
        url = "https://" + url
    url = re.sub(r"^https?://www\.", "https://", url, flags=re.IGNORECASE)
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
        elif "gitlab.com" in url.lower():
            _add(url, "GitLab")
        elif "kaggle.com" in url.lower():
            _add(url, "Kaggle")
        elif "leetcode.com" in url.lower():
            _add(url, "LeetCode")
        elif "medium.com" in url.lower():
            _add(url, "Medium")
        elif "behance.net" in url.lower():
            _add(url, "Behance")
        elif "dribbble.com" in url.lower():
            _add(url, "Dribbble")
        elif "stackoverflow.com" in url.lower():
            _add(url, "Stack Overflow")
        else:
            _add(url, "Portfolio")

                     
    combined = " ".join(lines)
    for m in _LINKEDIN_RE.finditer(combined):
        _add(m.group(0), "LinkedIn")

    for m in _GITHUB_RE.finditer(combined):
        _add(m.group(0), "GitHub")

    _PORTFOLIO_PREFIX_RE = re.compile(
        r"(?:portfolio|website|site|blog|web|personal\s+site|"
        r"homepage|home\s+page)\s*[:\-]\s*",
        re.IGNORECASE,
    )
    for line in lines:
        m = _PORTFOLIO_PREFIX_RE.search(line)
        if m:
            after = line[m.end():].strip()
            url_m = _URL_PATTERN_RE.search(after)
            if url_m:
                _add(url_m.group(0), "Portfolio")

    for m in _URL_PATTERN_RE.finditer(combined):
        url = m.group(0)
        lower_url = url.lower()
        if "linkedin.com" in lower_url or "github.com" in lower_url:
            continue
        canonical_url = _canonicalize_url(url)
        domain = canonical_url.split("/", 3)[2].lower()
        if domain in _EMAIL_PROVIDER_DOMAINS:
            continue
        if (
            domain.endswith((".com", ".net", ".org", ".co"))
            and "/" not in canonical_url.removeprefix("https://").removeprefix("http://")
            and not any(marker in combined.lower() for marker in ("portfolio", "website", "site:", "blog"))
        ):
            continue
        if "gitlab.com" in lower_url:
            _add(url, "GitLab"); continue
        if "kaggle.com" in lower_url:
            _add(url, "Kaggle"); continue
        if "leetcode.com" in lower_url:
            _add(url, "LeetCode"); continue
        if "medium.com" in lower_url:
            _add(url, "Medium"); continue
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

    ner_name: Optional[str] = None
    ner_conf = 0.0
    if ner_available():
        ner = extract_ner_from_header(header_lines)
        if ner.name and ner.name_confidence >= 0.70:
            ner_name = ner.name
            ner_conf = ner.name_confidence

    regex_name: Optional[str] = None
    for line in header_lines[:3]:
        cleaned = _EMAIL_RE.sub("", line)
        cleaned = _PHONE_RE.sub("", cleaned)
        cleaned = _URL_PATTERN_RE.sub("", cleaned)
        cleaned = _NOISE_CHARS.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if looks_like_name(cleaned):
            regex_name = cleaned
            break
        if "|" in cleaned:
            first_part = cleaned.split("|")[0].strip()
            if looks_like_name(first_part):
                regex_name = first_part
                break

    if ner_name and ner_conf >= 0.80:
        result["name"] = ner_name
    elif regex_name:
        result["name"] = regex_name
    elif ner_name:
        result["name"] = ner_name

                                                                               
                                                           
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
