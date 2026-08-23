from pathlib import Path
from pprint import pprint

import pytest

from app.audio_analysis import ESSENTIA_AVAILABLE, analyze_audio


TRACK_PATH = Path(__file__).parent / "assets" / "The Range, Jim-E Stack - With You.mp3"


@pytest.mark.skipif(
    not ESSENTIA_AVAILABLE,
    reason="Для интеграционного теста нужна установленная Essentia",
)
def test_analyze_first_track_and_print_result():
    result = analyze_audio(TRACK_PATH)

    pprint(result)

    assert result["file"] == TRACK_PATH.name
    assert result["duration_sec"] > 0
    assert result["sample_rate"] == 44100
    assert 0 <= result["energy"] <= 1
    assert {"rhythm", "tonal", "dynamics", "spectral"} <= result.keys()