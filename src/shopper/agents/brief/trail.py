"""The brief agent's trail entries: the shared ones (`agents/shared/trail.py`), written as it."""

from shopper.agents.shared import trail
from shopper.agents.shared.trail import by_model, counted
from shopper.llm import LlmFailure
from shopper.state import Agent, Source, TrailEntry, TrailKind
from shopper.tools.results import SearchOutcome

__all__ = ["by_model", "counted", "entry", "first_read_stands", "model_call_failed", "searched"]


def entry(
    kind: TrailKind, summary: str, *, reason: str | None = None, source: Source | None = None
) -> TrailEntry:
    return trail.entry(Agent.BRIEF, kind, summary, reason=reason, source=source)


def first_read_stands(second: int, first: int) -> TrailEntry:
    return trail.first_read_stands(Agent.BRIEF, "read", "factor", second, first)


def model_call_failed(doing: str, failure: LlmFailure) -> TrailEntry:
    return trail.model_call_failed(Agent.BRIEF, doing, failure)


def searched(outcome: SearchOutcome) -> TrailEntry:
    return trail.searched(Agent.BRIEF, outcome)
