"""Вызовы LLM для агентов Growth Copilot: LangChain-цепочки с логированием ошибок."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app.llm_providers import get_chat_model, get_structured_model

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


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
        chain = prompt | get_structured_model(schema)
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
