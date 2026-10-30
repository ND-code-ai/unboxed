"""The daily ceiling on Tavily credits, kept in a small ledger file in the cache folder.

Past the limit the search returns `daily_limit_reached` without calling Tavily
(data_sources.md, "Calls per analysis").
"""

import json
from pathlib import Path

from shopper.tools.results import (
    Clock,
    FailureKind,
    SearchRequest,
    SearchService,
    StoredResponse,
)

# A basic search costs one credit (data_sources.md, "Tavily").
RESERVED_CREDITS = 1


def tavily_credits(stored: StoredResponse) -> int:
    """The credits Tavily reported for the call."""
    return int(stored.response.get("usage", {}).get("credits", 0))


def with_daily_ceiling(
    service: SearchService, ledger: Path, limit: int, clock: Clock
) -> SearchService:
    """The same service, refused once the credits reported today reach `limit`."""

    async def search(request: SearchRequest) -> StoredResponse | FailureKind:
        day = _day(clock)
        if _spent(ledger, day) >= limit:
            return FailureKind.DAILY_LIMIT_REACHED
        # One credit is reserved before the call, so searches running at the same time cannot
        # all pass the check; it is settled with what Tavily reports.
        _add(ledger, day, RESERVED_CREDITS)
        fetched = await service(request)
        reported = tavily_credits(fetched) if isinstance(fetched, StoredResponse) else 0
        _add(ledger, day, reported - RESERVED_CREDITS)
        return fetched

    return search


def _day(clock: Clock) -> str:
    return clock().date().isoformat()


def _read(ledger: Path) -> dict[str, int]:
    if not ledger.is_file():
        return {}
    return json.loads(ledger.read_text(encoding="utf-8"))


def _spent(ledger: Path, day: str) -> int:
    return _read(ledger).get(day, 0)


def _add(ledger: Path, day: str, credits: int) -> None:
    """Only today's total is kept; earlier days are dropped."""
    ledger.parent.mkdir(parents=True, exist_ok=True)
    total = _spent(ledger, day) + credits
    ledger.write_text(json.dumps({day: total}), encoding="utf-8")
