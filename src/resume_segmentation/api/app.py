from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..services.pipeline import ARIEPipeline
from ..settings import settings

_USE_ASYNC = os.getenv("ARIA_ASYNC", "false").lower() == "true"

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline = ARIEPipeline(output_dir=settings.output_dir)


def _upload_suffix(filename: str | None) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".docx"):
        return ".docx"
    return ".pdf"


def _validate_upload(file: UploadFile) -> None:
    lower = (file.filename or "").lower()
    if not lower.endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files accepted.")
    allowed_types = {
        "application/pdf",
        "application/octet-stream",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Content-type must be PDF or DOCX.")


async def _read_and_validate_upload(file: UploadFile) -> bytes:
    _validate_upload(file)
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_file_size_bytes // (1024*1024)}MB limit.",
        )
    if len(file_bytes) < 100:
        raise HTTPException(status_code=400, detail="File appears empty or corrupt.")
    return file_bytes


@app.post("/extract")
async def extract_resume(file: UploadFile = File(...)):
    file_bytes = await _read_and_validate_upload(file)

    if _USE_ASYNC:
        from ..worker import process_resume_task
        task = process_resume_task.delay(file_bytes.hex(), file.filename)
        return JSONResponse(
            status_code=202,
            content={
                "job_id": task.id,
                "status": "queued",
                "filename": file.filename,
                "poll_url": f"/jobs/{task.id}",
            },
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=_upload_suffix(file.filename)) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        result = _pipeline.extract(tmp_path)
        if not result.success:
            raise HTTPException(status_code=422, detail=result.error)
        return JSONResponse(content=result.to_dict())
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/extract/batch")
async def extract_batch(files: list[UploadFile] = File(...)):
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Max 50 files per batch.")

    jobs = []
    for file in files:
        try:
            file_bytes = await _read_and_validate_upload(file)
            if _USE_ASYNC:
                from ..worker import process_resume_task
                task = process_resume_task.delay(file_bytes.hex(), file.filename)
                jobs.append({"filename": file.filename, "job_id": task.id, "status": "queued", "poll_url": f"/jobs/{task.id}"})
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=_upload_suffix(file.filename)) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = Path(tmp.name)
                try:
                    result = _pipeline.extract(tmp_path)
                    jobs.append({"filename": file.filename, "status": "done", "data": result.to_dict() if result.success else None, "error": result.error if not result.success else None})
                finally:
                    tmp_path.unlink(missing_ok=True)
        except HTTPException as exc:
            jobs.append({"filename": file.filename, "status": "rejected", "error": exc.detail})
        except Exception as exc:
            jobs.append({"filename": file.filename, "status": "error", "error": str(exc)})

    return JSONResponse(content={"total": len(files), "jobs": jobs})


@app.get("/jobs/{job_id}")
async def get_job_result(job_id: str):
    if not _USE_ASYNC:
        raise HTTPException(status_code=400, detail="Async mode not enabled. Set ARIA_ASYNC=true.")

    from celery.result import AsyncResult
    from ..worker import celery_app

    result = AsyncResult(job_id, app=celery_app)

    if result.state == "PENDING":
        return JSONResponse(content={"job_id": job_id, "status": "queued"})

    if result.state == "PROCESSING":
        meta = result.info or {}
        return JSONResponse(content={"job_id": job_id, "status": "processing", "stage": meta.get("stage", "unknown")})

    if result.state == "SUCCESS":
        data = result.result
        return JSONResponse(content={"job_id": job_id, "status": "done", **data})

    if result.state == "FAILURE":
        return JSONResponse(status_code=500, content={"job_id": job_id, "status": "failed", "error": str(result.result)})

    return JSONResponse(content={"job_id": job_id, "status": result.state.lower()})


@app.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    from celery.result import AsyncResult
    from ..worker import celery_app
    result = AsyncResult(job_id, app=celery_app)
    return {"job_id": job_id, "status": result.state.lower(), "ready": result.ready()}


@app.post("/quality")
async def quality_report(file: UploadFile = File(...)):
    file_bytes = await _read_and_validate_upload(file)
    with tempfile.NamedTemporaryFile(delete=False, suffix=_upload_suffix(file.filename)) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)
    try:
        result = _pipeline.extract(tmp_path)
        if not result.success:
            raise HTTPException(status_code=422, detail=result.error)
        qr = result.enrichment.quality_report
        return JSONResponse(content=qr.to_dict() if qr else {})
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/validate")
async def validate_resume(file: UploadFile = File(...)):
    file_bytes = await _read_and_validate_upload(file)
    with tempfile.NamedTemporaryFile(delete=False, suffix=_upload_suffix(file.filename)) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)
    try:
        result = _pipeline.extract(tmp_path)
        if not result.success:
            raise HTTPException(status_code=422, detail=result.error)
        vr = result.enrichment.validation_report
        return JSONResponse(content=vr.to_dict() if vr else {})
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/health")
def health():
    from ..services.spacy_ner_extractor import current_model
    return {
        "status": "ok",
        "version": settings.app_version,
        "mode": "async" if _USE_ASYNC else "sync",
        "ner_model": current_model(),
        "output_directory": str(settings.output_dir),
    }


@app.get("/models")
def models():
    from ..services.model_registry import check_all_models, get_best_available
    status = check_all_models()
    return {
        "active_model": get_best_available(),
        "models": [
            {
                "name": m.name,
                "available": m.available,
                "accuracy": m.accuracy_estimate,
                "note": m.note,
            }
            for m in status
        ],
        "install_guide": {
            "best_accuracy": [
                "pip install transformers torch",
                "python -m transformers-cli download jjzha/jobbert-base-cased",
            ],
            "good_accuracy_fast": [
                "pip install spacy",
                "python -m spacy download en_core_web_trf",
            ],
            "minimum": [
                "pip install spacy",
                "python -m spacy download en_core_web_sm",
            ],
        },
    }
