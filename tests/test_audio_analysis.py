import numpy as np

from app.audio_analysis import _coerce_to_float
from app.config import get_runtime_llm_setting, set_runtime_llm_setting


def test_coerce_to_float_prefers_scalar_from_tuple():
    result = _coerce_to_float((np.array([1.0, 2.0]), 3.5))
    assert result == 3.5


def test_coerce_to_float_averages_array_values():
    result = _coerce_to_float(np.array([1.0, 3.0, 5.0]))
    assert result == 3.0


def test_runtime_llm_setting_can_be_overridden():
    set_runtime_llm_setting("LLM_PROVIDER", "claude")
    set_runtime_llm_setting("ANTHROPIC_API_KEY", "test-key")

    assert get_runtime_llm_setting("LLM_PROVIDER") == "claude"
    assert get_runtime_llm_setting("ANTHROPIC_API_KEY") == "test-key"
