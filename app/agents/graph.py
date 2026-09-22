"""Граф Growth Copilot на LangGraph."""

from __future__ import annotations

import logging
from typing import Any

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt
except ImportError:  # Доступность проверяется при установке requirements.txt.
    StateGraph = None  # type: ignore[assignment,misc]
    START = END = None  # type: ignore[assignment]
    Command = Any  # type: ignore[assignment,misc]
    interrupt = None  # type: ignore[assignment]

from app.agents.critique_agent import critique_agent, critique_router
from app.agents.draft_agent import draft_agent
from app.agents.ideation_agent import ideation_agent
from app.agents.state import GrowthState
from app.agents.trend_agent import trend_agent
from app.agents.voice_agent import voice_agent
from app.audio_analysis import analyze_audio
from app.config import GROWTH_CHECKPOINT_DB_PATH

logger = logging.getLogger(__name__)


def extract_audio_features(state: GrowthState) -> dict[str, object]:
    """Переиспользует существующий Essentia-анализ."""
    if not state.audio_path:
        raise ValueError("В состоянии не указан путь к аудиофайлу")
    return {"audio_features": analyze_audio(state.audio_path)}


def selection_interrupt(state: GrowthState) -> dict[str, list[str]]:
    """Останавливает граф и принимает IDs выбранных артистом идей."""
    if interrupt is None:
        raise RuntimeError("LangGraph не установлен")
    selection = interrupt({"content_ideas": [idea.model_dump() for idea in state.content_ideas]})
    if isinstance(selection, dict):
        selected_ids = selection.get("selected_idea_ids", [])
    else:
        selected_ids = selection
    if not isinstance(selected_ids, list):
        raise ValueError("selected_idea_ids должен быть списком")
    valid_ids = {idea.id for idea in state.content_ideas}
    return {"selected_idea_ids": [str(item) for item in selected_ids if str(item) in valid_ids]}


def _build_checkpointer() -> Any:
    """Хранилище состояния графа между шагами (`/api/growth/start` и `/api/growth/select`).

    Эти два запроса могут выполняться в разных процессах — например, в разных
    Celery-воркерах, — поэтому состояние не может жить только в памяти одного
    процесса. SQLite-файл на общем томе (см. docker-compose.yml) делает его
    общим между веб-процессом и воркером ценой одного файла, без отдельного
    сервиса БД. Если файл недоступен (нет прав на каталог и т.п.), используется
    MemorySaver — граф работает, но только в пределах одного процесса.
    """
    try:
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(str(GROWTH_CHECKPOINT_DB_PATH), check_same_thread=False, timeout=30)
        saver = SqliteSaver(conn)
        saver.setup()
        return saver
    except Exception as exc:
        logger.warning(
            "SqliteSaver недоступен (%s) — состояние Growth Copilot будет жить "
            "только в памяти текущего процесса. С Celery это ломает "
            "/api/growth/select, если start и select достанутся разным воркерам.",
            exc,
        )
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()


def build_growth_graph() -> Any:
    """Компилирует граф Growth Copilot."""
    if StateGraph is None:
        raise RuntimeError("Установите зависимости langgraph и langchain-core")

    builder = StateGraph(GrowthState)
    builder.add_node("extract_audio_features", extract_audio_features)
    builder.add_node("voice_agent", voice_agent)
    builder.add_node("trend_agent", trend_agent)
    builder.add_node("ideation_agent", ideation_agent)
    builder.add_node("selection_interrupt", selection_interrupt)
    builder.add_node("draft_agent", draft_agent)
    builder.add_node("critique_agent", critique_agent)
    builder.add_edge(START, "extract_audio_features")
    builder.add_edge("extract_audio_features", "voice_agent")
    builder.add_edge("extract_audio_features", "trend_agent")
    builder.add_edge("voice_agent", "ideation_agent")
    builder.add_edge("trend_agent", "ideation_agent")
    builder.add_edge("ideation_agent", "selection_interrupt")
    builder.add_edge("selection_interrupt", "draft_agent")
    builder.add_edge("draft_agent", "critique_agent")
    builder.add_conditional_edges(
        "critique_agent",
        critique_router,
        {"retry": "draft_agent", "done": END},
    )
    return builder.compile(checkpointer=_build_checkpointer())


growth_graph = build_growth_graph() if StateGraph is not None else None
