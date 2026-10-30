import os
from collections.abc import Iterator

import langsmith
import pytest

# The tests run on the default models, whatever a developer's .env overrides: the process
# environment wins over it, and empty means the default. Before any test imports `config.py`.
for name in ("NEBIUS_MODEL_SMALL", "NEBIUS_MODEL_MEDIUM", "NEBIUS_MODEL_LARGE"):
    os.environ[name] = ""


@pytest.fixture(autouse=True)
def no_tracing_from_the_environment() -> Iterator[None]:
    """No test is traced because the process environment asks LangSmith for it: tracing is on
    only through the settings `config.py` reads (`tracing.py`)."""
    with langsmith.tracing_context(enabled=False):
        yield
