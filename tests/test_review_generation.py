"""Тесты провайдеров как фабрик LangChain-моделей и генерации обзора без реального LLM."""

from __future__ import annotations

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from app import review_generator
from app.config import DEFAULT_CLAUDE_MODEL, set_runtime_llm_setting
from app.llm_providers import ClaudeProvider, LLMProviderFactory, get_chat_model
from app.review_generator import ReviewSections, TrackReview, generate_review

FEATURES = {
    "duration_sec": 180.5,
    "rhythm": {"bpm": 128, "beats_count": 245, "beat_confidence": 0.95, "onset_rate": 0.123},
    "tonal": {"key": "C", "scale": "minor", "key_strength": 0.88, "danceability": 0.72},
    "dynamics": {"loudness_ebu128_lufs": -9.5, "rms": 0.156, "dynamic_complexity": 0.38},
    "spectral": {
        "spectral_brightness": 0.45,
        "spectral_centroid_hz": 2340,
        "spectral_flux": 0.045,
        "mfcc_coefficients": [1, 2, 3],
    },
    "energy": 0.64,
}

SECTIONS = ReviewSections(
    summary="Резюме", rhythm="Ритм", tonality="Тональность", production="Продакшн", verdict="Вывод"
)


class StubProvider:
    """Провайдер-заглушка: structured_model возвращает заранее заданный ответ."""

    name = "stub"
    model = "stub-model"

    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.prompts: list[str] = []

    def structured_model(self, schema):
        def respond(prompt_value):
            self.prompts.append(prompt_value.to_string())
            if self.error:
                raise self.error
            return self.response

        return RunnableLambda(respond)


@pytest.fixture
def stub_provider(monkeypatch):
    def install(provider: StubProvider, rag=("", [])):
        monkeypatch.setattr(LLMProviderFactory, "get_provider", classmethod(lambda cls, name=None: provider))
        monkeypatch.setattr(review_generator, "retrieve_rag_context", lambda features: rag)
        return provider

    return install


# --- Провайдеры как фабрики LangChain-моделей -------------------------------


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

    assert type(get_chat_model()).__name__ == expected_class


def test_nemotron_uses_nvidia_base_url():
    set_runtime_llm_setting("LLM_PROVIDER", "nemotron")
    set_runtime_llm_setting("NEMOTRON_API_KEY", "test-key")

    assert "nvidia.com" in str(get_chat_model().openai_api_base)


def test_get_chat_model_raises_without_api_key():
    set_runtime_llm_setting("LLM_PROVIDER", "openai")
    set_runtime_llm_setting("OPENAI_API_KEY", "")

    with pytest.raises(ValueError):
        get_chat_model()


def test_claude_default_model_is_current_generation(monkeypatch):
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)

    assert DEFAULT_CLAUDE_MODEL == "claude-sonnet-5"
    assert ClaudeProvider().model == DEFAULT_CLAUDE_MODEL


def test_claude_model_does_not_send_sampling_params():
    """Актуальные модели Claude отклоняют temperature ошибкой 400."""
    set_runtime_llm_setting("ANTHROPIC_API_KEY", "test-key")

    model = ClaudeProvider().build_chat_model()

    assert model.temperature is None and model.top_p is None and model.top_k is None


def test_claude_uses_native_json_schema_output():
    assert ClaudeProvider.structured_output_kwargs == {"method": "json_schema"}


# --- Промпт ------------------------------------------------------------------


def test_compact_features_drop_mfcc():
    compact = review_generator._compact_features(FEATURES)

    assert "mfcc_coefficients" not in compact["spectral"]
    assert compact["rhythm"]["bpm"] == 128


def test_review_prompt_contains_features_and_rag_context():
    rendered = review_generator._REVIEW_PROMPT.invoke(
        {"features": '{"bpm": 128}', "rag_section": review_generator._rag_section("Контекст {из} книги")}
    ).to_string()

    assert "Essentia" in rendered
    assert '{"bpm": 128}' in rendered
    assert "Контекст {из} книги" in rendered  # скобки из данных не ломают шаблон
    assert "не цитируй учебник" in rendered.lower()


def test_review_prompt_without_rag_has_no_textbook_instruction():
    rendered = review_generator._REVIEW_PROMPT.invoke(
        {"features": "{}", "rag_section": review_generator._rag_section("")}
    ).to_string()

    assert "учебник" not in rendered.lower()


# --- generate_review ---------------------------------------------------------


def test_generate_review_builds_result_from_structured_response(stub_provider):
    provider = stub_provider(StubProvider(TrackReview(score=7.46, sections=SECTIONS)))

    review = generate_review(FEATURES)

    assert review["source"] == "stub"
    assert review["model"] == "stub-model"
    assert review["language"] == "ru"
    assert review["score"] == 7.5
    assert review["sections"] == SECTIONS.model_dump()
    # full_text собирается из разделов в порядке полей схемы
    assert review["full_text"] == "Резюме\n\nРитм\n\nТональность\n\nПродакшн\n\nВывод"
    assert '"bpm": 128' in provider.prompts[0]
    assert "mfcc_coefficients" not in provider.prompts[0]


@pytest.mark.parametrize("raw, expected", [(11.2, 10.0), (0.0, 1.0), (-3, 1.0)])
def test_generate_review_clamps_score(stub_provider, raw, expected):
    stub_provider(StubProvider(TrackReview(score=raw, sections=SECTIONS)))

    assert generate_review(FEATURES)["score"] == expected


def test_generate_review_reports_rag_usage(stub_provider):
    passages = [{"source": "book.pdf"}, {"source": "book.pdf"}, {"source": "other.pdf"}]
    stub_provider(StubProvider(TrackReview(score=8, sections=SECTIONS)), rag=("контекст", passages))

    review = generate_review(FEATURES)

    assert review["rag"]["passages_used"] == 3
    assert sorted(review["rag"]["sources"]) == ["book.pdf", "other.pdf"]


def test_generate_review_falls_back_to_template_when_provider_unavailable(monkeypatch):
    def unavailable(cls, name=None):
        raise ValueError("Провайдер openai недоступен")

    monkeypatch.setattr(LLMProviderFactory, "get_provider", classmethod(unavailable))

    review = generate_review(FEATURES)

    assert review["source"] == "template"
    assert "llm_error" not in review


def test_generate_review_falls_back_to_template_on_llm_error(stub_provider):
    stub_provider(StubProvider(error=RuntimeError("сеть недоступна")))

    review = generate_review(FEATURES)

    assert review["source"] == "template"
    assert review["llm_error"] == "сеть недоступна"


def test_invalid_model_answer_is_reported_as_llm_error(stub_provider):
    """ValidationError — подкласс ValueError, но это сбой генерации, а не «нет провайдера»."""
    try:
        TrackReview.model_validate({"score": "не число", "sections": {}})
    except ValidationError as exc:
        error = exc
    stub_provider(StubProvider(error=error))

    review = generate_review(FEATURES)

    assert review["source"] == "template"
    assert "llm_error" in review
