"""Tests for the MCP tool analyze_audio, which has to wait for a queued analysis.

POST /api/analyze only returns a task_id; the tool must then poll
/api/tasks/{task_id} and hand the real result to the caller. The server is
replaced by httpx.MockTransport, so no network, Redis or worker is needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mcp_server  # noqa: E402

RESULT = {
    "success": True,
    "filename": "track.mp3",
    "features": {"rhythm": {"bpm": 123.06}},
    "review": {"source": "template", "score": 8.2},
}


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "track.mp3"
    path.write_bytes(b"fake-audio")
    return path


@pytest.fixture
def fake_server(monkeypatch):
    """Returns install(handler): routes the tool's HTTP calls to `handler` and records them."""
    calls: list[str] = []
    sleeps: list[float] = []
    real_client = httpx.Client

    def install(handler):
        def recording_handler(request: httpx.Request) -> httpx.Response:
            calls.append(f"{request.method} {request.url.path}")
            return handler(request)

        def client_factory(**kwargs):
            return real_client(transport=httpx.MockTransport(recording_handler), **kwargs)

        monkeypatch.setattr(
            mcp_server, "httpx", SimpleNamespace(Client=client_factory, HTTPError=httpx.HTTPError)
        )
        monkeypatch.setattr(mcp_server.time, "sleep", lambda seconds: sleeps.append(seconds))
        return SimpleNamespace(calls=calls, sleeps=sleeps)

    return install


def _task_server(*statuses):
    """A handler: accepts the upload, then answers each poll with the next status in the list."""
    remaining = list(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"task_id": "task-1"})
        return httpx.Response(200, json=remaining.pop(0) if len(remaining) > 1 else remaining[0])

    return handler


def test_waits_until_the_task_is_done_and_returns_the_real_result(audio_file, fake_server):
    server = fake_server(
        _task_server({"status": "pending"}, {"status": "pending"}, {"status": "done", "result": RESULT})
    )

    answer = json.loads(mcp_server.analyze_audio(str(audio_file)))

    assert answer == RESULT  # the analysis itself, not just a task_id
    assert server.calls == [
        "POST /api/analyze",
        "GET /api/tasks/task-1",
        "GET /api/tasks/task-1",
        "GET /api/tasks/task-1",
    ]
    assert server.sleeps == [mcp_server.POLL_INTERVAL_SEC] * 2  # it waited between the polls


def test_a_failed_task_becomes_an_error_answer(audio_file, fake_server):
    fake_server(_task_server({"status": "error", "error": "Файл повреждён"}))

    answer = json.loads(mcp_server.analyze_audio(str(audio_file)))

    assert answer == {"error": "Файл повреждён"}


def test_gives_up_after_the_timeout_and_says_which_task(audio_file, fake_server, monkeypatch):
    monkeypatch.setattr(mcp_server, "ANALYSIS_TIMEOUT_SEC", 0)
    fake_server(_task_server({"status": "pending"}))

    answer = json.loads(mcp_server.analyze_audio(str(audio_file)))

    assert "task-1" in answer["error"]
    assert "воркер" in answer["error"]


def test_a_rejected_upload_returns_the_servers_reason_without_polling(audio_file, fake_server):
    server = fake_server(lambda request: httpx.Response(400, json={"detail": "Пустой файл"}))

    answer = json.loads(mcp_server.analyze_audio(str(audio_file)))

    assert answer == {"error": "Пустой файл"}
    assert server.calls == ["POST /api/analyze"]


def test_an_unreachable_server_is_reported_instead_of_crashing(audio_file, fake_server):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    fake_server(handler)

    answer = json.loads(mcp_server.analyze_audio(str(audio_file)))

    assert mcp_server.MUSE_API in answer["error"]


def test_a_missing_file_is_reported_without_touching_the_server(tmp_path, fake_server):
    server = fake_server(lambda request: httpx.Response(500))

    answer = json.loads(mcp_server.analyze_audio(str(tmp_path / "nope.mp3")))

    assert "error" in answer
    assert server.calls == []
