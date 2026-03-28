from __future__ import annotations

from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
_SRC_PACKAGE = _PACKAGE_ROOT.parent / "src" / "resume_segmentation"

if _SRC_PACKAGE.exists():
    __path__.append(str(_SRC_PACKAGE))
