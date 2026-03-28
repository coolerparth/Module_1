from __future__ import annotations

from dataclasses import dataclass
import copy
import re
from typing import Any

_PLACEHOLDER_RE = re.compile(r"(?:link\s+present|link\s+not\s+specified|not\s+specified\s+in\s+text|not\s+provided)", re.IGNORECASE)
_DOMAIN_WITHOUT_SCHEME_RE = re.compile(r"^(?:linkedin\.com|github\.com|leetcode\.com|www\.)", re.IGNORECASE)
_LINKEDIN_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_%]{2,99}/?$")
_GITHUB_USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?$|^[A-Za-z0-9]$")


def _has_safe_slug_signal(value: str) -> bool:
    return any(ch.isdigit() for ch in value) or "-" in value


@dataclass(frozen=True)
class DatasetNormalizationChange:
    path: str
    old_value: str
    new_value: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DatasetNormalizationResult:
    data: list[dict[str, Any]]
    changes: list[DatasetNormalizationChange]


def normalize_resume_dataset(data: object) -> DatasetNormalizationResult:
    if not isinstance(data, list):
        raise TypeError("Dataset root must be a list.")

    normalized = copy.deepcopy(data)
    changes: list[DatasetNormalizationChange] = []

    for item_idx, item in enumerate(normalized):
        if not isinstance(item, dict):
            continue
        personal = item.get("personal_info")
        if not isinstance(personal, dict):
            continue
        links = personal.get("links")
        if not isinstance(links, list):
            continue
        for link_idx, link in enumerate(links):
            if not isinstance(link, dict):
                continue
            label = str(link.get("label") or "").strip()
            url = link.get("url")
            if not isinstance(url, str):
                continue
            new_url, reason = _normalize_link_url(label, url)
            if new_url != url:
                link["url"] = new_url
                changes.append(
                    DatasetNormalizationChange(
                        path=f"$[{item_idx}].personal_info.links[{link_idx}].url",
                        old_value=url,
                        new_value=new_url,
                        reason=reason,
                    )
                )

    return DatasetNormalizationResult(data=normalized, changes=changes)


def _normalize_link_url(label: str, url: str) -> tuple[str, str | None]:
    original = url
    cleaned = url.strip()
    if not cleaned:
        return original, None

    if _PLACEHOLDER_RE.search(cleaned):
        return "", "cleared_placeholder_link"

    if _DOMAIN_WITHOUT_SCHEME_RE.match(cleaned) and " " not in cleaned:
        return f"https://{cleaned.lstrip('/')}", "added_https_scheme"

    lowered_label = label.strip().lower()
    compact = cleaned.strip().strip("/")

    if lowered_label == "linkedin" and _LINKEDIN_SLUG_RE.fullmatch(compact) and _has_safe_slug_signal(compact):
        return f"https://www.linkedin.com/in/{compact}/", "expanded_linkedin_slug"

    if lowered_label == "github" and _GITHUB_USER_RE.fullmatch(compact) and _has_safe_slug_signal(compact):
        return f"https://github.com/{compact}", "expanded_github_username"

    return original, None
