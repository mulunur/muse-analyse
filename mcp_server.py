#!/usr/bin/env python3
"""MCP сервер для Muse Analyse."""

import json
import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

# Сервер Muse Analyse по умолчанию
MUSE_API = os.getenv("MUSE_API", "http://localhost:8000").rstrip("/")

mcp = FastMCP("muse-analyse")


@mcp.tool()
def check_providers() -> str:
    """Проверить доступные LLM провайдеры."""
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{MUSE_API}/api/providers")
        return json.dumps(r.json(), ensure_ascii=False)


@mcp.tool()
def analyze_audio(file_path: str) -> str:
    """Анализ аудиофайла: параметры Essentia + AI-обзор."""
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"Файл не найден: {path}"})

    with path.open("rb") as f:
        files = {"file": (path.name, f)}
        with httpx.Client(timeout=300) as client:
            r = client.post(f"{MUSE_API}/api/analyze", files=files)
            return json.dumps(r.json(), ensure_ascii=False)


@mcp.tool()
def get_status() -> str:
    """Статус системы: Essentia, провайдеры."""
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{MUSE_API}/api/health")
        return json.dumps(r.json(), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
