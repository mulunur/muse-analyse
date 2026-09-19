"""Адаптер агентов Growth Copilot к LangChain chat-моделям."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app.config import LLM_MAX_TOKENS, LLM_TEMPERATURE
from app.llm_providers import (
    ClaudeProvider,
    LLMProvider,
    LLMProviderFactory,
    NemotronProvider,
    OllamaProvider,
    OpenAIProvider,
)

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _build_chat_model(provider: LLMProvider) -> BaseChatModel:
    """Превращает настроенный провайдер в LangChain chat-модель."""
    if isinstance(provider, OpenAIProvider):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=provider.model,
            api_key=provider.api_key,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
    if isinstance(provider, ClaudeProvider):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=provider.model,
            api_key=provider.api_key,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
    if isinstance(provider, OllamaProvider):
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=provider.model,
            base_url=provider.base_url,
            temperature=LLM_TEMPERATURE,
            num_predict=LLM_MAX_TOKENS,
        )
    if isinstance(provider, NemotronProvider):
        # NVIDIA API совместим с форматом OpenAI, отличается только base_url.
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=provider.model,
            api_key=provider.api_key,
            base_url=provider.base_url,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
    raise ValueError(f"Неподдерживаемый провайдер: {type(provider).__name__}")


def get_chat_model() -> BaseChatModel:
    """Возвращает chat-модель для провайдера из текущих runtime-настроек."""
    return _build_chat_model(LLMProviderFactory.get_provider())


def invoke_structured(
    prompt: ChatPromptTemplate,
    schema: type[SchemaT],
    variables: dict[str, Any],
) -> SchemaT | None:
    """Вызывает LLM и возвращает ответ, разобранный в объект ``schema``.

    При любой ошибке (нет ключа, сеть, невалидный ответ) пишет предупреждение
    в лог и возвращает None — агент сам решает, какое значение подставить.
    """
    try:
        chain = prompt | get_chat_model().with_structured_output(schema)
        return chain.invoke(variables)
    except Exception:
        logger.warning("Структурированный вызов LLM не удался (%s)", schema.__name__, exc_info=True)
        return None


def invoke_text(prompt: ChatPromptTemplate, variables: dict[str, Any]) -> str:
    """Вызывает LLM и возвращает обычный текст или пустую строку при ошибке."""
    try:
        chain = prompt | get_chat_model() | StrOutputParser()
        return chain.invoke(variables)
    except Exception:
        logger.warning("Текстовый вызов LLM не удался", exc_info=True)
        return ""
