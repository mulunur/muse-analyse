#!/usr/bin/env python3
"""Ручная проверка MCP сервера без Claude Desktop.

Это не автоматический тест, а CLI-скрипт для быстрой проверки вручную:
    python scripts/check_mcp_server.py
"""

import json
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check_mcp_server():
    """Проверяет основные инструменты MCP сервера."""
    from mcp_server import analyze_audio, check_providers, get_status

    print("🎵 Тест MCP сервера Muse Analyse\n")

    # Тест 1: check_providers
    print("1️⃣  Проверяем доступные провайдеры...")
    data = json.loads(check_providers())
    print(f"   ✓ Доступные: {list(data.get('available', {}).keys())}\n")

    # Тест 2: get_status
    print("2️⃣  Проверяем статус системы...")
    data = json.loads(get_status())
    print(f"   ✓ Essentia: {data.get('essentia_available')}")
    print(f"   ✓ Версия: {data.get('version')}\n")

    # Тест 3: analyze_audio (если есть тестовый файл)
    test_file = ROOT / "test_track.mp3"
    if test_file.exists():
        print(f"3️⃣  Анализируем {test_file.name}...")
        data = json.loads(analyze_audio(str(test_file)))
        if "error" not in data:
            print(f"   ✓ BPM: {data['features']['rhythm']['bpm']}")
            print(f"   ✓ Оценка: {data['review']['score']}/10\n")
        else:
            print(f"   ✗ Ошибка: {data['error']}\n")
    else:
        print(f"3️⃣  Пропускаем анализ (нет test_track.mp3)\n")

    print("✅ MCP сервер работает!")


if __name__ == "__main__":
    check_mcp_server()
