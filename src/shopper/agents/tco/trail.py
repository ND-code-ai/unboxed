"""The TCO analyzer's trail entries: the shared ones (`agents/shared/trail.py`), written as it."""

from shopper.agents.shared import trail
from shopper.agents.shared.trail import by_model, counted
from shopper.llm import LlmFailure
from shopper.state import Agent, Source, TrailEntry, TrailKind
from shopper.tools.results import SearchOutcome

__all__ = [
    "by_model",
    "counted",
    "entry",
    "left_out",
    "left_out_of",
    "model_call_failed",
    "searched",
]


def entry(
    kind: TrailKind, summary: str, *, reason: str | None = None, source: Source | None = None
) -> TrailEntry:
    return trail.entry(Agent.TCO, kind, summary, reason=reason, source=source)


def model_call_failed(doing: str, failure: LlmFailure) -> TrailEntry:
    return trail.model_call_failed(Agent.TCO, doing, failure)


def searched(outcome: SearchOutcome) -> TrailEntry:
    return trail.searched(Agent.TCO, outcome)


def left_out(name: str, reason: str) -> TrailEntry:
    """The exclusion of a candidate, by its name, with the reason."""
    named = f'"{name.strip()}"' if name.strip() else "a candidate"
    return entry(TrailKind.EXCLUDED, f"Left out {named}", reason=reason)


def left_out_of(name: str, what: str, reason: str) -> TrailEntry:
    """The exclusion of a value found for a product option, such as a lifespan or a warranty."""
    return entry(TrailKind.EXCLUDED, f'Left out {what} for "{name}"', reason=reason)
