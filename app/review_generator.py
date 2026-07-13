"""Генерация музыкальных обзоров: OpenAI API, Claude, Ollama, Nemotron или шаблонный fallback."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.llm_providers import LLMProviderFactory

logger = logging.getLogger(__name__)

SCALE_RU = {
    "major": "мажор",
    "minor": "минор",
    "unknown": "неопределённая",
}

KEY_RU = {
    "A": "ля", "B": "си", "C": "до", "D": "ре", "E": "ми",
    "F": "фа", "G": "соль",
    "Ab": "ля-бемоль", "Bb": "си-бемоль", "Db": "ре-бемоль",
    "Eb": "ми-бемоль", "Gb": "фа-бемоль",
}


def _translate_key(key: str, scale: str) -> str:
    key_name = KEY_RU.get(key, key)
    scale_name = SCALE_RU.get(scale.lower(), scale)
    return f"{key_name} {scale_name}"


def _energy_label(energy: float) -> str:
    if energy >= 0.75:
        return "высокая"
    if energy >= 0.5:
        return "умеренная"
    if energy >= 0.25:
        return "сдержанная"
    return "низкая"


def _brightness_label(brightness: float) -> str:
    if brightness >= 0.65:
        return "яркое, насыщенное верхними частотами"
    if brightness >= 0.4:
        return "сбалансированное по спектру"
    return "тёмное, с акцентом на низкие и средние частоты"


def _danceability_label(danceability: float | None) -> str:
    if danceability is None:
        return "ритмическая структура не позволяет однозначно оценить танцевальность"
    if danceability >= 0.7:
        return "выраженно танцевальный характер"
    if danceability >= 0.45:
        return "умеренная танцевальность"
    return "скорее слушательский, чем танцевальный материал"


def _tempo_label(bpm: float) -> str:
    if bpm < 80:
        return "медленный, созерцательный темп"
    if bpm < 110:
        return "умеренный, размеренный темп"
    if bpm < 130:
        return "энергичный, движущийся темп"
    return "быстрый, напряжённый темп"


def _dynamics_label(complexity: float, loudness: float) -> str:
    if complexity >= 0.5:
        dyn = "широкий динамический диапазон с выраженными контрастами"
    elif complexity >= 0.25:
        dyn = "умеренная динамическая вариативность"
    else:
        dyn = "сжатая, ровная динамика"

    if loudness >= -8:
        loud = "громкая, плотная подача"
    elif loudness >= -14:
        loud = "средняя громкость, коммерчески сбалансированная"
    else:
        loud = "тихая, интимная подача"

    return f"{dyn}; {loud}"


def _build_template_review(features: dict[str, Any]) -> dict[str, Any]:
    """Шаблонный обзор на русском без внешнего API."""
    rhythm = features.get("rhythm", {})
    tonal = features.get("tonal", {})
    dynamics = features.get("dynamics", {})
    spectral = features.get("spectral", {})

    bpm = rhythm.get("bpm", 0)
    key = tonal.get("key", "?")
    scale = tonal.get("scale", "unknown")
    key_strength = tonal.get("key_strength", 0)
    danceability = tonal.get("danceability")
    energy = features.get("energy", 0.5)
    brightness = spectral.get("spectral_brightness", 0.5)
    loudness = dynamics.get("loudness_ebu128_lufs", -14)
    dyn_complexity = dynamics.get("dynamic_complexity", 0.3)
    duration = features.get("duration_sec", 0)

    key_text = _translate_key(key, scale)
    energy_text = _energy_label(energy)
    brightness_text = _brightness_label(brightness)
    dance_text = _danceability_label(danceability)
    tempo_text = _tempo_label(bpm)
    dynamics_text = _dynamics_label(dyn_complexity, loudness)

    tonal_clarity = (
        "чётко выраженная тональность"
        if key_strength >= 0.7
        else "размытая или модальная тональность"
        if key_strength < 0.4
        else "умеренно определённая тональность"
    )

    summary = (
        f"Композиция длительностью {duration} с демонстрирует {tempo_text} "
        f"({bpm} уд./мин) в тональности {key_text}. "
        f"Общая энергетика трека — {energy_text}, спектральный характер — {brightness_text}."
    )

    rhythm_section = (
        f"Ритмический анализ выявил {rhythm.get('beats_count', 0)} ударных импульсов "
        f"с уверенностью детекции {rhythm.get('beat_confidence', 0):.0%}. "
        f"Частота атак (onset rate): {rhythm.get('onset_rate', 0):.2f}. "
        f"{dance_text.capitalize()}."
    )

    tonal_section = (
        f"Тональный центр — {key_text} (сила тональности: {key_strength:.0%}). "
        f"{tonal_clarity.capitalize()}. "
        f"Строй: {tonal.get('tuning_frequency_hz', 440)} Гц."
    )

    production_section = (
        f"Динамика и продакшн: {dynamics_text}. "
        f"Спектральный центр — {spectral.get('spectral_centroid_hz', 0):.0f} Гц, "
        f"спектральная сложность (flux) — {spectral.get('spectral_flux', 0):.3f}. "
        f"RMS-уровень: {dynamics.get('rms', 0):.3f}."
    )

    verdict_score = round(
        min(
            10,
            5
            + (energy * 1.5)
            + (key_strength * 1.5)
            + ((danceability or 0.5) * 1.0)
            + (min(dyn_complexity, 0.6) * 1.5),
        ),
        1,
    )

    if verdict_score >= 8:
        verdict = "Сильная работа с выразительной структурой и убедительной подачей."
    elif verdict_score >= 6:
        verdict = "Солидный трек с интересными характеристиками, есть потенциал для развития."
    else:
        verdict = "Экспериментальный или минималистичный материал; оценка субъективна."

    full_text = "\n\n".join([summary, rhythm_section, tonal_section, production_section, verdict])

    return {
        "source": "template",
        "language": "ru",
        "score": verdict_score,
        "sections": {
            "summary": summary,
            "rhythm": rhythm_section,
            "tonality": tonal_section,
            "production": production_section,
            "verdict": verdict,
        },
        "full_text": full_text,
    }


def generate_review(features: dict[str, Any]) -> dict[str, Any]:
    """
    Генерирует музыкальный обзор.

    Использует LLM провайдера из конфигурации (OpenAI, Claude, Ollama, Nemotron)
    с fallback на шаблонный обзор при ошибке.

    Args:
        features: Словарь со всеми параметрами аудиоанализа

    Returns:
        Словарь с обзором (source, language, score, sections, full_text, model)
    """
    try:
        provider = LLMProviderFactory.get_provider()
        logger.info("Используется LLM провайдер: %s", provider.__class__.__name__)
        review = provider.generate_review(features)
        return review

    except ValueError as exc:
        logger.warning("LLM провайдер недоступен (%s) — используется шаблонный обзор", exc)
        return _build_template_review(features)
    except Exception as exc:
        logger.warning("Ошибка LLM (%s) — fallback на шаблон", exc)
        result = _build_template_review(features)
        result["llm_error"] = str(exc)
        return result

