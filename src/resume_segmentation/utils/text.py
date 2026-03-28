import re

from ..models.resume import BoundingBox


def clean_text(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return text.strip()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def box_area(box: BoundingBox) -> float:
    return abs(box.x1 - box.x0) * abs(box.y1 - box.y0)


def box_contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    if outer.page != inner.page:
        return False
    ox0, ox1 = min(outer.x0, outer.x1), max(outer.x0, outer.x1)
    oy0, oy1 = min(outer.y0, outer.y1), max(outer.y0, outer.y1)
    ix0, ix1 = min(inner.x0, inner.x1), max(inner.x0, inner.x1)
    iy0, iy1 = min(inner.y0, inner.y1), max(inner.y0, inner.y1)
    return ox0 <= ix0 and oy0 <= iy0 and ox1 >= ix1 and oy1 >= iy1


def boxes_overlap(a: BoundingBox, b: BoundingBox) -> bool:
    if a.page != b.page:
        return False
    ax0, ax1 = min(a.x0, a.x1), max(a.x0, a.x1)
    ay0, ay1 = min(a.y0, a.y1), max(a.y0, a.y1)
    bx0, bx1 = min(b.x0, b.x1), max(b.x0, b.x1)
    by0, by1 = min(b.y0, b.y1), max(b.y0, b.y1)
    return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)


def is_valid_url(url: str) -> bool:
    return (
        isinstance(url, str)
        and url.startswith(("http://", "https://"))
        and "." in url
        and len(url) > 10
    )


def split_lines_clean(text: str) -> list:
    return [l.strip() for l in text.splitlines() if l.strip()]

