"""Eval cases: "input -> what we expect from the result".

This is the eval "dataset". To add a check, append a dict to the right list
below; nothing else needs to change.
"""


def _features(*, bpm, key, scale, key_strength, energy, lufs, dynamics, danceability,
              brightness=0.4, duration=200.0):
    """Builds a features dict in the same shape that analyze_audio() returns.

    Eval needs no audio files: the review is built from these numbers alone.
    None means "Essentia could not compute this parameter".
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


# --- Track review: generate_review(features) --------------------------------
# expect (optional):
#   bpm     - a number the review should mention (checks that it "relies on the parameters")
#   no_lufs - True if the loudness is unknown and the review must not invent LUFS
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
        # Essentia could not compute loudness and danceability: the model must not invent them.
        "id": "missing_data",
        "features": _features(bpm=100, key="D", scale="minor", key_strength=0.5,
                              energy=0.5, lufs=None, dynamics=None, danceability=None),
        "expect": {"bpm": 100, "no_lufs": True},
    },
    {
        # Real numbers taken from one of the tracks; there is no audio in the case.
        "id": "real_track_example",
        "features": _features(bpm=123.06, key="F", scale="major", key_strength=0.7248,
                              energy=0.5363, lufs=-9.15, dynamics=4.2887, danceability=0.37,
                              brightness=0.1236, duration=243.65),
        "expect": {"bpm": 123},
    },
]


# --- Critic: critique_agent(state) -----------------------------------------
# The right answer is known in advance here, because we set it ourselves.
# expect_passed: whether the critic should let the draft through (True) or reject it (False).
_PROFILE = {
    "tone": "тёплый, интимный",
    "themes": ["ночной город", "одиночество"],
    "avoid": ["вайб", "эксклюзивный", "уникальный"],
}

CRITIQUE_CASES = [
    {
        # The first version of this case ended with the sentence "The new track is
        # already on all platforms". The critic rejected it as too commercial for a
        # warm, intimate tone, and rightly so. The case was wrong, not the critic:
        # a failing eval does not always mean "the model is bad", sometimes the test
        # itself is bad. The sentence was removed.
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
        # No forbidden words, but the tone and the themes are completely off: harder than the first four.
        "id": "off_tone_sales_pitch",
        "profile": _PROFILE,
        "drafts": {"d1": "Покупайте наш мерч со скидкой 50%! Только сегодня, успейте!!!"},
        "expect_passed": False,
    },
]
