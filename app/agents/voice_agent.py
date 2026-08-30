"""Агент, извлекающий творческий голос артиста."""

from __future__ import annotations

from app.agents.llm import ask_llm, parse_json_response
from app.agents.state import GrowthState, VoiceProfile


def voice_agent(state: GrowthState) -> dict[str, VoiceProfile]:
    """Анализирует переданные артистом материалы одним вызовом LLM."""
    materials = "\n\n---\n\n".join(state.artist_materials)
    prompt = (
        "Ты анализируешь материалы независимого музыкального артиста, чтобы описать его творческий голос.\n"
        "Определи тон (2-4 прилагательных), повторяющиеся темы и образы, а также слова и клише, которых следует избегать.\n"
        "Не придумывай факты. Если материалов мало, укажи это в tone или recurring_themes.\n"
        "Ответь строго JSON по схеме VoiceProfile.\n\nМатериалы:\n" + materials
    )
    parsed = parse_json_response(ask_llm(prompt), {})
    try:
        profile = VoiceProfile.model_validate(parsed)
    except (TypeError, ValueError):
        profile = VoiceProfile(
            tone="сдержанный, авторский",
            recurring_themes=[],
            avoid_list=[],
        )
    return {"voice_profile": profile}