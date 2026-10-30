"""The fixture twins: recorded responses from tests/fixtures/ in place of the services.

A fixture is a stored response with a readable file name, matched on the search query and
purpose, or on the URL, never on a hash, so changing a parameter in config.py does not orphan
it. A miss is a programmer error, except for a search query a model wrote: that one is answered
when it was recorded and is `not_recorded` otherwise. When the app runs on the fixtures, a page is
lenient the same way: the live model can pick a candidate no recording read.
"""

from pathlib import Path

from shopper.tools.cache import normalised_query
from shopper.tools.results import (
    FailureKind,
    PageRequest,
    PageService,
    SearchRequest,
    SearchService,
    Service,
    StoredResponse,
)


class FixtureMissingError(LookupError):
    """No fixture was recorded for this request."""


def fixture_search_service(folder: Path) -> SearchService:
    async def search(request: SearchRequest) -> StoredResponse | FailureKind:
        wanted = (normalised_query(request.search_query), request.purpose)
        for stored in _fixtures(folder, Service.TAVILY):
            found = (normalised_query(stored.request["search_query"]), stored.request["purpose"])
            if found == wanted:
                return stored
        if request.follow_up:
            return FailureKind.NOT_RECORDED
        raise FixtureMissingError(
            f"No fixture for the search query {request.search_query!r} ({request.purpose})"
        )

    return search


def fixture_page_service(folder: Path, *, lenient: bool = False) -> PageService:
    """A page no fixture holds raises, or with `lenient` is `not_recorded`."""

    async def fetch(request: PageRequest) -> StoredResponse | FailureKind:
        for stored in _fixtures(folder, Service.FIRECRAWL):
            if stored.request["url"] == request.url:
                return stored
        if lenient:
            return FailureKind.NOT_RECORDED
        raise FixtureMissingError(f"No fixture for the page {request.url!r}")

    return fetch


def _fixtures(folder: Path, service: Service) -> tuple[StoredResponse, ...]:
    return tuple(
        StoredResponse.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted((folder / service).glob("*.json"))
    )
