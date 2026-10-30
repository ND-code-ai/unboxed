"""The daily credit ceiling, through the web search, against recorded responses."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fakes import Clock, counted, failing_page_service
from shopper.config import SearchPurpose
from shopper.tools.fixtures import fixture_search_service
from shopper.tools.ledger import with_daily_ceiling
from shopper.tools.results import (
    FailureKind,
    SearchOutcome,
    SearchRequest,
    SearchService,
    StoredResponse,
)
from shopper.tools.search import search_view
from shopper.tools.sources import Sources

FIXTURES = Path(__file__).parent.parent / "fixtures"
QUERIES = (
    "frying pan buying guide what to look for",
    "kettle buying guide what to look for",
    "drill buying guide what to look for",
)
NOON = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def searched(sources: Sources, *queries: str) -> list[SearchOutcome]:
    view = search_view(sources, max_calls=10)

    async def run() -> list[SearchOutcome]:
        return [await view(query, SearchPurpose.CATEGORY) for query in queries]

    return asyncio.run(run())


def answering_later(service: SearchService) -> SearchService:
    """The same service, giving way to other searches before it answers, as a network call does."""

    async def search(request: SearchRequest) -> StoredResponse | FailureKind:
        await asyncio.sleep(0)
        return await service(request)

    return search


def ceiling_sources(tmp_path: Path, limit: int, clock: Clock) -> tuple[Sources, list[object]]:
    service, calls = counted(answering_later(fixture_search_service(FIXTURES)))
    limited: SearchService = with_daily_ceiling(service, tmp_path / "ledger.json", limit, clock)
    sources = Sources(
        search=limited,
        fetch_page=failing_page_service(),
        cache_folder=tmp_path / "cache",
        clock=clock,
    )
    return sources, calls


def test_past_the_daily_limit_the_search_returns_daily_limit_reached_without_calling(
    tmp_path: Path,
) -> None:
    sources, calls = ceiling_sources(tmp_path, 2, Clock(NOON))

    outcomes = searched(sources, *QUERIES)

    assert [outcome.failure for outcome in outcomes] == [
        None,
        None,
        FailureKind.DAILY_LIMIT_REACHED,
    ]
    assert len(calls) == 2


def test_the_ledger_outlives_the_view_and_the_process(tmp_path: Path) -> None:
    clock = Clock(NOON)
    first, _ = ceiling_sources(tmp_path, 2, clock)
    searched(first, *QUERIES[:2])
    later, calls = ceiling_sources(tmp_path, 2, clock)

    (outcome,) = searched(later, QUERIES[2])

    assert outcome.failure is FailureKind.DAILY_LIMIT_REACHED
    assert calls == []


def test_the_next_day_starts_from_zero(tmp_path: Path) -> None:
    clock = Clock(NOON)
    sources, _ = ceiling_sources(tmp_path, 2, clock)
    searched(sources, *QUERIES[:2])
    clock.now = NOON + timedelta(days=1)

    (outcome,) = searched(sources, QUERIES[2])

    assert outcome.failure is None


def test_cache_hits_spend_nothing_from_the_daily_limit(tmp_path: Path) -> None:
    sources, _ = ceiling_sources(tmp_path, 1, Clock(NOON))

    outcomes = searched(sources, QUERIES[0], QUERIES[0], QUERIES[0])

    assert [outcome.failure for outcome in outcomes] == [None, None, None]


def test_searches_running_at_the_same_time_cannot_overshoot_the_limit(tmp_path: Path) -> None:
    sources, calls = ceiling_sources(tmp_path, 2, Clock(NOON))
    view = search_view(sources, max_calls=10)

    async def run() -> list[SearchOutcome]:
        return list(
            await asyncio.gather(*(view(query, SearchPurpose.CATEGORY) for query in QUERIES))
        )

    outcomes = asyncio.run(run())

    assert sorted(str(outcome.failure) for outcome in outcomes) == [
        "None",
        "None",
        "daily_limit_reached",
    ]
    assert len(calls) == 2
