from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "A.R.I.E."
    app_description: str = "Automated Resume Intelligence Engine — deterministic resume parser."
    app_version: str = "3.1.0"
    package_name: str = "resume_segmentation"
    max_file_size_bytes: int = 50 * 1024 * 1024

    @property
    def project_root(self) -> Path:
        env_root = os.environ.get("ARIA_PROJECT_ROOT")
        if env_root:
            return Path(env_root)
        candidate = Path(__file__).resolve().parents[2]
        if (candidate / "data").exists() or (candidate / "main.py").exists():
            return candidate
        return Path.cwd()

    @property
    def output_dir(self) -> Path:
        env_out = os.environ.get("ARIA_OUTPUT_DIR")
        if env_out:
            return Path(env_out)
        return self.project_root / "data" / "output"


settings = Settings()
