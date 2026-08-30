"""FastAPI-приложение Muse Analyse."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
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
from app.llm_providers import LLMProviderFactory
from app.rag.knowledge import get_knowledge_base
from app.review_generator import generate_review

try:
    from langgraph.types import Command
    from app.agents.graph import growth_graph
except ImportError:
    Command = None  # type: ignore[assignment,misc]
    growth_graph = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Muse Analyse",
    description="Музыкальный анализ с Essentia и AI-критика",
    version=__version__,
)


class GrowthSelection(BaseModel):
    """Выбор карточек после паузы графа."""

    thread_id: str
    selected_idea_ids: list[str] = Field(min_length=1)

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
    llm_providers = LLMProviderFactory.list_available_providers()
    rag_status = get_knowledge_base().get_status()
    return {
        "status": "ok",
        "version": __version__,
        "essentia_available": ESSENTIA_AVAILABLE,
        "essentia_error": ESSENTIA_ERROR,
        "llm_providers": llm_providers,
        "rag": rag_status,
    }


@app.get("/api/providers")
async def list_providers():
    """Возвращает список доступных LLM провайдеров."""
    providers = LLMProviderFactory.list_available_providers()
    return {
        "available": providers,
        "description": {
            "openai": "OpenAI GPT (требует OPENAI_API_KEY)",
            "claude": "Anthropic Claude (требует ANTHROPIC_API_KEY)",
            "ollama": "Локальный Ollama (требует ollama serve)",
            "nemotron": "NVIDIA Nemotron API (требует NEMOTRON_API_KEY)",
        }
    }


@app.get("/api/rag/status")
async def rag_status():
    """Статус RAG: индекс, источники, количество чанков."""
    return get_knowledge_base().get_status()


@app.post("/api/rag/reindex")
async def rag_reindex(force: bool = True):
    """Переиндексация PDF из data/knowledge/."""
    result = get_knowledge_base().build_index(force=force)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


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


@app.post("/api/growth/start")
async def growth_start(
    file: UploadFile = File(...),
    artist_materials: list[str] = Form(default=[]),
):
    """Запускает Growth Copilot до выбора карточек артистом."""
    if growth_graph is None:
        raise HTTPException(status_code=503, detail="Growth Copilot недоступен: установите langgraph")
    if not file.filename or Path(file.filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат аудиофайла")
    content = await file.read()
    if not content or len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Пустой файл или превышен лимит размера")
    suffix = Path(file.filename).suffix.lower()
    file_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    async with aiofiles.open(file_path, "wb") as target:
        await target.write(content)
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}
    try:
        growth_graph.invoke(
            {"audio_path": str(file_path), "artist_materials": artist_materials},
            config,
        )
        snapshot = growth_graph.get_state(config)
        return {"thread_id": thread_id, "content_ideas": snapshot.values.get("content_ideas", [])}
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        logger.exception("Ошибка запуска Growth Copilot")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/growth/select")
async def growth_select(selection: GrowthSelection):
    """Возобновляет граф с выбранными карточками и возвращает черновики."""
    if growth_graph is None or Command is None:
        raise HTTPException(status_code=503, detail="Growth Copilot недоступен")
    config = {"configurable": {"thread_id": selection.thread_id}}
    try:
        result = growth_graph.invoke(
            Command(resume={"selected_idea_ids": selection.selected_idea_ids}),
            config,
        )
        snapshot = growth_graph.get_state(config)
        audio_path = snapshot.values.get("audio_path")
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)
        return {"drafts": result.get("drafts", snapshot.values.get("drafts", {}))}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/growth/status/{thread_id}")
async def growth_status(thread_id: str):
    """Возвращает текущее состояние потока Growth Copilot."""
    if growth_graph is None:
        raise HTTPException(status_code=503, detail="Growth Copilot недоступен")
    snapshot = growth_graph.get_state({"configurable": {"thread_id": thread_id}})
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="Поток не найден")
    return snapshot.values
