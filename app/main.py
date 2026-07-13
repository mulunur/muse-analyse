"""FastAPI-приложение Muse Analyse."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import aiofiles
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.audio_analysis import (
    ESSENTIA_AVAILABLE,
    ESSENTIA_ERROR,
    AudioAnalysisError,
    analyze_audio,
)
from app.config import MAX_UPLOAD_SIZE_BYTES, SUPPORTED_EXTENSIONS, STATIC_DIR, UPLOAD_DIR
from app.review_generator import generate_review

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Muse Analyse",
    description="Музыкальный анализ с Essentia и AI-критика",
    version=__version__,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Muse Analyse API", "docs": "/docs"}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": __version__,
        "essentia_available": ESSENTIA_AVAILABLE,
        "essentia_error": ESSENTIA_ERROR,
    }


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    """Загрузка аудио, анализ Essentia и генерация обзора."""
    if not ESSENTIA_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Essentia не установлена",
                "message": ESSENTIA_ERROR,
                "hint": "См. README — раздел установки Essentia на macOS",
            },
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Имя файла не указано")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Неподдерживаемый формат",
                "supported": sorted(SUPPORTED_EXTENSIONS),
                "received": suffix,
            },
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Пустой файл")

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Файл превышает лимит {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} МБ",
        )

    safe_name = f"{uuid.uuid4().hex}{suffix}"
    file_path: Path | None = UPLOAD_DIR / safe_name

    try:
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        features = analyze_audio(file_path)
        review = generate_review(features)

        return {
            "success": True,
            "filename": file.filename,
            "features": features,
            "review": review,
        }

    except AudioAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Неожиданная ошибка анализа")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка: {exc}") from exc
    finally:
        if file_path and file_path.exists():
            file_path.unlink(missing_ok=True)
