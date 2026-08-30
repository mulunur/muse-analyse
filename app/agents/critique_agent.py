"""Проверка черновиков и маршрутизация повторов."""

from __future__ import annotations

from typing import Literal

from app.agents.llm import ask_llm, parse_json_response
from app.agents.state import GrowthState


def critique_agent(state: GrowthState) -> dict[str, object]:
    """Оценивает черновики по голосу, запретным словам и темам."""
    profile = state.voice_profile
    prompt = (
        "Проверь черновики: соответствие тону, отсутствие слов из avoid_list и тематическую консистентность. "
        "Верни строго JSON {\"passed\": bool, \"feedback\": str}.\n"
        f"Тон: {profile.tone if profile else ''}; темы: {profile.recurring_themes if profile else []}; "
        f"avoid_list: {profile.avoid_list if profile else []}\nЧерновики: {state.drafts}"
    )
    parsed = parse_json_response(ask_llm(prompt), {})
    passed = bool(parsed.get("passed", True)) if isinstance(parsed, dict) else True
    feedback = str(parsed.get("feedback", "Проверка пройдена.")) if isinstance(parsed, dict) else "Проверка пройдена."
    return {"critique_passed": passed, "critique_feedback": feedback}


def critique_router(state: GrowthState) -> Literal["retry", "done"]:
    """Возвращает retry максимум для двух повторных черновиков."""
    if not state.critique_passed and state.retry_count < 2:
        return "retry"
    return "done"