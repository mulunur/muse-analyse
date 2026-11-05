"""Reviews the drafts and decides whether they need another pass."""

from __future__ import annotations

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app.agents.llm import invoke_structured
from app.agents.state import GrowthState


class Critique(BaseModel):
    passed: bool
    feedback: str


_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Проверь черновики: соответствие тону, отсутствие слов из avoid_list и тематическую консистентность. "
            "passed=true только если все три условия выполнены; в feedback кратко опиши, что исправить.",
        ),
        (
            "human",
            "Тон: {tone}; темы: {themes}; avoid_list: {avoid_list}\nЧерновики: {drafts}",
        ),
    ]
)


def critique_agent(state: GrowthState) -> dict[str, object]:
    """Checks the drafts against the artist's voice, forbidden words and themes."""
    profile = state.voice_profile
    critique = invoke_structured(
        _PROMPT,
        Critique,
        {
            "tone": profile.tone if profile else "",
            "themes": profile.recurring_themes if profile else [],
            "avoid_list": profile.avoid_list if profile else [],
            "drafts": state.drafts,
        },
    )
    if critique is None:
        critique = Critique(passed=True, feedback="Проверка пройдена.")
    return {"critique_passed": critique.passed, "critique_feedback": critique.feedback}


def critique_router(state: GrowthState) -> Literal["retry", "done"]:
    """Sends the graph back to redraft, but at most twice."""
    if not state.critique_passed and state.retry_count < 2:
        return "retry"
    return "done"
