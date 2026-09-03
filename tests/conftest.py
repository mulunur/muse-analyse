import os

import pytest

from app.config import _RUNTIME_OVERRIDES


@pytest.fixture(autouse=True)
def _isolate_runtime_llm_settings():
    """Откатывает runtime-переопределения LLM-настроек после каждого теста.

    ``set_runtime_llm_setting`` пишет как в module-level ``_RUNTIME_OVERRIDES``,
    так и в ``os.environ`` — без отката эти изменения "утекают" в другие тесты
    в рамках одного процесса pytest.
    """
    overrides_before = dict(_RUNTIME_OVERRIDES)
    env_before = dict(os.environ)
    try:
        yield
    finally:
        _RUNTIME_OVERRIDES.clear()
        _RUNTIME_OVERRIDES.update(overrides_before)
        os.environ.clear()
        os.environ.update(env_before)
