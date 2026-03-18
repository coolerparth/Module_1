from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..services.pipeline import ARIEPipeline
from ..settings import settings

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
)

_pipeline = ARIEPipeline(output_dir=settings.output_dir)


@app.post("/extract")
async def extract_resume(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must have a .pdf extension.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        if tmp_path.stat().st_size > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {settings.max_file_size_bytes // (1024 * 1024)} MB limit.",
            )
        if tmp_path.stat().st_size < 100:
            raise HTTPException(status_code=400, detail="File appears to be empty or corrupt.")

        result = _pipeline.extract(tmp_path)

        if not result.success:
            raise HTTPException(status_code=422, detail=result.error)

        output_dict = result.to_dict()
        _pipeline._processor.save_output({"profile": output_dict["profile"]}, file.filename)
        return JSONResponse(content=output_dict)

    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/quality")
async def quality_report(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must have a .pdf extension.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = _pipeline.extract(tmp_path)
        if not result.success:
            raise HTTPException(status_code=422, detail=result.error)
        qr = result.enrichment.quality_report
        return JSONResponse(content=qr.to_dict() if qr else {})
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.package_name,
        "version": settings.app_version,
        "output_directory": str(settings.output_dir),
    }
