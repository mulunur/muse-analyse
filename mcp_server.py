#!/usr/bin/env python3
"""MCP server for Muse Analyse."""

import json
import os
import time
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

# The default Muse Analyse server
MUSE_API = os.getenv("MUSE_API", "http://localhost:8000").rstrip("/")

# /api/analyze only queues the analysis and returns a task_id, so analyze_audio has
# to wait for the result: it asks "is it ready?" every POLL_INTERVAL_SEC seconds and
# gives up after ANALYSIS_TIMEOUT_SEC.
ANALYSIS_TIMEOUT_SEC = int(os.getenv("MUSE_ANALYSIS_TIMEOUT", "300"))
POLL_INTERVAL_SEC = 2

mcp = FastMCP("muse-analyse")


def _wait_for_task(client: httpx.Client, task_id: str) -> dict:
    """Polls /api/tasks/{task_id} until the task finishes.

    Returns the task's result, or {"error": ...} if it failed or took too long.
    """
    deadline = time.monotonic() + ANALYSIS_TIMEOUT_SEC
    while True:
        r = client.get(f"{MUSE_API}/api/tasks/{task_id}")
        r.raise_for_status()
        state = r.json()

        if state["status"] == "done":
            return state["result"]
        if state["status"] == "error":
            return {"error": state.get("error", "Неизвестная ошибка")}

        if time.monotonic() >= deadline:
            return {
                "error": (
                    f"Анализ не завершился за {ANALYSIS_TIMEOUT_SEC} с (task_id: {task_id}). "
                    "Проверьте, что воркер запущен."
                )
            }
        time.sleep(POLL_INTERVAL_SEC)


@mcp.tool()
def check_providers() -> str:
    """Check which LLM providers are available."""
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{MUSE_API}/api/providers")
        return json.dumps(r.json(), ensure_ascii=False)


@mcp.tool()
def analyze_audio(file_path: str) -> str:
    """Analyse an audio file: Essentia parameters plus an AI review."""
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"Файл не найден: {path}"})

    try:
        with httpx.Client(timeout=60) as client:
            with path.open("rb") as f:
                r = client.post(f"{MUSE_API}/api/analyze", files={"file": (path.name, f)})
            body = r.json()

            task_id = body.get("task_id") if r.status_code == 200 else None
            if not task_id:
                # The server turned the upload down (unsupported format, empty file, too big...)
                return json.dumps({"error": body.get("detail", body)}, ensure_ascii=False)

            result = _wait_for_task(client, task_id)
    except httpx.HTTPError as exc:
        return json.dumps(
            {"error": f"Не удалось связаться с сервером Muse Analyse ({MUSE_API}): {exc}"},
            ensure_ascii=False,
        )

    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def get_status() -> str:
    """System status: Essentia and the providers."""
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{MUSE_API}/api/health")
        return json.dumps(r.json(), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
