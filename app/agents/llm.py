"""Небольшой адаптер нового пайплайна к существующим LLM-провайдерам."""

from __future__ import annotations

import json
from typing import Any

from app.llm_providers import LLMProviderFactory


def ask_llm(prompt: str, *, features: dict[str, Any] | None = None) -> str:
    """Возвращает текст ответа существующего провайдера или пустую строку."""
    try:
        provider = LLMProviderFactory.get_provider()
        result = provider.generate_review(features or {}, rag_context=prompt)
        return str(result.get("full_text", ""))
    except Exception:
        return ""


def parse_json_response(text: str, default: Any) -> Any:
    """Извлекает JSON даже если провайдер добавил markdown-ограждение."""
    if not text:
        return default
    candidate = text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = min((i for i in (candidate.find("{"), candidate.find("[")) if i >= 0), default=-1)
        end = max(candidate.rfind("}"), candidate.rfind("]"))
        if start >= 0 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                pass
    return default