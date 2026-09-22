"""Тесты задач Celery.

Основная часть вызывает функции задач напрямую (без брокера — Celery-задача
остаётся обычной вызываемой функцией) и подменяет тяжёлые зависимости через
monkeypatch. Один тест внизу — настоящая сквозная проверка через реальный
Celery в eager-режиме и реальный Redis; он пропускается, если Redis недоступен,
как уже принято в этом проекте для Essentia/Ollama.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.agents.state import ContentIdea
from app.audio_analysis import AudioAnalysisError
from app.config import CELERY_BROKER_URL
from app.tasks import analyze_track_task, growth_select_task, growth_start_task


def _redis_reachable(url: str) -> bool:
    parsed = urlparse(url)
    try:
        with socket.create_connection((parsed.hostname, parsed.port or 6379), timeout=0.5):
            return True
    except OSError:
        return False


REDIS_AVAILABLE = _redis_reachable(CELERY_BROKER_URL)


class FakeSnapshot:
    def __init__(self, values: dict):
        self.values = values


class FakeGraph:
    """Подмена growth_graph: запоминает вызовы invoke(), не трогает LLM/checkpointer."""

    def __init__(self, state_after_invoke: dict, invoke_error: Exception | None = None):
        self._state = state_after_invoke
        self._invoke_error = invoke_error
        self.invoke_calls: list[tuple] = []

    def invoke(self, *args, **kwargs):
        self.invoke_calls.append((args, kwargs))
        if self._invoke_error:
            raise self._invoke_error
        return self._state

    def get_state(self, config):
        return FakeSnapshot(self._state)


class TestAnalyzeTrackTask:
    def test_success_returns_review_and_deletes_file(self, monkeypatch, tmp_path):
        path = tmp_path / "track.mp3"
        path.write_bytes(b"fake-audio")
        features = {"duration_sec": 120}
        review = {"source": "template", "score": 7.0}
        monkeypatch.setattr("app.audio_analysis.analyze_audio", lambda p: features)
        monkeypatch.setattr("app.review_generator.generate_review", lambda f: review)

        result = analyze_track_task(str(path), "track.mp3")

        assert result == {
            "success": True,
            "filename": "track.mp3",
            "features": features,
            "review": review,
        }
        assert not path.exists()

    def test_audio_analysis_error_is_reported_without_retry(self, monkeypatch, tmp_path):
        path = tmp_path / "broken.mp3"
        path.write_bytes(b"not audio")
        monkeypatch.setattr(
            "app.audio_analysis.analyze_audio",
            lambda p: (_ for _ in ()).throw(AudioAnalysisError("Файл повреждён")),
        )

        result = analyze_track_task(str(path), "broken.mp3")

        assert result == {"success": False, "error": "Файл повреждён"}
        assert not path.exists()

    def test_unexpected_error_is_caught_and_file_still_deleted(self, monkeypatch, tmp_path):
        path = tmp_path / "track.mp3"
        path.write_bytes(b"fake-audio")
        monkeypatch.setattr(
            "app.audio_analysis.analyze_audio",
            lambda p: (_ for _ in ()).throw(RuntimeError("essentia упала")),
        )

        result = analyze_track_task(str(path), "track.mp3")

        assert result["success"] is False
        assert "essentia упала" in result["error"]
        assert not path.exists()


class TestGrowthStartTask:
    def test_success_returns_json_safe_content_ideas(self, monkeypatch, tmp_path):
        audio_path = tmp_path / "a.mp3"
        audio_path.write_bytes(b"x")
        idea = ContentIdea(
            id="idea-1",
            format="instagram_caption",
            hook="Хук",
            rationale="Обоснование",
            voice_alignment="Совпадает",
        )
        # snapshot.values отдаёт content_ideas как объекты Pydantic, а не dict —
        # именно это ломает json.dumps без явного model_dump.
        fake_graph = FakeGraph({"content_ideas": [idea]})
        monkeypatch.setattr("app.agents.graph.growth_graph", fake_graph)

        result = growth_start_task(str(audio_path), ["материал"], "thread-1")

        assert result["success"] is True
        assert result["thread_id"] == "thread-1"
        assert result["content_ideas"] == [idea.model_dump(mode="json")]
        assert isinstance(result["content_ideas"][0], dict)
        # Файл нужен следующему шагу (select) — здесь при успехе не удаляется.
        assert audio_path.exists()

    def test_failure_deletes_uploaded_file(self, monkeypatch, tmp_path):
        audio_path = tmp_path / "a.mp3"
        audio_path.write_bytes(b"x")
        fake_graph = FakeGraph({}, invoke_error=RuntimeError("LLM недоступен"))
        monkeypatch.setattr("app.agents.graph.growth_graph", fake_graph)

        result = growth_start_task(str(audio_path), [], "thread-1")

        assert result == {"success": False, "error": "LLM недоступен"}
        assert not audio_path.exists()


class TestGrowthSelectTask:
    def test_success_returns_drafts_and_cleans_up_audio(self, monkeypatch, tmp_path):
        audio_path = tmp_path / "a.mp3"
        audio_path.write_bytes(b"x")
        fake_graph = FakeGraph({"drafts": {"idea-1": "готовый текст"}, "audio_path": str(audio_path)})
        monkeypatch.setattr("app.agents.graph.growth_graph", fake_graph)

        result = growth_select_task("thread-1", ["idea-1"])

        assert result == {"success": True, "drafts": {"idea-1": "готовый текст"}}
        assert not audio_path.exists()

    def test_failure_still_cleans_up_audio(self, monkeypatch, tmp_path):
        audio_path = tmp_path / "a.mp3"
        audio_path.write_bytes(b"x")
        # get_state читает то, что уже успело закрепиться в чекпойнте (включая
        # исходный audio_path), даже если сам invoke() упал.
        fake_graph = FakeGraph({"audio_path": str(audio_path)}, invoke_error=ValueError("критик упал"))
        monkeypatch.setattr("app.agents.graph.growth_graph", fake_graph)

        result = growth_select_task("thread-1", ["idea-1"])

        assert result == {"success": False, "error": "критик упал"}
        assert not audio_path.exists()


_ROUNDTRIP_SCRIPT = """
import json
from unittest.mock import patch

from app.tasks import analyze_track_task, celery_app

with patch("app.audio_analysis.analyze_audio", lambda p: {"duration_sec": 10}), \\
     patch("app.review_generator.generate_review", lambda f: {"source": "template", "score": 5}):
    async_result = analyze_track_task.delay("/tmp/does-not-matter.mp3", "track.mp3")

# Отдельный, "свежий" AsyncResult по id — именно так его достаёт
# GET /api/tasks/{task_id}, отдельным запросом, без ссылки на async_result.
fresh = celery_app.AsyncResult(async_result.id)
print(json.dumps({"ready": fresh.ready(), "failed": fresh.failed(), "result": fresh.result}))
"""


@pytest.mark.skipif(not REDIS_AVAILABLE, reason=f"Redis недоступен на {CELERY_BROKER_URL}")
def test_task_roundtrip_through_real_celery_and_redis():
    """Проверяет реальный путь .delay() -> Redis -> свежий AsyncResult(id),
    как это делает GET /api/tasks/{task_id} — без мока, с настоящим брокером.

    Запускается в отдельном процессе: task_always_eager/task_store_eager_result
    у Celery можно понять только на старте приложения, а не переключить на
    лету у уже импортированного модуля — см. комментарий в app/tasks.py.
    """
    import json
    import subprocess
    import sys

    env = {**os.environ, "CELERY_TASK_ALWAYS_EAGER": "true"}
    proc = subprocess.run(
        [sys.executable, "-c", _ROUNDTRIP_SCRIPT],
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["ready"] is True
    assert payload["failed"] is False
    assert payload["result"]["success"] is True
    assert payload["result"]["review"]["score"] == 5
