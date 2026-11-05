"""Tests for the Celery tasks.

Most of them call the task functions directly (without a broker: a Celery task
is still an ordinary callable function) and replace the heavy dependencies with
monkeypatch. One test at the bottom is a real end-to-end check through real
Celery in eager mode and a real Redis; it is skipped if Redis is unavailable,
as is already the custom in this project for Essentia and Ollama.
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
    """A stand-in for growth_graph: records invoke() calls and does not touch the LLM or the checkpointer."""

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
        # snapshot.values returns content_ideas as Pydantic objects, not dicts,
        # and that is exactly what breaks json.dumps without an explicit model_dump.
        fake_graph = FakeGraph({"content_ideas": [idea]})
        monkeypatch.setattr("app.agents.graph.growth_graph", fake_graph)

        result = growth_start_task(str(audio_path), ["материал"], "thread-1")

        assert result["success"] is True
        assert result["thread_id"] == "thread-1"
        assert result["content_ideas"] == [idea.model_dump(mode="json")]
        assert isinstance(result["content_ideas"][0], dict)
        # The next step (select) needs the file, so on success it is not deleted here.
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
        # get_state reads whatever already made it into the checkpoint (including the
        # original audio_path), even if invoke() itself crashed.
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
    """Checks the real path .delay() -> Redis -> a fresh AsyncResult(id),
    just like GET /api/tasks/{task_id} does, with no mocks and with a real broker.

    It runs in a separate process: Celery only lets you set
    task_always_eager / task_store_eager_result when the app starts, you cannot
    switch them on the fly in a module that is already imported. See the comment in app/tasks.py.
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
