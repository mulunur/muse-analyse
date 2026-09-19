"""LLM провайдеры для генерации музыкальных обзоров."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.config import (
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    get_runtime_llm_setting,
)

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Абстрактный интерфейс для LLM провайдеров."""

    @abstractmethod
    def generate_review(
        self,
        features: dict[str, Any],
        *,
        rag_context: str = "",
    ) -> dict[str, Any]:
        """
        Генерирует музыкальный обзор на основе признаков.

        Args:
            features: Словарь со всеми параметрами аудиоанализа
            rag_context: Справочный контекст из RAG (учебник)

        Returns:
            Словарь с полями: source, language, score, sections, full_text, model
        """
        pass

    @staticmethod
    def _build_prompt(
        features: dict[str, Any],
        *,
        rag_context: str = "",
    ) -> str:
        """Строит промпт для генерации обзора."""
        compact = {
            "duration_sec": features.get("duration_sec"),
            "rhythm": features.get("rhythm"),
            "tonal": features.get("tonal"),
            "dynamics": features.get("dynamics"),
            "spectral": {
                k: v
                for k, v in features.get("spectral", {}).items()
                if k != "mfcc_coefficients"
            },
            "energy": features.get("energy"),
        }

        rag_section = ""
        if rag_context:
            rag_section = (
                f"\n\n{rag_context}\n\n"
                "При анализе опирайся на параметры Essentia и, где уместно, "
                "обосновывай оценки терминами и концепциями из учебника "
                "(композиция, гармония, ритм, форма, фактура). "
                "Не цитируй учебник дословно — интерпретируй применительно к треку."
            )

        return (
            "Ты — профессиональный музыкальный критик. На основе объективных параметров "
            "аудиоанализа (библиотека Essentia) напиши структурированный обзор трека на русском языке.\n\n"
            "Параметры анализа (JSON):\n"
            f"{json.dumps(compact, ensure_ascii=False, indent=2)}"
            f"{rag_section}\n\n"
            "Формат ответа — JSON с полями:\n"
            '- "score": число 1–10\n'
            '- "sections": объект с ключами summary, rhythm, tonality, production, verdict\n'
            '- "full_text": полный связный текст обзора\n\n'
            "Пиши профессионально, но доступно. Не выдумывай жанр или исполнителя — "
            "опирайся только на параметры."
        )


class OpenAIProvider(LLMProvider):
    """OpenAI GPT провайдер."""

    def __init__(self):
        self.api_key = get_runtime_llm_setting("OPENAI_API_KEY", "")
        self.model = get_runtime_llm_setting("OPENAI_MODEL", "gpt-4o-mini")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_review(
        self,
        features: dict[str, Any],
        *,
        rag_context: str = "",
    ) -> dict[str, Any]:
        """Генерирует обзор через OpenAI API."""
        if not self.is_available():
            raise ValueError("OPENAI_API_KEY не установлен")

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты музыкальный критик. Отвечай только валидным JSON "
                            "на русском языке."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(features, rag_context=rag_context),
                    },
                ],
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Пустой ответ от OpenAI")

            parsed = json.loads(content)
            parsed["source"] = "openai"
            parsed["language"] = "ru"
            parsed["model"] = self.model

            if "full_text" not in parsed and "sections" in parsed:
                parsed["full_text"] = "\n\n".join(
                    str(v) for v in parsed["sections"].values()
                )

            return parsed

        except Exception as exc:
            logger.error("OpenAI ошибка: %s", exc)
            raise


class ClaudeProvider(LLMProvider):
    """Anthropic Claude провайдер."""

    def __init__(self):
        self.api_key = get_runtime_llm_setting("ANTHROPIC_API_KEY", "")
        self.model = get_runtime_llm_setting("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_review(
        self,
        features: dict[str, Any],
        *,
        rag_context: str = "",
    ) -> dict[str, Any]:
        """Генерирует обзор через Anthropic Claude API."""
        if not self.is_available():
            raise ValueError("ANTHROPIC_API_KEY не установлен")

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=LLM_MAX_TOKENS,
                system=(
                    "Ты музыкальный критик. Отвечай только валидным JSON "
                    "на русском языке."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": self._build_prompt(features, rag_context=rag_context),
                    },
                ],
            )

            content = message.content[0].text
            if not content:
                raise ValueError("Пустой ответ от Claude")

            parsed = json.loads(content)
            parsed["source"] = "claude"
            parsed["language"] = "ru"
            parsed["model"] = self.model

            if "full_text" not in parsed and "sections" in parsed:
                parsed["full_text"] = "\n\n".join(
                    str(v) for v in parsed["sections"].values()
                )

            return parsed

        except Exception as exc:
            logger.error("Claude ошибка: %s", exc)
            raise


class OllamaProvider(LLMProvider):
    """Ollama локальный провайдер (поддержка Mistral, LLaMA и др.)."""

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

    def generate_review(
        self,
        features: dict[str, Any],
        *,
        rag_context: str = "",
    ) -> dict[str, Any]:
        """Генерирует обзор через локальный Ollama."""
        if not self.is_available():
            raise ValueError(
                f"Ollama недоступна на {self.base_url}. "
                "Убедитесь, что Ollama запущена локально."
            )

        try:
            import requests

            prompt = self._build_prompt(features, rag_context=rag_context)
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            }

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()

            result = response.json()
            content = result.get("response", "")

            if not content:
                raise ValueError("Пустой ответ от Ollama")

            # Пытаемся распарсить JSON из ответа
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                # Если не JSON, оборачиваем в базовую структуру
                logger.warning("Ollama вернула не-JSON ответ, оборачиваем в структуру")
                parsed = {
                    "score": 7,
                    "sections": {
                        "summary": "Анализ трека на основе параметров.",
                        "rhythm": content[:500],
                        "tonality": "Информация о тональности.",
                        "production": "Информация о продакшене.",
                        "verdict": "Обзор завершён.",
                    },
                }

            parsed["source"] = "ollama"
            parsed["language"] = "ru"
            parsed["model"] = self.model

            if "full_text" not in parsed and "sections" in parsed:
                parsed["full_text"] = "\n\n".join(
                    str(v) for v in parsed["sections"].values()
                )

            return parsed

        except Exception as exc:
            logger.error("Ollama ошибка: %s", exc)
            raise


class NemotronProvider(LLMProvider):
    """NVIDIA Nemotron API провайдер."""

    def __init__(self):
        self.api_key = get_runtime_llm_setting("NEMOTRON_API_KEY", "")
        self.model = get_runtime_llm_setting("NEMOTRON_MODEL", "meta/llama-2-70b-chat")
        self.base_url = get_runtime_llm_setting("NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_review(
        self,
        features: dict[str, Any],
        *,
        rag_context: str = "",
    ) -> dict[str, Any]:
        """Генерирует обзор через NVIDIA Nemotron API."""
        if not self.is_available():
            raise ValueError("NEMOTRON_API_KEY не установлен")

        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Ты музыкальный критик. Отвечай только валидным JSON "
                            "на русском языке."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(features, rag_context=rag_context),
                    },
                ],
                "temperature": LLM_TEMPERATURE,
                "max_tokens": LLM_MAX_TOKENS,
                "top_p": 1,
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            if not content:
                raise ValueError("Пустой ответ от Nemotron")

            parsed = json.loads(content)
            parsed["source"] = "nemotron"
            parsed["language"] = "ru"
            parsed["model"] = self.model

            if "full_text" not in parsed and "sections" in parsed:
                parsed["full_text"] = "\n\n".join(
                    str(v) for v in parsed["sections"].values()
                )

            return parsed

        except Exception as exc:
            logger.error("Nemotron ошибка: %s", exc)
            raise


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
        from app.config import get_runtime_llm_setting

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
