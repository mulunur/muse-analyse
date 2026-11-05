"""LLM providers: their settings, and how they build LangChain chat models."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from app.config import (
    DEFAULT_CLAUDE_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    get_runtime_llm_setting,
)

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """A provider knows its own settings and can build a LangChain chat model.

    LangChain does the actual model call, parsing the answer and validating the
    schema, so a provider needs no API-talking code of its own.
    """

    name: ClassVar[str]
    model: str
    # Extra arguments for chat.with_structured_output(): providers have different
    # ways of producing structured output.
    structured_output_kwargs: ClassVar[dict[str, Any]] = {}

    @abstractmethod
    def is_available(self) -> bool:
        """Is there an API key / is the service reachable?"""

    @abstractmethod
    def build_chat_model(self) -> BaseChatModel:
        """Builds a LangChain chat model using the provider's settings."""

    def structured_model(self, schema: type[BaseModel]) -> Runnable:
        """A chat model that returns a ``schema`` object instead of plain text."""
        return self.build_chat_model().with_structured_output(
            schema, **self.structured_output_kwargs
        )


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    name = "openai"

    def __init__(self):
        self.api_key = get_runtime_llm_setting("OPENAI_API_KEY", "")
        self.model = get_runtime_llm_setting("OPENAI_MODEL", "gpt-4o-mini")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def build_chat_model(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider."""

    name = "claude"
    # Use Anthropic's native structured output instead of forced tool calling
    # (function_calling), which clashes with the model's thinking.
    structured_output_kwargs = {"method": "json_schema"}

    def __init__(self):
        self.api_key = get_runtime_llm_setting("ANTHROPIC_API_KEY", "")
        self.model = get_runtime_llm_setting("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def build_chat_model(self) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic

        # We deliberately do not pass temperature: the current Claude models
        # (Sonnet 5, Opus 5) reject sampling parameters with a 400 error.
        return ChatAnthropic(
            model=self.model,
            api_key=self.api_key,
            max_tokens=LLM_MAX_TOKENS,
        )


class OllamaProvider(LLMProvider):
    """Local Ollama provider (works with Mistral, LLaMA and others)."""

    name = "ollama"

    def __init__(self):
        self.base_url = get_runtime_llm_setting("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = get_runtime_llm_setting("OLLAMA_MODEL", "mistral")

    def is_available(self) -> bool:
        try:
            import requests

            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def build_chat_model(self) -> BaseChatModel:
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=LLM_TEMPERATURE,
            num_predict=LLM_MAX_TOKENS,
        )


class NemotronProvider(LLMProvider):
    """NVIDIA Nemotron API provider."""

    name = "nemotron"

    def __init__(self):
        self.api_key = get_runtime_llm_setting("NEMOTRON_API_KEY", "")
        self.model = get_runtime_llm_setting("NEMOTRON_MODEL", "meta/llama-2-70b-chat")
        self.base_url = get_runtime_llm_setting(
            "NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )

    def is_available(self) -> bool:
        return bool(self.api_key)

    def build_chat_model(self) -> BaseChatModel:
        # NVIDIA's API is OpenAI-compatible; only the base_url differs.
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )


class LLMProviderFactory:
    """Factory that creates LLM providers."""

    _providers: dict[str, type[LLMProvider]] = {
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
        "ollama": OllamaProvider,
        "nemotron": NemotronProvider,
    }

    @classmethod
    def get_provider(cls, provider_name: str | None = None) -> LLMProvider:
        """
        Returns a provider instance.

        Args:
            provider_name: Provider name (openai, claude, ollama, nemotron).
                         If omitted, LLM_PROVIDER from the config is used.

        Returns:
            An LLMProvider instance

        Raises:
            ValueError: If the provider is unknown or not available
        """
        name = (provider_name or get_runtime_llm_setting("LLM_PROVIDER", "openai")).lower()

        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Неизвестный провайдер: {name}. Доступны: {available}")

        provider = cls._providers[name]()

        if not provider.is_available():
            raise ValueError(
                f"Провайдер {name} недоступен. "
                "Проверьте ключи API и конфигурацию."
            )

        return provider

    @classmethod
    def list_available_providers(cls) -> dict[str, bool]:
        """Returns the available providers and whether each one is ready."""
        result = {}
        for name, provider_class in cls._providers.items():
            provider = provider_class()
            result[name] = provider.is_available()
        return result


def get_chat_model() -> BaseChatModel:
    """A chat model for the provider chosen in the current runtime settings."""
    return LLMProviderFactory.get_provider().build_chat_model()


def get_structured_model(schema: type[BaseModel]) -> Runnable:
    """The chosen provider's model, returning a ``schema`` object."""
    return LLMProviderFactory.get_provider().structured_model(schema)
