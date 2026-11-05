import os

import pytest

from app.config import _RUNTIME_OVERRIDES


@pytest.fixture(autouse=True)
def _isolate_runtime_llm_settings():
    """Rolls back runtime overrides of the LLM settings after every test.

    ``set_runtime_llm_setting`` writes both to the module-level ``_RUNTIME_OVERRIDES``
    and to ``os.environ``. Without a rollback these changes "leak" into other tests
    running in the same pytest process.
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
