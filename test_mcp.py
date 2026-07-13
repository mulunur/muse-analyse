#!/usr/bin/env python3
"""Тест MCP сервера без Claude Desktop."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_mcp():
    """Тест основных инструментов."""
    from mcp_server import call_tool

    print("🎵 Тест MCP сервера Muse Analyse\n")

    # Тест 1: check_providers
    print("1️⃣  Проверяем доступные провайдеры...")
    result = await call_tool("check_providers", {})
    data = json.loads(result)
    print(f"   ✓ Доступные: {list(data.get('available', {}).keys())}\n")

    # Тест 2: get_status
    print("2️⃣  Проверяем статус системы...")
    result = await call_tool("get_status", {})
    data = json.loads(result)
    print(f"   ✓ Essentia: {data.get('essentia_available')}")
    print(f"   ✓ Версия: {data.get('version')}\n")

    # Тест 3: analyze_audio (если есть тестовый файл)
    test_file = Path(__file__).parent / "test_track.mp3"
    if test_file.exists():
        print(f"3️⃣  Анализируем {test_file.name}...")
        result = await call_tool("analyze_audio", {"file_path": str(test_file)})
        data = json.loads(result)
        if "error" not in data:
            print(f"   ✓ BPM: {data['features']['rhythm']['bpm']}")
            print(f"   ✓ Оценка: {data['review']['score']}/10\n")
        else:
            print(f"   ✗ Ошибка: {data['error']}\n")
    else:
        print(f"3️⃣  Пропускаем анализ (нет test_track.mp3)\n")

    print("✅ MCP сервер работает!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_mcp())
