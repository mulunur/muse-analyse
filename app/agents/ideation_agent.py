"""Agent that comes up with the idea cards."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app.agents.llm import invoke_structured
from app.agents.state import ContentIdea, GrowthState


class _IdeasResponse(BaseModel):
    """Wrapper: structured output needs an object at the root of the answer."""

    ideas: list[ContentIdea]


_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Ты придумываешь идеи контента для независимого музыкального артиста. Используй аудио-характеристики, "
            "творческий голос и рыночный контекст. Контекст используй ТОЛЬКО для формата и площадки, не для тона. "
            "Сгенерируй 5-8 разных идей в разных форматах. Только хук и обоснование, без полного текста. "
            "Голос имеет приоритет. Поле id — короткий уникальный идентификатор идеи (например, idea-1).",
        ),
        ("human", "Аудио: {features}\nГолос: {profile}\nРынок: {trends}"),
    ]
)


def ideation_agent(state: GrowthState) -> dict[str, list[ContentIdea]]:
    """Comes up with 5-8 rough ideas, without turning them into finished posts."""
    response = invoke_structured(
        _PROMPT,
        _IdeasResponse,
        {
            "features": state.audio_features.model_dump() if state.audio_features else {},
            "profile": state.voice_profile.model_dump() if state.voice_profile else {},
            "trends": state.trend_context.model_dump() if state.trend_context else {},
        },
    )
    ideas = response.ideas if response else []
    return {"content_ideas": ideas[:8]}
