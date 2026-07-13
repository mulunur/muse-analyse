# MCP Server для Muse Analyse

Для интеграции Muse Analyse как MCP сервера в Claude Desktop или других приложениях, вам понадобится MCP server wrapper.

## Минимальная реализация MCP Server

Создайте файл `mcp_server.py` в корне проекта:

```python
"""MCP Server для Muse Analyse — анализ музыкальных композиций."""

import json
from pathlib import Path

from mcp.server import Server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
    ToolUseBlock,
)
from pydantic import BaseModel

import httpx

SERVER_URL = "http://localhost:8000"

server = Server("muse-analyse")


class AudioFeatures(BaseModel):
    duration_sec: float
    bpm: float
    key: str
    scale: str
    energy: float
    danceability: float | None
    loudness_ebu128_lufs: float
    dynamic_complexity: float
    spectral_brightness: float


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Возвращает список доступных инструментов."""
    return [
        Tool(
            name="check_providers",
            description="Проверить какие LLM провайдеры доступны для анализа",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="analyze_audio",
            description="Загрузить аудиофайл и получить анализ музыки с AI-обзором",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к аудиофайлу (MP3, WAV, FLAC, OGG, M4A)",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="get_health",
            description="Получить статус сервиса и доступности компонентов",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Выполняет вызванный инструмент."""
    
    if name == "check_providers":
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SERVER_URL}/api/providers")
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
    
    elif name == "analyze_audio":
        file_path = arguments.get("file_path")
        if not Path(file_path).exists():
            return json.dumps({"error": f"Файл не найден: {file_path}"})
        
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                files = {"file": (Path(file_path).name, f)}
                response = await client.post(
                    f"{SERVER_URL}/api/analyze",
                    files=files,
                    timeout=300,
                )
        
        if response.status_code == 200:
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        else:
            return json.dumps({"error": response.text})
    
    elif name == "get_health":
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SERVER_URL}/api/health")
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
    
    else:
        return json.dumps({"error": f"Неизвестный инструмент: {name}"})


if __name__ == "__main__":
    import asyncio
    
    # Запуск MCP server на stdio
    async def main():
        async with server:
            await server.wait_for_shutdown()
    
    asyncio.run(main())
```

## Интеграция с Claude Desktop

### 1. Установите MCP SDK

```bash
pip install mcp httpx
```

### 2. Добавьте конфигурацию

**На macOS:**
Отредактируйте `~/Library/Application\ Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "muse-analyse": {
      "command": "python",
      "args": [
        "/path/to/muse-analyse/mcp_server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**На Windows:**
`%APPDATA%\Claude\claude_desktop_config.json`

**На Linux:**
`~/.config/Claude/claude_desktop_config.json`

### 3. Запустите Muse Analyse сервер

```bash
cd /path/to/muse-analyse
python run.py
```

### 4. Перезагрузите Claude Desktop

Теперь в Claude Desktop будут доступны инструменты:
- **check_providers** — проверить доступные LLM
- **analyze_audio** — загрузить и проанализировать трек
- **get_health** — статус системы

## Примеры использования в Claude

### Анализ трека
```
Проанализируй трек "~/Music/song.mp3" и дай детальный обзор
```

Claude использует инструмент `analyze_audio`, получит все параметры и обзор от Essentia + LLM.

### Проверка настроек
```
Какие LLM провайдеры доступны для анализа музыки?
```

Claude использует `check_providers` и покажет статус.

---

## Альтернатива: FastAPI + nginx

Если вы хотите использовать Muse Analyse через обычный HTTP API без MCP:

```bash
# Запустите сервер
python run.py

# Используйте API напрямую через curl или Python requests
curl http://localhost:8000/api/providers
```

---

## Документация

- [MCP Protocol](https://modelcontextprotocol.io/)
- [Claude Desktop Configuration](https://claude.ai/desktop)
- [Muse Analyse API](./README.md)
- [LLM Провайдеры](./LLM_PROVIDERS.md)
