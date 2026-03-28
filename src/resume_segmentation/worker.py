from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from celery import Celery

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aria_worker",
    broker=_REDIS_URL,
    backend=_REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)


@celery_app.task(bind=True, name="aria.process_resume")
def process_resume_task(self, file_bytes_hex: str, filename: str) -> dict:
    from .services.pipeline import ARIEPipeline
    from .settings import settings

    self.update_state(state="PROCESSING", meta={"filename": filename, "stage": "extracting"})

    tmp_path: Path | None = None
    try:
        file_bytes = bytes.fromhex(file_bytes_hex)

        suffix = Path(filename).suffix.lower() if filename else ".pdf"
        if suffix not in {".pdf", ".docx"}:
            suffix = ".pdf"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)

        pipeline = ARIEPipeline(output_dir=settings.output_dir)

        self.update_state(state="PROCESSING", meta={"filename": filename, "stage": "parsing"})
        result = pipeline.extract(tmp_path)

        if not result.success:
            return {"success": False, "error": result.error, "filename": filename}

        return {"success": True, "filename": filename, "data": result.to_dict()}

    except Exception as exc:
        return {"success": False, "error": str(exc), "filename": filename}

    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
