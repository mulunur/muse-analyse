#!/usr/bin/env python3
"""
Examples of using different LLM providers through the Muse Analyse API
"""

import json
import requests
from pathlib import Path


def check_available_providers():
    """Checks which providers are available."""
    response = requests.get("http://localhost:8000/api/providers")
    print("Доступные LLM провайдеры:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))


def analyze_audio_file(file_path: str):
    """Sends an audio file for analysis."""
    if not Path(file_path).exists():
        print(f"Ошибка: файл {file_path} не найден")
        return

    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post("http://localhost:8000/api/analyze", files=files)

    if response.status_code == 200:
        result = response.json()
        
        # Review info
        review = result.get("review", {})
        print(f"\n📊 Обзор от провайдера: {review.get('source')} ({review.get('model', 'unknown')})")
        print(f"⭐ Оценка: {review.get('score', 'N/A')}/10")
        print(f"\n{review.get('full_text', 'Обзор недоступен')}")
        
        # Main parameters
        features = result.get("features", {})
        print(f"\n📈 Основные параметры:")
        print(f"  • Длительность: {features.get('duration_sec')} сек")
        print(f"  • BPM: {features.get('rhythm', {}).get('bpm')} уд./мин")
        print(f"  • Тональность: {features.get('tonal', {}).get('key')} {features.get('tonal', {}).get('scale')}")
        print(f"  • Энергия: {features.get('energy')}")
        print(f"  • Танцевальность: {features.get('tonal', {}).get('danceability')}")
    else:
        print(f"Ошибка: {response.status_code}")
        print(response.text)


def compare_providers():
    """
    Compares the results of different providers for one track.
    
    Needs the file to be available locally for every request.
    """
    # First check availability
    providers_response = requests.get("http://localhost:8000/api/providers")
    available = providers_response.json()["available"]
    
    available_providers = [name for name, is_available in available.items() if is_available]
    print(f"Доступные провайдеры: {', '.join(available_providers)}\n")
    
    if not available_providers:
        print("Ошибка: нет доступных провайдеров!")
        return
    
    print("Примечание: для сравнения провайдеров измените LLM_PROVIDER в .env и перезагрузите сервер.")
    print(f"Текущий провайдер проверен через /api/health")


if __name__ == "__main__":
    import sys

    print("=== Примеры использования Muse Analyse с разными LLM провайдерами ===\n")

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"Анализируем файл: {file_path}\n")
        analyze_audio_file(file_path)
    else:
        print("Использование:")
        print("  python examples/test_providers.py <путь-к-аудиофайлу>\n")
        print("Доступные операции:")
        print("  check_available_providers() - показывает доступные провайдеры")
        print("  analyze_audio_file(file_path) - анализирует аудиофайл текущим провайдером")
        print("  compare_providers() - сравнивает провайдеры\n")
        
        check_available_providers()
