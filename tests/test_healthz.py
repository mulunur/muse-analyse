"""Tests for /healthz, the lightweight check used by Kubernetes probes."""

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
    """A failing Ollama/RAG must not make the web process look "unhealthy" to Kubernetes.

    If /healthz used the providers or RAG, either call would blow up here,
    and the probe would restart the pod because of someone else's breakage.
    """

    def boom(*args, **kwargs):
        raise RuntimeError("внешняя зависимость недоступна")

    monkeypatch.setattr(main_module.LLMProviderFactory, "list_available_providers", boom)
    monkeypatch.setattr(main_module, "get_knowledge_base", boom)

    response = client.get("/healthz")

    assert response.status_code == 200
