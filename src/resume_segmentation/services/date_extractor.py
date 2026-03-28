from __future__ import annotations

import re
from typing import Optional

from ..models.resume import DateRange

_MONTH_MAP: dict[str, str] = {
    "jan": "Jan", "january": "Jan",
    "feb": "Feb", "february": "Feb",
    "mar": "Mar", "march": "Mar",
    "apr": "Apr", "april": "Apr",
    "may": "May",
    "jun": "Jun", "june": "Jun",
    "jul": "Jul", "july": "Jul",
    "aug": "Aug", "august": "Aug",
    "sep": "Sep", "sept": "Sep", "september": "Sep",
    "oct": "Oct", "october": "Oct",
    "nov": "Nov", "november": "Nov",
    "dec": "Dec", "december": "Dec",
}

_MONTH_NUM_MAP: dict[str, str] = {
    "01": "Jan", "1": "Jan", "02": "Feb", "2": "Feb",
    "03": "Mar", "3": "Mar", "04": "Apr", "4": "Apr",
    "05": "May", "5": "May", "06": "Jun", "6": "Jun",
    "07": "Jul", "7": "Jul", "08": "Aug", "8": "Aug",
    "09": "Sep", "9": "Sep", "10": "Oct",
    "11": "Nov", "12": "Dec",
}

_MA = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?"
    r"|Nov(?:ember)?|Dec(?:ember)?)"
)
_PR = (
    r"(?:Present|Current|Now|Till\s*Date|To\s*Date|Ongoing"
    r"|Till\s*Now|Running|Continuing|Today|Pursuing)"
)
_DS = r"(?:\s*[-\u2013\u2014/]\s*|\s+to\s+|\s+till\s+|\s+through\s+|\s+until\s+)"
_MONTH_YEAR4 = _MA + r",?\s+\d{4}"
_MONTH_YEAR2 = _MA + r"['\u2019`]\d{2}"
_SLASH_DATE  = r"(?:0?[1-9]|1[0-2])/\d{4}"
_YEAR4       = r"\b20\d{2}\b"

_DATE_RANGE_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(" + _MONTH_YEAR4 + r")" + _DS + r"(" + _MONTH_YEAR4 + r"|" + _PR + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"(" + _MONTH_YEAR2 + r")" + _DS + r"(" + _MONTH_YEAR2 + r"|" + _PR + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"(" + _SLASH_DATE + r")" + _DS + r"(" + _SLASH_DATE + r"|" + _PR + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"(" + _YEAR4 + r")" + _DS + r"(" + _YEAR4 + r"|" + _PR + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"(" + _YEAR4 + r")" + _DS + r"(\b\d{2}\b)",
        re.IGNORECASE,
    ),
]

_SINGLE_DATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(" + _MONTH_YEAR4 + r")", re.IGNORECASE),
    re.compile(r"(" + _SLASH_DATE  + r")"),
    re.compile(r"(" + _MONTH_YEAR2 + r")", re.IGNORECASE),
    re.compile(r"(" + _YEAR4       + r")"),
]

_MONTH_RANGE_RE = re.compile(
    r"(" + _MA + r")"
    r"\s*[-\u2013\u2014]\s*"
    r"(" + _MA + r")"
    r",?\s+(\d{4})",
    re.IGNORECASE,
)

_TILL_DATE_RE = re.compile(
    r"(" + _YEAR4 + r")\s+(?:till|until|upto|up\s*to)\s+(?:date|now|today|present)",
    re.IGNORECASE,
)

_SINCE_RE = re.compile(
    r"\bsince\s+(" + _MONTH_YEAR4 + r"|" + _YEAR4 + r")",
    re.IGNORECASE,
)

_FROM_TO_RE = re.compile(
    r"\bfrom\s+(" + _MONTH_YEAR4 + r"|" + _YEAR4 + r")"
    r"\s+to\s+(" + _MONTH_YEAR4 + r"|" + _PR + r")",
    re.IGNORECASE,
)


def _normalize_date_token(token: str) -> str:
    token = token.strip().rstrip(".,")
    m = re.match(r"(" + _MA + r"),?\s+(\d{4})", token, re.IGNORECASE)
    if m:
        key = m.group(1).lower().rstrip(".")
        return _MONTH_MAP.get(key[:3], m.group(1).capitalize()[:3]) + " " + m.group(2)
    m = re.match(r"(" + _MA + r")['\u2019`](\d{2})", token, re.IGNORECASE)
    if m:
        key = m.group(1).lower()
        yr = m.group(2)
        year = "20" + yr if int(yr) <= 35 else "19" + yr
        return _MONTH_MAP.get(key[:3], m.group(1).capitalize()[:3]) + " " + year
    m = re.match(r"(0?[1-9]|1[0-2])/(\d{4})", token)
    if m:
        return _MONTH_NUM_MAP.get(m.group(1).zfill(2), m.group(1)) + " " + m.group(2)
    if re.match(r"20\d{2}$", token.strip()):
        return token.strip()
    return token


def _is_present(token: str) -> bool:
    return bool(re.match(_PR, token.strip(), re.IGNORECASE))


def extract_date_range(text: str) -> tuple[str, Optional[DateRange]]:
    if not text:
        return text, None

    m = _MONTH_RANGE_RE.search(text)
    if m:
        start = _normalize_date_token(m.group(1).strip() + " " + m.group(3).strip())
        end   = _normalize_date_token(m.group(2).strip() + " " + m.group(3).strip())
        before = text[:m.start()].strip().rstrip(",-")
        after  = text[m.end():].strip().lstrip(",-")
        remaining = re.sub(r"\s+", " ", before + " " + after).strip().rstrip(",-")
        return remaining, DateRange(start=start, end=end, is_current=False)

    m = _TILL_DATE_RE.search(text)
    if m:
        start = _normalize_date_token(m.group(1))
        before = text[:m.start()].strip().rstrip(",-")
        after = text[m.end():].strip().lstrip(",-")
        remaining = re.sub(r"\s+", " ", before + " " + after).strip().rstrip(",-")
        return remaining, DateRange(start=start, end=None, is_current=True)

    m = _FROM_TO_RE.search(text)
    if m:
        start = _normalize_date_token(m.group(1))
        raw_end = m.group(2)
        is_curr = _is_present(raw_end)
        end = None if is_curr else _normalize_date_token(raw_end)
        before = text[:m.start()].strip().rstrip(",-")
        after = text[m.end():].strip().lstrip(",-")
        remaining = re.sub(r"\s+", " ", before + " " + after).strip().rstrip(",-")
        return remaining, DateRange(start=start, end=end, is_current=is_curr)

    m = _SINCE_RE.search(text)
    if m:
        start = _normalize_date_token(m.group(1))
        before = text[:m.start()].strip().rstrip(",-")
        after = text[m.end():].strip().lstrip(",-")
        remaining = re.sub(r"\s+", " ", before + " " + after).strip().rstrip(",-")
        return remaining, DateRange(start=start, end=None, is_current=True)

    for pattern in _DATE_RANGE_PATTERNS:
        match = pattern.search(text)
        if match:
            start = _normalize_date_token(match.group(1))
            raw_end = match.group(2)
            is_curr = _is_present(raw_end)
            if is_curr:
                end = None
            else:
                norm_end = _normalize_date_token(raw_end)
                if re.match(r"^\d{2}$", raw_end.strip()):
                    start_year = re.search(r"20\d{2}", start)
                    prefix = start_year.group(0)[:2] if start_year else "20"
                    end = prefix + raw_end.strip()
                else:
                    end = norm_end
            before = text[:match.start()].strip().rstrip(",-")
            after = text[match.end():].strip().lstrip(",-")
            remaining = re.sub(r"\s+", " ", before + " " + after).strip().rstrip(",-")
            return remaining, DateRange(start=start, end=end, is_current=is_curr)

    for pattern in _SINGLE_DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            start = _normalize_date_token(match.group(1))
            before = text[:match.start()].strip().rstrip(",-")
            after = text[match.end():].strip().lstrip(",-")
            remaining = re.sub(r"\s+", " ", before + " " + after).strip().rstrip(",-")
            return remaining, DateRange(start=start, end=None, is_current=False)

    return text.strip(), None


def find_all_dates(text: str) -> list[str]:
    dates: list[str] = []
    for pattern in _DATE_RANGE_PATTERNS + _SINGLE_DATE_PATTERNS:
        for m in pattern.finditer(text):
            dates.append(m.group(0))
    return list(dict.fromkeys(dates))


def has_date(text: str) -> bool:
    if _MONTH_RANGE_RE.search(text) or _TILL_DATE_RE.search(text) or _SINCE_RE.search(text) or _FROM_TO_RE.search(text):
        return True
    return any(p.search(text) for p in _DATE_RANGE_PATTERNS + _SINGLE_DATE_PATTERNS)
