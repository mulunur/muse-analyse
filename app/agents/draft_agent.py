"""Агент развёртывания выбранных идей."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.agents.llm import invoke_text
from app.agents.state import GrowthState

_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Разверни идею контента в полный финальный текст, готовый к публикации. "
            "Строго придерживайся голоса артиста: тон {tone}, избегай: {avoid_list}. "
            "Регистр: {register}. Верни только финальный текст.",
        ),
        (
            "human",
            "Идея: {idea}\nАудио: {features}\nЗамечание проверки: {critique}",
        ),
    ]
)


def draft_agent(state: GrowthState) -> dict[str, dict[str, str]]:
    """Готовит отдельный текст для каждой выбранной карточки."""
    ideas = {idea.id: idea for idea in state.content_ideas}
    features = state.audio_features.model_dump() if state.audio_features else {}
    profile = state.voice_profile
    drafts: dict[str, str] = {}
    for idea_id in state.selected_idea_ids:
        idea = ideas.get(idea_id)
        if not idea:
            continue
        drafts[idea_id] = (
            invoke_text(
                _PROMPT,
                {
                    "tone": profile.tone if profile else "авторский",
                    "avoid_list": profile.avoid_list if profile else [],
                    "register": profile.voice_register if profile else "classical",
                    "idea": idea.model_dump(),
                    "features": features,
                    "critique": state.critique_feedback or "нет",
                },
            )
            or idea.hook
        )
    return {"drafts": drafts, "retry_count": state.retry_count + 1}
