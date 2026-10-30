"""The web search an agent is given: the cache first, then its call limit, then the service.

The graph makes a fresh view each time a node runs, so the count is per invocation and is not
kept in the graph state. Cache hits do not count (data_sources.md, "Calls per analysis").
"""

from collections.abc import Mapping, Sequence
from datetime import date
from email.utils import parsedate_to_datetime
from types import MappingProxyType
from typing import Any
from urllib.parse import urlparse

from shopper.config import (
    RAW_CONTENT_MAX_CHARACTERS,
    SEARCH_CACHE_MAX_AGE,
    SEARCH_PURPOSE_PARAMETERS,
    TAVILY_FIXED_PARAMETERS,
    SearchPurpose,
)
from shopper.tools.cache import read_cached, search_key, write_cached
from shopper.tools.ledger import tavily_credits
from shopper.tools.results import (
    FailureKind,
    SearchOutcome,
    SearchRequest,
    SearchResult,
    Service,
    StoredResponse,
    WebSearch,
)
from shopper.tools.sources import Sources


def search_request(
    search_query: str, purpose: SearchPurpose, *, follow_up: bool = False
) -> SearchRequest:
    """The search as it is sent: the fixed parameters plus the purpose's own."""
    parameters: Mapping[str, Any] = MappingProxyType(
        {**TAVILY_FIXED_PARAMETERS, **SEARCH_PURPOSE_PARAMETERS[purpose]}
    )
    return SearchRequest(
        search_query=search_query.strip(),
        purpose=purpose,
        parameters=parameters,
        follow_up=follow_up,
    )


def search_view(sources: Sources, max_calls: int) -> WebSearch:
    """A web search that makes at most `max_calls` calls to the service."""
    calls_made = 0

    async def search(
        search_query: str, purpose: SearchPurpose, *, follow_up: bool = False
    ) -> SearchOutcome:
        nonlocal calls_made
        request = search_request(search_query, purpose, follow_up=follow_up)
        key = search_key(request.search_query, request.parameters)
        cached = read_cached(
            sources.cache_folder,
            Service.TAVILY,
            key,
            SEARCH_CACHE_MAX_AGE.get(purpose),
            sources.clock(),
        )
        if cached is not None:
            return search_outcome(request, cached, from_cache=True)
        if calls_made >= max_calls:
            return _failed(request, FailureKind.LIMIT_REACHED)
        calls_made += 1
        fetched = await sources.search(request)
        if isinstance(fetched, FailureKind):
            return _failed(request, fetched)
        # Stamped with the clock, so a fixture's recorded date does not age its cache entry, and
        # the outcome says the same time as a later cache hit does.
        stamped = fetched.model_copy(update={"retrieved_at": sources.clock()})
        write_cached(sources.cache_folder, key, stamped)
        return search_outcome(request, stamped, from_cache=False)

    return search


def search_outcome(
    request: SearchRequest, stored: StoredResponse, *, from_cache: bool
) -> SearchOutcome:
    """The results of a stored response, without those on a domain the purpose excludes; none
    at all is `not_found`.

    The service excludes those domains too; this drops them from a response stored before a
    domain was excluded, so a recorded search answers as a live one does.
    """
    excluded = tuple(request.parameters.get("exclude_domains", ()))
    results = tuple(
        SearchResult(
            url=result["url"],
            title=result["title"],
            content=result["content"],
            raw_content=_cut(result.get("raw_content")),
            published_date=published_date(result.get("published_date")),
        )
        for result in stored.response.get("results", ())
        if not on_domain(result["url"], excluded)
    )
    return SearchOutcome(
        search_query=request.search_query,
        purpose=request.purpose,
        results=results,
        retrieved_at=stored.retrieved_at,
        from_cache=from_cache,
        credits=0 if from_cache else tavily_credits(stored),
        failure=None if results else FailureKind.NOT_FOUND,
    )


def published_date(value: str | None) -> date | None:
    """The day a result was published, from the ISO or the e-mail style date Tavily gives;
    missing when it gives none or one that cannot be read."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        return None


def _cut(raw_content: str | None) -> str | None:
    return raw_content[:RAW_CONTENT_MAX_CHARACTERS] if raw_content else None


def on_domain(url: str, domains: Sequence[str]) -> bool:
    """Whether the URL is on one of the domains or a subdomain of one ("www.bol.com")."""
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def _failed(request: SearchRequest, failure: FailureKind) -> SearchOutcome:
    return SearchOutcome(
        search_query=request.search_query, purpose=request.purpose, failure=failure
    )
