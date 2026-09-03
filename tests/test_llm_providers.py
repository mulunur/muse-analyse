#!/usr/bin/env python3
"""
Тесты для проверки интеграции LLM провайдеров.
Запуск: python -m pytest tests/test_llm_providers.py -v
"""

import os
import sys
from pathlib import Path

# Добавляем parent directory в path для импорта app
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestLLMProviders:
    """Тесты для LLM провайдеров."""

    def test_config_loaded(self):
        """Проверка загрузки конфигурации."""
        from app.config import LLM_PROVIDER, SUPPORTED_PROVIDERS
        
        assert LLM_PROVIDER in SUPPORTED_PROVIDERS
        assert len(SUPPORTED_PROVIDERS) == 4

    def test_provider_factory_initialization(self):
        """Проверка инициализации фабрики провайдеров."""
        from app.llm_providers import LLMProviderFactory
        
        providers = LLMProviderFactory.list_available_providers()
        assert isinstance(providers, dict)
        assert all(isinstance(v, bool) for v in providers.values())

    def test_openai_provider_available(self):
        """Проверка доступности OpenAI (если ключ установлен)."""
        from app.config import OPENAI_API_KEY
        from app.llm_providers import OpenAIProvider
        
        provider = OpenAIProvider()
        
        if OPENAI_API_KEY:
            assert provider.is_available()
        else:
            assert not provider.is_available()

    def test_claude_provider_available(self):
        """Проверка доступности Claude (если ключ установлен)."""
        from app.config import ANTHROPIC_API_KEY
        from app.llm_providers import ClaudeProvider
        
        provider = ClaudeProvider()
        
        if ANTHROPIC_API_KEY:
            assert provider.is_available()
        else:
            assert not provider.is_available()

    def test_ollama_provider_detection(self):
        """Проверка детекции Ollama."""
        from app.llm_providers import OllamaProvider
        
        provider = OllamaProvider()
        # Не будем падать если Ollama не запущена
        result = provider.is_available()
        assert isinstance(result, bool)

    def test_nemotron_provider_available(self):
        """Проверка доступности Nemotron (если ключ установлен)."""
        from app.config import NEMOTRON_API_KEY
        from app.llm_providers import NemotronProvider
        
        provider = NemotronProvider()
        
        if NEMOTRON_API_KEY:
            assert provider.is_available()
        else:
            assert not provider.is_available()

    def test_provider_factory_get_provider_unknown(self):
        """Проверка ошибки для неизвестного провайдера."""
        from app.llm_providers import LLMProviderFactory
        
        with pytest.raises(ValueError) as exc_info:
            LLMProviderFactory.get_provider("unknown_provider")
        
        assert "Неизвестный провайдер" in str(exc_info.value)

    def test_provider_prompt_building(self):
        """Проверка построения промпта."""
        from app.llm_providers import LLMProvider
        
        features = {
            "duration_sec": 180.5,
            "rhythm": {"bpm": 128},
            "tonal": {"key": "C", "scale": "major"},
            "dynamics": {"loudness_ebu128_lufs": -9.5},
            "spectral": {
                "spectral_centroid_hz": 2340,
                "mfcc_coefficients": [1, 2, 3]  # Should be excluded
            },
            "energy": 0.64
        }
        
        prompt = LLMProvider._build_prompt(features)
        
        # Проверяем структуру промпта
        assert "Essentia" in prompt
        assert "128" in prompt  # BPM
        assert "мажор" not in prompt  # Промпт на русском, но мажор тут не должен быть
        assert "mfcc_coefficients" not in prompt  # MFCC должна быть исключена

    def test_template_review_generation(self):
        """Проверка генерации шаблонного обзора."""
        from app.review_generator import _build_template_review
        
        features = {
            "duration_sec": 180.5,
            "rhythm": {"bpm": 128, "beats_count": 245, "beat_confidence": 0.95, "onset_rate": 0.123},
            "tonal": {
                "key": "C",
                "scale": "minor",
                "key_strength": 0.88,
                "danceability": 0.72,
                "tuning_frequency_hz": 440
            },
            "dynamics": {
                "loudness_ebu128_lufs": -9.5,
                "rms": 0.156,
                "dynamic_complexity": 0.38
            },
            "spectral": {
                "spectral_brightness": 0.45,
                "spectral_centroid_hz": 2340,
                "spectral_flux": 0.045
            },
            "energy": 0.64
        }
        
        review = _build_template_review(features)
        
        assert review["source"] == "template"
        assert review["language"] == "ru"
        assert 1 <= review["score"] <= 10
        assert "sections" in review
        assert "full_text" in review
        assert all(k in review["sections"] for k in ["summary", "rhythm", "tonality", "production", "verdict"])

    def test_review_generator_fallback(self):
        """Проверка fallback на шаблон если нет провайдеров."""
        from app.review_generator import generate_review
        
        features = {
            "duration_sec": 180.5,
            "rhythm": {"bpm": 128, "beats_count": 245, "beat_confidence": 0.95, "onset_rate": 0.123},
            "tonal": {
                "key": "C",
                "scale": "minor",
                "key_strength": 0.88,
                "danceability": 0.72,
                "tuning_frequency_hz": 440
            },
            "dynamics": {
                "loudness_ebu128_lufs": -9.5,
                "rms": 0.156,
                "dynamic_complexity": 0.38
            },
            "spectral": {
                "spectral_brightness": 0.45,
                "spectral_centroid_hz": 2340,
                "spectral_flux": 0.045
            },
            "energy": 0.64
        }
        
        review = generate_review(features)
        
        # Должен вернуть либо обзор от провайдера, либо шаблонный
        assert "source" in review
        assert "score" in review
        assert "full_text" in review


class TestAPIEndpoints:
    """Тесты для API эндпоинтов."""

    @pytest.fixture
    def client(self):
        """Фикстура для FastAPI тестового клиента."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Проверка эндпоинта /api/health."""
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "llm_providers" in data

    def test_providers_endpoint(self, client):
        """Проверка эндпоинта /api/providers."""
        response = client.get("/api/providers")
        
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "description" in data
        assert all(k in data["available"] for k in ["openai", "claude", "ollama", "nemotron"])

    def test_analyze_without_file(self, client):
        """Проверка ошибки при анализе без файла."""
        response = client.post("/api/analyze")
        
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
