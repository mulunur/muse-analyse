"""Небольшой адаптер нового пайплайна к существующим LLM-провайдерам."""

from __future__ import annotations

import json
from typing import Any

from app.llm_providers import LLMProviderFactory

GROWTH_COPILOT_SYSTEM_PROMPT = (
    "Ты — ассистент по продвижению независимых музыкальных артистов. "
    "Следуй инструкциям в промпте пользователя, включая требуемый формат ответа. "
    "Если тебя просят ответить JSON — верни только валидный JSON без markdown-ограждений "
    "и без лишнего текста до или после него."
)


def ask_llm(prompt: str) -> str:
    """Возвращает сырой текст ответа LLM-провайдера или пустую строку."""
    try:
        provider = LLMProviderFactory.get_provider()
        return provider.complete(prompt, system_prompt=GROWTH_COPILOT_SYSTEM_PROMPT)
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