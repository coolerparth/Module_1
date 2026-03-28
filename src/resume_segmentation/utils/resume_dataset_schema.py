from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class DatasetSchemaIssue:
    level: str
    path: str
    message: str


@dataclass(frozen=True)
class DatasetSchemaSummary:
    total_items: int
    error_count: int
    warning_count: int
    issues: list[DatasetSchemaIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_items": self.total_items,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "is_valid": self.is_valid,
            "issues": [
                {"level": issue.level, "path": issue.path, "message": issue.message}
                for issue in self.issues
            ],
        }


_REQUIRED_TOP_LEVEL_KEYS = {
    "file",
    "personal_info",
    "education",
    "experience",
    "projects",
    "skills",
    "certifications",
}

_OPTIONAL_PERSONAL_INFO_KEYS = {"name", "email", "phone", "location", "links"}

_URL_PLACEHOLDER_RE = re.compile(r"link not specified|not provided|not available", re.IGNORECASE)
_EMAIL_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.+\-]*@[A-Za-z0-9][A-Za-z0-9\-]*(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"
)
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")


def validate_resume_dataset(data: object, dataset_dir: Path | None = None) -> DatasetSchemaSummary:
    issues: list[DatasetSchemaIssue] = []

    def error(path: str, message: str) -> None:
        issues.append(DatasetSchemaIssue("error", path, message))

    def warning(path: str, message: str) -> None:
        issues.append(DatasetSchemaIssue("warning", path, message))

    if not isinstance(data, list):
        error("$", "Dataset root must be a list of resume objects.")
        return DatasetSchemaSummary(total_items=0, error_count=1, warning_count=0, issues=issues)

    seen_files: set[str] = set()

    for idx, item in enumerate(data):
        base = f"$[{idx}]"
        if not isinstance(item, dict):
            error(base, "Each dataset item must be an object.")
            continue

        missing = sorted(_REQUIRED_TOP_LEVEL_KEYS - set(item.keys()))
        for key in missing:
            error(f"{base}.{key}", "Missing required top-level field.")

        extra = sorted(set(item.keys()) - _REQUIRED_TOP_LEVEL_KEYS)
        for key in extra:
            warning(f"{base}.{key}", "Unknown top-level field; evaluator will ignore it.")

        file_name = item.get("file")
        if not isinstance(file_name, str) or not file_name.strip():
            error(f"{base}.file", "File must be a non-empty string.")
        else:
            normalized = file_name.strip()
            if normalized in seen_files:
                error(f"{base}.file", "Duplicate file entry in dataset.")
            seen_files.add(normalized)
            if dataset_dir is not None and not (dataset_dir / normalized).exists():
                error(f"{base}.file", "Referenced PDF file does not exist in dataset directory.")

        _validate_personal_info(item.get("personal_info"), base, error, warning)
        _validate_entries(
            item.get("education"),
            f"{base}.education",
            required_keys=("institution", "degree", "field_of_study", "start", "end", "gpa"),
            list_string_fields=(),
            error=error,
            warning=warning,
        )
        _validate_entries(
            item.get("experience"),
            f"{base}.experience",
            required_keys=("company", "title", "start", "end", "location", "bullets"),
            list_string_fields=("bullets",),
            error=error,
            warning=warning,
        )
        _validate_entries(
            item.get("projects"),
            f"{base}.projects",
            required_keys=("name", "description", "technologies", "url"),
            list_string_fields=("technologies",),
            error=error,
            warning=warning,
        )
        _validate_string_list(item.get("skills"), f"{base}.skills", error)
        _validate_string_list(item.get("certifications"), f"{base}.certifications", error)

    error_count = sum(1 for issue in issues if issue.level == "error")
    warning_count = sum(1 for issue in issues if issue.level == "warning")
    return DatasetSchemaSummary(
        total_items=len(data),
        error_count=error_count,
        warning_count=warning_count,
        issues=issues,
    )


def _validate_personal_info(value: object, base: str, error, warning) -> None:
    if not isinstance(value, dict):
        error(f"{base}.personal_info", "personal_info must be an object.")
        return

    extra = sorted(set(value.keys()) - _OPTIONAL_PERSONAL_INFO_KEYS)
    for key in extra:
        warning(f"{base}.personal_info.{key}", "Unknown personal_info field; validator ignores it.")

    for key in ("name", "email", "phone", "location"):
        field_value = value.get(key)
        if field_value is not None and not isinstance(field_value, str):
            error(f"{base}.personal_info.{key}", "Field must be a string or empty.")

    email = value.get("email")
    if isinstance(email, str) and email.strip() and not _EMAIL_RE.fullmatch(email.strip()):
        warning(f"{base}.personal_info.email", "Email does not look normalized.")

    phone = value.get("phone")
    if isinstance(phone, str) and phone.strip() and not _PHONE_RE.search(phone.strip()):
        warning(f"{base}.personal_info.phone", "Phone number does not look normalized.")

    links = value.get("links", [])
    if links is None:
        return
    if not isinstance(links, list):
        error(f"{base}.personal_info.links", "links must be a list.")
        return
    for idx, item in enumerate(links):
        link_base = f"{base}.personal_info.links[{idx}]"
        if not isinstance(item, dict):
            error(link_base, "Each link must be an object.")
            continue
        for key in ("label", "url"):
            if key not in item:
                error(f"{link_base}.{key}", "Missing required link field.")
            elif not isinstance(item[key], str):
                error(f"{link_base}.{key}", "Link field must be a string.")
        url = item.get("url")
        if isinstance(url, str) and url.strip():
            normalized = url.strip()
            if not (
                normalized.startswith(("http://", "https://"))
                or normalized.startswith("www.")
                or _URL_PLACEHOLDER_RE.search(normalized)
            ):
                warning(f"{link_base}.url", "Link URL is present but not fully normalized.")


def _validate_entries(
    value: object,
    base: str,
    required_keys: tuple[str, ...],
    list_string_fields: tuple[str, ...],
    error,
    warning,
) -> None:
    if not isinstance(value, list):
        error(base, "Field must be a list.")
        return
    for idx, item in enumerate(value):
        entry_base = f"{base}[{idx}]"
        if not isinstance(item, dict):
            error(entry_base, "Each entry must be an object.")
            continue
        for key in required_keys:
            if key not in item:
                error(f"{entry_base}.{key}", "Missing required field.")
                continue
            field_value = item.get(key)
            if key in list_string_fields:
                if not isinstance(field_value, list):
                    error(f"{entry_base}.{key}", "Field must be a list of strings.")
                else:
                    for value_idx, list_item in enumerate(field_value):
                        if not isinstance(list_item, str):
                            error(f"{entry_base}.{key}[{value_idx}]", "List item must be a string.")
            elif field_value is not None and not isinstance(field_value, str):
                error(f"{entry_base}.{key}", "Field must be a string or empty.")

        extra = sorted(set(item.keys()) - set(required_keys))
        for key in extra:
            warning(f"{entry_base}.{key}", "Unknown field; evaluator ignores it.")


def _validate_string_list(value: object, base: str, error) -> None:
    if not isinstance(value, list):
        error(base, "Field must be a list of strings.")
        return
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            error(f"{base}[{idx}]", "List item must be a string.")
