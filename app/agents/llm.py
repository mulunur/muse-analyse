"""LLM calls for the Growth Copilot agents: LangChain chains that log their own errors."""

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
    """Calls the LLM and returns the answer parsed into a ``schema`` object.

    If anything goes wrong (no API key, network error, an answer that does not
    match the schema) it logs a warning and returns None, so the agent can
    decide what to fall back to.
    """
    try:
        chain = prompt | get_structured_model(schema)
        return chain.invoke(variables)
    except Exception:
        logger.warning("Структурированный вызов LLM не удался (%s)", schema.__name__, exc_info=True)
        return None


def invoke_text(prompt: ChatPromptTemplate, variables: dict[str, Any]) -> str:
    """Calls the LLM and returns plain text, or an empty string if the call fails."""
    try:
        chain = prompt | get_chat_model() | StrOutputParser()
        return chain.invoke(variables)
    except Exception:
        logger.warning("Текстовый вызов LLM не удался", exc_info=True)
        return ""
