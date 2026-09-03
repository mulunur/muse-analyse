"""Агент развёртывания выбранных идей."""

from __future__ import annotations

from app.agents.llm import ask_llm
from app.agents.state import GrowthState


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
        prompt = (
            "Разверни следующую идею контента в полный финальный текст, готовый к публикации. "
            f"Строго придерживайся голоса артиста: тон {profile.tone if profile else 'авторский'}, "
            f"избегай: {profile.avoid_list if profile else []}. "
            f"Регистр: {profile.voice_register if profile else 'classical'}. Верни только финальный текст.\n"
            f"Идея: {idea.model_dump()}\nАудио: {features}\n"
            f"Замечание проверки: {state.critique_feedback or 'нет'}"
        )
        drafts[idea_id] = ask_llm(prompt) or idea.hook
    return {"drafts": drafts, "retry_count": state.retry_count + 1}