"""Извлечение музыкальных признаков с помощью Essentia."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ESSENTIA_AVAILABLE = False
ESSENTIA_ERROR: str | None = None

try:
    import essentia
    import essentia.standard as es

    ESSENTIA_AVAILABLE = True
except ImportError as exc:
    ESSENTIA_ERROR = str(exc)


class AudioAnalysisError(Exception):
    """Ошибка при анализе аудиофайла."""


def _coerce_to_float(value: Any, default: float | None = None) -> float | None:
    """Преобразовать значение Essentia к float, поддерживая массивы и кортежи."""
    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, tuple):
        if not value:
            return default
        # В некоторых версиях Essentia возвращает (value, extra_info) или подобное.
        for item in value:
            coerced = _coerce_to_float(item, default=None)
            if coerced is not None:
                return coerced
        return default

    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except Exception:
            return default

    if isinstance(value, list):
        if not value:
            return default
        if all(isinstance(item, (int, float)) for item in value):
            return round(sum(float(item) for item in value) / len(value), 4)
        for item in value:
            coerced = _coerce_to_float(item, default=None)
            if coerced is not None:
                return coerced
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _check_essentia() -> None:
    if not ESSENTIA_AVAILABLE:
        raise AudioAnalysisError(
            "Библиотека Essentia не установлена. "
            "См. README для инструкций по установке на macOS."
        )


def _frame_features(audio: Any, sample_rate: int) -> dict[str, float]:
    """Спектральные и ритмические признаки по кадрам."""
    frame_size = 2048
    hop_size = 1024

    windowing = es.Windowing(type="hann", size=frame_size)
    spectrum_algo = es.Spectrum(size=frame_size)
    centroid_algo = es.Centroid(range=sample_rate / 2)
    rolloff_algo = es.RollOff(sampleRate=sample_rate)
    flux_algo = es.Flux()
    zcr_algo = es.ZeroCrossingRate()
    mfcc_algo = es.MFCC(
        numberCoefficients=13,
        sampleRate=sample_rate,
        lowFrequencyBound=20,
        highFrequencyBound=sample_rate / 2,
    )

    centroids: list[float] = []
    rolloffs: list[float] = []
    fluxes: list[float] = []
    zcrs: list[float] = []
    mfcc_means: list[list[float]] = []

    prev_spectrum = None
    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size):
        windowed = windowing(frame)
        spectrum = spectrum_algo(windowed)

        centroids.append(float(centroid_algo(spectrum)))
        rolloffs.append(float(rolloff_algo(spectrum)))
        zcrs.append(float(zcr_algo(frame)))

        if prev_spectrum is not None:
            try:
                flux_value = flux_algo(spectrum, prev_spectrum)
            except Exception:
                try:
                    flux_value = flux_algo(spectrum)
                except Exception:
                    flux_value = 0.0
            fluxes.append(float(_coerce_to_float(flux_value, default=0.0)))
        prev_spectrum = spectrum

        _, mfcc_coeffs = mfcc_algo(spectrum)
        mfcc_means.append([float(c) for c in mfcc_coeffs])

    def _avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    mfcc_avg = []
    if mfcc_means:
        n_coeffs = len(mfcc_means[0])
        for i in range(n_coeffs):
            mfcc_avg.append(round(sum(row[i] for row in mfcc_means) / len(mfcc_means), 4))

    brightness_hz = _avg(centroids)
    # Нормализованная яркость 0–1 относительно Nyquist
    brightness_norm = round(min(brightness_hz / (sample_rate / 2), 1.0), 4)

    return {
        "spectral_centroid_hz": brightness_hz,
        "spectral_brightness": brightness_norm,
        "spectral_rolloff_hz": _avg(rolloffs),
        "spectral_flux": _avg(fluxes),
        "zero_crossing_rate": _avg(zcrs),
        "mfcc_coefficients": mfcc_avg,
    }


def _tonal_features(audio: Any) -> dict[str, Any]:
    """Тональность, гармония и танцевальность."""
    key, scale, key_strength = es.KeyExtractor()(audio)
    tuning_freq = _coerce_to_float(es.TuningFrequencyExtractor()(audio))

    try:
        danceability, dfa = es.Danceability()(audio)
        danceability = round(_coerce_to_float(danceability, default=None), 4) if _coerce_to_float(danceability, default=None) is not None else None
        dfa_value = round(_coerce_to_float(dfa, default=None), 4) if _coerce_to_float(dfa, default=None) is not None else None
    except Exception:
        danceability = None
        dfa_value = None

    try:
        chords, strength = es.ChordsDetection()(audio)
        chord_hist: dict[str, int] = {}
        for chord in chords:
            chord_hist[chord] = chord_hist.get(chord, 0) + 1
        top_chords = sorted(chord_hist.items(), key=lambda x: x[1], reverse=True)[:5]
    except Exception:
        top_chords = []

    return {
        "key": key,
        "scale": scale,
        "key_strength": round(_coerce_to_float(key_strength, default=0.0), 4),
        "tuning_frequency_hz": round(tuning_freq, 2) if tuning_freq is not None else None,
        "danceability": danceability,
        "danceability_dfa": dfa_value,
        "top_chords": [{"chord": c, "count": n} for c, n in top_chords],
    }


def _rhythm_features(audio: Any) -> dict[str, Any]:
    """Темп, ритм и пульс."""
    rhythm = es.RhythmExtractor2013(method="multifeature")
    bpm, beats, confidence, _, beat_intervals = rhythm(audio)

    onset_rate = _coerce_to_float(es.OnsetRate()(audio), default=None)
    try:
        beat_loudness = _coerce_to_float(es.BeatLoudness()(audio), default=None)
    except Exception:
        beat_loudness = None
    try:
        beat_loudness_band_ratio = _coerce_to_float(es.BeatLoudnessBandRatio()(audio), default=None)
    except Exception:
        beat_loudness_band_ratio = None

    return {
        "bpm": round(_coerce_to_float(bpm, default=0.0), 2),
        "beat_confidence": round(_coerce_to_float(confidence, default=0.0), 4),
        "beats_count": len(beats),
        "onset_rate": round(onset_rate, 4) if onset_rate is not None else None,
        "beat_loudness": round(beat_loudness, 4) if beat_loudness is not None else None,
        "beat_loudness_band_ratio": round(beat_loudness_band_ratio, 4) if beat_loudness_band_ratio is not None else None,
        "avg_beat_interval_sec": round(
            sum(_coerce_to_float(i, default=0.0) for i in beat_intervals) / len(beat_intervals), 4
        )
        if len(beat_intervals) > 0
        else None,
    }


def _dynamics_features(audio: Any) -> dict[str, Any]:
    """Громкость и динамика."""
    try:
        _, _, loudness_ebu, _ = es.LoudnessEBUR128()(audio)
        loudness_ebu = _coerce_to_float(loudness_ebu, default=None)
    except Exception:
        loudness_ebu = None

    loudness = _coerce_to_float(es.Loudness()(audio), default=None)
    dynamic_complexity = _coerce_to_float(es.DynamicComplexity()(audio), default=None)

    try:
        replay_gain = _coerce_to_float(es.ReplayGain()(audio), default=None)
    except Exception:
        replay_gain = None

    rms = _coerce_to_float(es.RMS()(audio), default=None)

    return {
        "loudness_ebu128_lufs": round(loudness_ebu, 2) if loudness_ebu is not None else None,
        "loudness_db": round(loudness, 2) if loudness is not None else None,
        "dynamic_complexity": round(dynamic_complexity, 4) if dynamic_complexity is not None else None,
        "replay_gain_db": round(replay_gain, 2) if replay_gain is not None else None,
        "rms": round(rms, 4) if rms is not None else None,
    }


def _energy_proxy(features: dict[str, Any]) -> float:
    """Оценка энергичности на основе доступных признаков (0–1)."""
    rms = features.get("dynamics", {}).get("rms") or 0.0
    bpm = features.get("rhythm", {}).get("bpm") or 120.0
    brightness = features.get("spectral", {}).get("spectral_brightness") or 0.5
    danceability = features.get("tonal", {}).get("danceability") or 0.5

    # Нормализация BPM: 60–180 → 0–1
    bpm_norm = min(max((bpm - 60) / 120, 0.0), 1.0)
    rms_norm = min(rms * 10, 1.0)

    energy = 0.3 * rms_norm + 0.25 * bpm_norm + 0.25 * brightness + 0.2 * danceability
    return round(min(max(energy, 0.0), 1.0), 4)


def analyze_audio(file_path: str | Path) -> dict[str, Any]:
    """
    Полный анализ аудиофайла.

    Возвращает словарь с сырыми параметрами Essentia и метаданными.
    """
    _check_essentia()

    path = Path(file_path)
    if not path.exists():
        raise AudioAnalysisError(f"Файл не найден: {path}")

    try:
        loader = es.MonoLoader(filename=str(path), sampleRate=44100)
        audio = loader()
        sample_rate = 44100
    except Exception as exc:
        raise AudioAnalysisError(
            f"Не удалось загрузить аудио. Проверьте формат файла и наличие ffmpeg. "
            f"Детали: {exc}"
        ) from exc

    if len(audio) == 0:
        raise AudioAnalysisError("Аудиофайл пуст или повреждён.")

    duration_sec = round(len(audio) / sample_rate, 2)

    try:
        rhythm = _rhythm_features(audio)
        tonal = _tonal_features(audio)
        dynamics = _dynamics_features(audio)
        spectral = _frame_features(audio, sample_rate)
    except Exception as exc:
        logger.exception("Ошибка извлечения признаков")
        raise AudioAnalysisError(f"Ошибка анализа Essentia: {exc}") from exc

    result: dict[str, Any] = {
        "file": path.name,
        "essentia_version": essentia.__version__,
        "duration_sec": duration_sec,
        "sample_rate": sample_rate,
        "rhythm": rhythm,
        "tonal": tonal,
        "dynamics": dynamics,
        "spectral": spectral,
    }
    result["energy"] = _energy_proxy(result)

    return result
