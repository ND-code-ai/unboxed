"""The trail entries every research loop writes: who wrote them, which model when one did, and
the entry for a search. Each agent binds them to its own name (`agents/<agent>/trail.py`)."""

from shopper.llm import Completion, LlmFailure
from shopper.state import Agent, Source, TrailEntry, TrailKind
from shopper.tools.results import FailureKind, SearchOutcome


def entry(
    agent: Agent,
    kind: TrailKind,
    summary: str,
    *,
    reason: str | None = None,
    source: Source | None = None,
) -> TrailEntry:
    return TrailEntry(agent=agent, kind=kind, summary=summary, reason=reason, source=source)


def by_model[T](written: TrailEntry, completion: Completion[T] | LlmFailure) -> TrailEntry:
    return written.model_copy(update={"model_tier": completion.tier, "model": completion.model})


def model_call_failed(agent: Agent, doing: str, failure: LlmFailure) -> TrailEntry:
    failed = entry(
        agent,
        TrailKind.EXCLUDED,
        f"Could not {doing}",
        reason=f"the model call failed ({failure.kind})",
    )
    return by_model(failed, failure)


def searched(agent: Agent, outcome: SearchOutcome) -> TrailEntry:
    """A search's trail entry: its search query, how many results, and whether from the cache."""
    if outcome.failure not in (None, FailureKind.NOT_FOUND):
        summary = f'Could not search for "{outcome.search_query}"'
        return entry(agent, TrailKind.EXCLUDED, summary, reason=str(outcome.failure))
    where = ", from the cache" if outcome.from_cache else ""
    found = counted(len(outcome.results), "result")
    return entry(agent, TrailKind.FOUND, f'Searched "{outcome.search_query}": {found}{where}')


def first_read_stands(agent: Agent, read: str, noun: str, second: int, first: int) -> TrailEntry:
    """The entry for a second read that kept fewer cited items than the first, so the first
    stands (docs/architecture/data_sources.md, "Research rules")."""
    return entry(
        agent,
        TrailKind.DECIDED,
        f"The first {read} stands",
        reason=f"the second {read} kept {counted(second, noun)}, the first {first}",
    )


def counted(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
