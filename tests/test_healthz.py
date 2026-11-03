"""Тесты /healthz — лёгкой проверки для проб Kubernetes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_module


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_does_not_touch_external_dependencies(client, monkeypatch):
    """Сбой Ollama/RAG не должен делать веб-процесс "нездоровым" для Kubernetes.

    Если бы /healthz использовал провайдеры или RAG, любой из этих вызовов
    упал бы — а проба перезапускала бы под из-за чужой поломки.
    """

    def boom(*args, **kwargs):
        raise RuntimeError("внешняя зависимость недоступна")

    monkeypatch.setattr(main_module.LLMProviderFactory, "list_available_providers", boom)
    monkeypatch.setattr(main_module, "get_knowledge_base", boom)

    response = client.get("/healthz")

    assert response.status_code == 200
