#!/usr/bin/env python3
"""MCP сервер для Muse Analyse."""

import json
from pathlib import Path

import httpx
from mcp.server import Server
from mcp.types import Tool

# Сервер Muse Analyse по умолчанию
MUSE_API = "http://localhost:8000"

server = Server("muse-analyse")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Список доступных инструментов."""
    return [
        Tool(
            name="check_providers",
            description="Проверить доступные LLM провайдеры",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="analyze_audio",
            description="Анализ аудиофайла: параметры Essentia + AI-обзор",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу (MP3/WAV/FLAC/OGG/M4A)",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="get_status",
            description="Статус системы: Essentia, провайдеры",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Выполнить инструмент."""
    async with httpx.AsyncClient() as client:
        try:
            if name == "check_providers":
                r = await client.get(f"{MUSE_API}/api/providers", timeout=10)
                return json.dumps(r.json(), ensure_ascii=False)

            elif name == "analyze_audio":
                path = arguments.get("file_path")
                if not Path(path).exists():
                    return json.dumps({"error": f"Файл не найден: {path}"})

                with open(path, "rb") as f:
                    files = {"file": (Path(path).name, f)}
                    r = await client.post(
                        f"{MUSE_API}/api/analyze",
                        files=files,
                        timeout=300,
                    )
                return json.dumps(r.json(), ensure_ascii=False)

            elif name == "get_status":
                r = await client.get(f"{MUSE_API}/api/health", timeout=10)
                return json.dumps(r.json(), ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)})


if __name__ == "__main__":
    import asyncio

    async def main():
        async with server:
            await server.wait_for_shutdown()

    asyncio.run(main())
