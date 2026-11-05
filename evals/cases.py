"""Кейсы для eval: "вход -> что мы ожидаем от результата".

Это и есть "набор данных" eval. Чтобы добавить проверку, допишите словарь в
нужный список ниже — больше ничего менять не нужно.
"""


def _features(*, bpm, key, scale, key_strength, energy, lufs, dynamics, danceability,
              brightness=0.4, duration=200.0):
    """Собирает словарь признаков в том же виде, в каком его отдаёт analyze_audio().

    Аудиофайлы для eval не нужны: обзор строится только по этим числам.
    None означает "Essentia не смогла посчитать этот параметр".
    """
    return {
        "duration_sec": duration,
        "rhythm": {"bpm": bpm, "beat_confidence": 0.8, "beats_count": int(bpm * duration / 60)},
        "tonal": {"key": key, "scale": scale, "key_strength": key_strength,
                  "danceability": danceability},
        "dynamics": {"loudness_ebu128_lufs": lufs, "dynamic_complexity": dynamics, "rms": 0.2},
        "spectral": {"spectral_brightness": brightness, "spectral_centroid_hz": 2500.0,
                     "spectral_flux": 0.1},
        "energy": energy,
    }


# --- Обзор трека: generate_review(features) --------------------------------
# expect (необязательно):
#   bpm     - число, которое обзор должен упомянуть (проверка "опирается на параметры")
#   no_lufs - True, если громкость неизвестна и обзор не должен выдумывать LUFS
REVIEW_CASES = [
    {
        "id": "fast_electronic",
        "features": _features(bpm=140, key="A", scale="minor", key_strength=0.85,
                              energy=0.9, lufs=-7.0, dynamics=0.15, danceability=0.8,
                              brightness=0.7),
        "expect": {"bpm": 140},
    },
    {
        "id": "slow_ballad",
        "features": _features(bpm=62, key="C", scale="major", key_strength=0.6,
                              energy=0.2, lufs=-18.0, dynamics=0.6, danceability=0.25,
                              brightness=0.2, duration=260.0),
        "expect": {"bpm": 62},
    },
    {
        # Essentia не посчитала громкость и танцевальность: модель не должна их придумывать.
        "id": "missing_data",
        "features": _features(bpm=100, key="D", scale="minor", key_strength=0.5,
                              energy=0.5, lufs=None, dynamics=None, danceability=None),
        "expect": {"bpm": 100, "no_lufs": True},
    },
    {
        # Реальные числа, снятые с одного из треков, — аудио в кейсе нет.
        "id": "real_track_example",
        "features": _features(bpm=123.06, key="F", scale="major", key_strength=0.7248,
                              energy=0.5363, lufs=-9.15, dynamics=4.2887, danceability=0.37,
                              brightness=0.1236, duration=243.65),
        "expect": {"bpm": 123},
    },
]


# --- Критик: critique_agent(state) -----------------------------------------
# Здесь правильный ответ известен заранее — мы сами его задали.
# expect_passed: должен ли критик пропустить черновик (True) или забраковать (False).
_PROFILE = {
    "tone": "тёплый, интимный",
    "themes": ["ночной город", "одиночество"],
    "avoid": ["вайб", "эксклюзивный", "уникальный"],
}

CRITIQUE_CASES = [
    {
        # Первая версия этого кейса заканчивалась фразой "Новый трек уже на всех
        # площадках" — критик забраковал её как слишком коммерческую для тёплого
        # интимного тона, и по делу. Ошибся не критик, а кейс: провал eval не
        # всегда значит "модель плохая", иногда плох сам тест. Фразу убрали.
        "id": "clean_draft_1",
        "profile": _PROFILE,
        "drafts": {"d1": "Ночной город засыпает, а я пишу песню о том, как тихо бывает "
                         "в окнах напротив."},
        "expect_passed": True,
    },
    {
        "id": "clean_draft_2",
        "profile": _PROFILE,
        "drafts": {"d1": "Иногда одиночество звучит как последний трамвай. Этот трек — о нём."},
        "expect_passed": True,
    },
    {
        "id": "uses_forbidden_word_vibe",
        "profile": _PROFILE,
        "drafts": {"d1": "Новый трек — это настоящий вайб ночного города. Слушайте везде!"},
        "expect_passed": False,
    },
    {
        "id": "uses_forbidden_words_exclusive",
        "profile": _PROFILE,
        "drafts": {"d1": "Представляем эксклюзивный релиз — уникальный звук, "
                         "которого вы ещё не слышали."},
        "expect_passed": False,
    },
    {
        # Слов из запрета нет, но тон и темы совсем не те: это сложнее первых четырёх.
        "id": "off_tone_sales_pitch",
        "profile": _PROFILE,
        "drafts": {"d1": "Покупайте наш мерч со скидкой 50%! Только сегодня, успейте!!!"},
        "expect_passed": False,
    },
]
