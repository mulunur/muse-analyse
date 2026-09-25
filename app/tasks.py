"""Celery-приложение и фоновые задачи: анализ аудио и Growth Copilot.

Задачи выполняются в отдельном процессе-воркере, а не внутри event loop
FastAPI — долгий Essentia-анализ или цепочка вызовов LLM в Growth Copilot
больше не блокируют сервер целиком на время своей работы.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from celery import Celery

from app.config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_RESULT_EXPIRES_SECONDS,
)

logger = logging.getLogger(__name__)

celery_app = Celery(
    "muse_analyse",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Только для тестов: выполнить задачу синхронно, без брокера и воркера, и
# всё же записать результат в backend, чтобы AsyncResult(id) его нашёл — как
# и в проде, но без реального Celery-воркера. Обязательно задавать через
# переменную окружения ДО импорта этого модуля: once задача привязана к
# приложению, изменить эти два флага на лету Celery уже не позволяет.
_EAGER_FOR_TESTS = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=CELERY_RESULT_EXPIRES_SECONDS,
    # Задачи тяжёлые и небыстрые — не подтверждать их выполненными заранее,
    # чтобы упавший воркер не «потерял» задачу молча.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=_EAGER_FOR_TESTS,
    task_store_eager_result=_EAGER_FOR_TESTS,
)


def _state_to_json(values: dict[str, Any]) -> dict[str, Any]:
    """Состояние графа в виде, безопасном для JSON-сериализатора Celery.

    Узлы графа возвращают поля как объекты Pydantic (например, list[ContentIdea]),
    а не как словари. ``growth_graph.invoke()``/``get_state().values`` отдают их
    как есть — обычный json.dumps на таком словаре падает.
    """
    from app.agents.state import GrowthState

    return GrowthState.model_validate(values).model_dump(mode="json")


@celery_app.task(name="analyze_track")
def analyze_track_task(file_path: str, filename: str) -> dict[str, Any]:
    """Анализирует загруженный трек и генерирует обзор; файл удаляется в любом случае."""
    from app.audio_analysis import AudioAnalysisError, analyze_audio
    from app.review_generator import generate_review

    path = Path(file_path)
    try:
        features = analyze_audio(path)
        review = generate_review(features)
        return {"success": True, "filename": filename, "features": features, "review": review}
    except AudioAnalysisError as exc:
        # Файл повреждён или в неподдерживаемом формате — повтор не поможет.
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.exception("Неожиданная ошибка анализа трека")
        return {"success": False, "error": f"Внутренняя ошибка: {exc}"}
    finally:
        path.unlink(missing_ok=True)


@celery_app.task(name="growth_start")
def growth_start_task(audio_path: str, artist_materials: list[str], thread_id: str) -> dict[str, Any]:
    """Прогоняет граф до паузы на выборе идей артистом."""
    from app.agents.graph import growth_graph

    config = {"configurable": {"thread_id": thread_id}}
    try:
        growth_graph.invoke(
            {"audio_path": audio_path, "artist_materials": artist_materials},
            config,
        )
        state = _state_to_json(growth_graph.get_state(config).values)
        return {"success": True, "thread_id": thread_id, "content_ideas": state["content_ideas"]}
    except Exception as exc:
        Path(audio_path).unlink(missing_ok=True)
        logger.exception("Ошибка запуска Growth Copilot")
        return {"success": False, "error": str(exc)}


@celery_app.task(name="growth_select")
def growth_select_task(thread_id: str, selected_idea_ids: list[str]) -> dict[str, Any]:
    """Возобновляет граф с выбранными идеями и возвращает готовые черновики."""
    from langgraph.types import Command

    from app.agents.graph import growth_graph

    config = {"configurable": {"thread_id": thread_id}}
    try:
        growth_graph.invoke(Command(resume={"selected_idea_ids": selected_idea_ids}), config)
        state = _state_to_json(growth_graph.get_state(config).values)
        return {"success": True, "drafts": state["drafts"]}
    except Exception as exc:
        logger.exception("Ошибка выбора идей Growth Copilot")
        return {"success": False, "error": str(exc)}
    finally:
        snapshot = growth_graph.get_state(config)
        audio_path = snapshot.values.get("audio_path") if snapshot else None
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)
