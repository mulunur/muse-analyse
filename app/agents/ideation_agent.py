"""Агент карточек идей."""

from __future__ import annotations

from typing import Any

from app.agents.llm import ask_llm, parse_json_response
from app.agents.state import ContentIdea, GrowthState


def ideation_agent(state: GrowthState) -> dict[str, list[ContentIdea]]:
    """Создаёт 5-8 набросков, не превращая их в готовые публикации."""
    features = state.audio_features.model_dump() if state.audio_features else {}
    profile = state.voice_profile.model_dump() if state.voice_profile else {}
    trends = state.trend_context.model_dump() if state.trend_context else {}
    prompt = (
        "Ты придумываешь идеи контента для независимого музыкального артиста. Используй аудио-характеристики, "
        "творческий голос и рыночный контекст. Контекст используй ТОЛЬКО для формата и площадки, не для тона. "
        "Сгенерируй 5-8 разных идей в форматах instagram_caption, playlist_pitch_email, press_quote_card, "
        "story_series, bio_snippet. Только хук и обоснование, без полного текста. Голос имеет приоритет. Ответь JSON-массивом.\n"
        f"Аудио: {features}\nГолос: {profile}\nРынок: {trends}"
    )
    parsed: Any = parse_json_response(ask_llm(prompt), [])
    ideas: list[ContentIdea] = []
    if isinstance(parsed, list):
        for item in parsed:
            try:
                ideas.append(ContentIdea.model_validate(item))
            except (TypeError, ValueError):
                continue
    return {"content_ideas": ideas[:8]}