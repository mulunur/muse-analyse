"""LLM провайдеры: настройки и построение LangChain chat-моделей."""

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
    """Провайдер знает свои настройки и умеет строить LangChain chat-модель.

    Сам вызов модели, разбор ответа и валидацию схемы выполняет LangChain,
    поэтому провайдеру не нужен собственный код общения с API.
    """

    name: ClassVar[str]
    model: str
    # Доп. аргументы для chat.with_structured_output(): у провайдеров разные
    # способы получить структурированный ответ.
    structured_output_kwargs: ClassVar[dict[str, Any]] = {}

    @abstractmethod
    def is_available(self) -> bool:
        """Есть ли ключ / доступен ли сервис."""

    @abstractmethod
    def build_chat_model(self) -> BaseChatModel:
        """Создаёт LangChain chat-модель с настройками провайдера."""

    def structured_model(self, schema: type[BaseModel]) -> Runnable:
        """Chat-модель, которая возвращает объект ``schema`` вместо текста."""
        return self.build_chat_model().with_structured_output(
            schema, **self.structured_output_kwargs
        )


class OpenAIProvider(LLMProvider):
    """OpenAI GPT провайдер."""

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
    """Anthropic Claude провайдер."""

    name = "claude"
    # Родной структурированный вывод Anthropic вместо принудительного вызова
    # инструмента (function_calling), который конфликтует с мышлением модели.
    structured_output_kwargs = {"method": "json_schema"}

    def __init__(self):
        self.api_key = get_runtime_llm_setting("ANTHROPIC_API_KEY", "")
        self.model = get_runtime_llm_setting("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def build_chat_model(self) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic

        # temperature намеренно не передаём: актуальные модели Claude (Sonnet 5,
        # Opus 5) отклоняют sampling-параметры ошибкой 400.
        return ChatAnthropic(
            model=self.model,
            api_key=self.api_key,
            max_tokens=LLM_MAX_TOKENS,
        )


class OllamaProvider(LLMProvider):
    """Ollama локальный провайдер (поддержка Mistral, LLaMA и др.)."""

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
    """NVIDIA Nemotron API провайдер."""

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
        # NVIDIA API совместим с форматом OpenAI, отличается только base_url.
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )


class LLMProviderFactory:
    """Фабрика для создания провайдеров LLM."""

    _providers: dict[str, type[LLMProvider]] = {
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
        "ollama": OllamaProvider,
        "nemotron": NemotronProvider,
    }

    @classmethod
    def get_provider(cls, provider_name: str | None = None) -> LLMProvider:
        """
        Возвращает инстанс провайдера.

        Args:
            provider_name: Имя провайдера (openai, claude, ollama, nemotron).
                         Если не указан, используется LLM_PROVIDER из config.

        Returns:
            Инстанс LLMProvider

        Raises:
            ValueError: Если провайдер не найден или недоступен
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
        """Возвращает список доступных провайдеров и их статус."""
        result = {}
        for name, provider_class in cls._providers.items():
            provider = provider_class()
            result[name] = provider.is_available()
        return result


def get_chat_model() -> BaseChatModel:
    """Chat-модель для провайдера из текущих runtime-настроек."""
    return LLMProviderFactory.get_provider().build_chat_model()


def get_structured_model(schema: type[BaseModel]) -> Runnable:
    """Модель провайдера из настроек, возвращающая объект ``schema``."""
    return LLMProviderFactory.get_provider().structured_model(schema)
