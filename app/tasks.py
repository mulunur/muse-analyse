"""Celery app and background tasks: audio analysis and Growth Copilot.

Tasks run in a separate worker process, not inside the FastAPI event loop,
so a long Essentia analysis or a chain of LLM calls in Growth Copilot no
longer freezes the whole server while it works.
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

# For tests only: run a task synchronously, with no broker and no worker, but
# still store the result in the backend so AsyncResult(id) can find it, just
# like in production minus a real Celery worker. This has to be set through an
# environment variable BEFORE this module is imported: once a task is bound to
# the app, Celery no longer lets you change these two flags on the fly.
_EAGER_FOR_TESTS = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=CELERY_RESULT_EXPIRES_SECONDS,
    # Tasks are heavy and slow, so do not acknowledge them up front: that way a
    # crashed worker cannot silently "lose" a task.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=_EAGER_FOR_TESTS,
    task_store_eager_result=_EAGER_FOR_TESTS,
)


def _state_to_json(values: dict[str, Any]) -> dict[str, Any]:
    """Graph state in a form the Celery JSON serializer can handle.

    Graph nodes return fields as Pydantic objects (for example list[ContentIdea]),
    not dicts. ``growth_graph.invoke()`` and ``get_state().values`` hand them back
    as they are, and a plain json.dumps on such a dict fails.
    """
    from app.agents.state import GrowthState

    return GrowthState.model_validate(values).model_dump(mode="json")


@celery_app.task(name="analyze_track")
def analyze_track_task(file_path: str, filename: str) -> dict[str, Any]:
    """Analyses the uploaded track and generates a review; the file is deleted no matter what."""
    from app.audio_analysis import AudioAnalysisError, analyze_audio
    from app.review_generator import generate_review

    path = Path(file_path)
    try:
        features = analyze_audio(path)
        review = generate_review(features)
        return {"success": True, "filename": filename, "features": features, "review": review}
    except AudioAnalysisError as exc:
        # The file is broken or in an unsupported format, so retrying will not help.
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.exception("Неожиданная ошибка анализа трека")
        return {"success": False, "error": f"Внутренняя ошибка: {exc}"}
    finally:
        path.unlink(missing_ok=True)


@celery_app.task(name="growth_start")
def growth_start_task(audio_path: str, artist_materials: list[str], thread_id: str) -> dict[str, Any]:
    """Runs the graph until it pauses for the artist to pick ideas."""
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
    """Resumes the graph with the chosen ideas and returns the finished drafts."""
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
