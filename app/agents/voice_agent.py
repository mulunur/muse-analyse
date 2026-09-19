"""Агент, извлекающий творческий голос артиста."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.agents.llm import invoke_structured
from app.agents.state import GrowthState, VoiceProfile

_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Ты анализируешь материалы независимого музыкального артиста, чтобы описать его творческий голос.\n"
            "Определи тон (2-4 прилагательных), повторяющиеся темы и образы, а также слова и клише, которых следует избегать.\n"
            "Не придумывай факты. Если материалов мало, укажи это в tone или recurring_themes.",
        ),
        ("human", "Материалы:\n{materials}"),
    ]
)


def voice_agent(state: GrowthState) -> dict[str, VoiceProfile]:
    """Анализирует переданные артистом материалы одним вызовом LLM."""
    materials = "\n\n---\n\n".join(state.artist_materials)
    profile = invoke_structured(_PROMPT, VoiceProfile, {"materials": materials})
    if profile is None:
        profile = VoiceProfile(
            tone="сдержанный, авторский",
            recurring_themes=[],
            avoid_list=[],
        )
    return {"voice_profile": profile}
