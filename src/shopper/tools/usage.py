"""Counting the credits a tool's calls reported, for one log line per agent per analysis.

Credits are logged, never put on the trail, which is shown to the user. Rules:
docs/architecture/data_sources.md ("Rules for every source").
"""

from collections.abc import Awaitable, Callable
from typing import Protocol

# The logger of the one line per agent per analysis with the credits its tool used.
USAGE_LOGGER = "shopper.usage"


class Credited(Protocol):
    """What a tool returns: the credits the service reported for the call, none for a cache hit."""

    @property
    def credits(self) -> int: ...


def metered[**P, R: Credited](
    tool: Callable[P, Awaitable[R]],
) -> tuple[Callable[P, Awaitable[R]], Callable[[], int]]:
    """The same tool, and a function that gives the credits its calls have reported so far."""
    reported: list[int] = []

    async def counting(*args: P.args, **kwargs: P.kwargs) -> R:
        result = await tool(*args, **kwargs)
        reported.append(result.credits)
        return result

    return counting, lambda: sum(reported)
