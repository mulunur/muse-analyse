"""Тесты агентов Growth Copilot на LangChain без реальных вызовов LLM."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.agents import llm as llm_module
from app.agents.critique_agent import Critique, critique_agent, critique_router
from app.agents.draft_agent import draft_agent
from app.agents.ideation_agent import _IdeasResponse, ideation_agent
from app.agents.state import ContentIdea, GrowthState, TrendContext, VoiceProfile
from app.agents.trend_agent import trend_agent
from app.agents.voice_agent import voice_agent
from app.config import set_runtime_llm_setting


class FakeChatModel(GenericFakeChatModel):
    """Фейковая chat-модель: отдаёт заранее заданный объект и запоминает промпт."""

    structured_response: Any = None
    seen_prompts: list = []

    def with_structured_output(self, schema, **kwargs):
        def respond(prompt_value):
            self.seen_prompts.append(prompt_value.to_string())
            return self.structured_response

        return RunnableLambda(respond)


@pytest.fixture
def fake_llm(monkeypatch):
    """Подменяет get_chat_model; возвращает функцию для настройки ответа."""

    def install(structured_response: Any = None, text: str = "") -> FakeChatModel:
        model = FakeChatModel(
            messages=iter([AIMessage(content=text)] * 10),
            structured_response=structured_response,
            seen_prompts=[],
        )
        monkeypatch.setattr(llm_module, "get_chat_model", lambda: model)
        return model

    return install


@pytest.fixture
def llm_unavailable(monkeypatch):
    def boom():
        raise ValueError("Провайдер недоступен")

    monkeypatch.setattr(llm_module, "get_chat_model", boom)


def _idea(idea_id: str = "idea-1", hook: str = "Хук {с скобками}") -> ContentIdea:
    return ContentIdea(
        id=idea_id,
        format="instagram_caption",
        hook=hook,
        rationale="Потому что",
        voice_alignment="Совпадает",
    )


def test_voice_agent_uses_structured_output(fake_llm):
    expected = VoiceProfile(tone="тёплый", recurring_themes=["море"], avoid_list=["клише"])
    model = fake_llm(structured_response=expected)

    result = voice_agent(GrowthState(artist_materials=["текст {про} море"]))

    assert result["voice_profile"] == expected
    # Фигурные скобки из данных артиста не ломают шаблон и попадают в промпт как есть.
    assert "текст {про} море" in model.seen_prompts[0]


def test_voice_agent_falls_back_and_logs(llm_unavailable, caplog):
    result = voice_agent(GrowthState(artist_materials=["материал"]))

    assert result["voice_profile"].tone == "сдержанный, авторский"
    assert "Структурированный вызов LLM не удался" in caplog.text


def test_ideation_agent_returns_ideas_capped_at_eight(fake_llm):
    fake_llm(structured_response=_IdeasResponse(ideas=[_idea(f"idea-{i}") for i in range(10)]))

    result = ideation_agent(GrowthState())

    assert len(result["content_ideas"]) == 8


def test_ideation_agent_returns_empty_list_on_failure(llm_unavailable):
    assert ideation_agent(GrowthState()) == {"content_ideas": []}


def test_trend_agent_skips_llm_without_search_results(monkeypatch, llm_unavailable):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    context = trend_agent(GrowthState())["trend_context"]

    assert context.active_playlists == []
    assert context.genre_context_summary == "Рыночные данные пока недоступны."


def test_trend_agent_merges_search_urls_with_model_urls(monkeypatch, fake_llm):
    class FakeTavily:
        def __init__(self, api_key):
            pass

        def search(self, query, max_results):
            return {"results": [{"content": "плейлист X", "url": "https://a.example"}]}

    import sys
    import types

    monkeypatch.setenv("TAVILY_API_KEY", "test")
    monkeypatch.setitem(sys.modules, "tavily", types.SimpleNamespace(TavilyClient=FakeTavily))
    fake_llm(
        structured_response=TrendContext(
            active_playlists=["X"],
            genre_context_summary="кратко",
            source_urls=["https://a.example", "https://b.example"],
        )
    )

    context = trend_agent(GrowthState())["trend_context"]

    assert context.active_playlists == ["X"]
    assert context.source_urls == ["https://a.example", "https://b.example"]  # без дублей


def test_critique_agent_parses_boolean(fake_llm):
    fake_llm(structured_response=Critique(passed=False, feedback="уберите клише"))

    result = critique_agent(GrowthState(drafts={"idea-1": "текст"}))

    assert result == {"critique_passed": False, "critique_feedback": "уберите клише"}


def test_critique_agent_passes_on_llm_failure(llm_unavailable):
    result = critique_agent(GrowthState())

    assert result["critique_passed"] is True


def test_critique_router_retries_at_most_twice():
    assert critique_router(GrowthState(critique_passed=False, retry_count=1)) == "retry"
    assert critique_router(GrowthState(critique_passed=False, retry_count=2)) == "done"
    assert critique_router(GrowthState(critique_passed=True)) == "done"


def test_draft_agent_returns_model_text(fake_llm):
    fake_llm(text="Готовый текст поста")
    state = GrowthState(content_ideas=[_idea()], selected_idea_ids=["idea-1"])

    result = draft_agent(state)

    assert result["drafts"] == {"idea-1": "Готовый текст поста"}
    assert result["retry_count"] == 1


def test_draft_agent_falls_back_to_hook(llm_unavailable):
    state = GrowthState(content_ideas=[_idea(hook="Мой хук")], selected_idea_ids=["idea-1"])

    assert draft_agent(state)["drafts"] == {"idea-1": "Мой хук"}


def test_draft_agent_ignores_unknown_idea_ids(fake_llm):
    fake_llm(text="текст")
    state = GrowthState(content_ideas=[_idea()], selected_idea_ids=["нет-такой"])

    assert draft_agent(state)["drafts"] == {}


@pytest.mark.parametrize(
    "provider, api_key_name, expected_class",
    [
        ("openai", "OPENAI_API_KEY", "ChatOpenAI"),
        ("claude", "ANTHROPIC_API_KEY", "ChatAnthropic"),
        ("nemotron", "NEMOTRON_API_KEY", "ChatOpenAI"),
    ],
)
def test_get_chat_model_maps_provider_to_langchain_class(provider, api_key_name, expected_class):
    set_runtime_llm_setting("LLM_PROVIDER", provider)
    set_runtime_llm_setting(api_key_name, "test-key")

    model = llm_module.get_chat_model()

    assert type(model).__name__ == expected_class


def test_get_chat_model_nemotron_uses_custom_base_url():
    set_runtime_llm_setting("LLM_PROVIDER", "nemotron")
    set_runtime_llm_setting("NEMOTRON_API_KEY", "test-key")

    model = llm_module.get_chat_model()

    assert "nvidia.com" in str(model.openai_api_base)


def test_get_chat_model_raises_without_api_key():
    set_runtime_llm_setting("LLM_PROVIDER", "openai")
    set_runtime_llm_setting("OPENAI_API_KEY", "")

    with pytest.raises(ValueError):
        llm_module.get_chat_model()
