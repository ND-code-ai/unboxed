"""Firecrawl over plain HTTP: one page per request, markdown and raw HTML, no JSON extraction
(data_sources.md, "Firecrawl")."""

import asyncio
from types import MappingProxyType

import httpx

from shopper.config import (
    FIRECRAWL_KEY_NAME,
    FIRECRAWL_MAX_RETRY_AFTER_SECONDS,
    FIRECRAWL_RETRY_PAUSE_SECONDS,
    FIRECRAWL_SCRAPE_URL,
    FIRECRAWL_TIMEOUT_SECONDS,
)
from shopper.tools.http import Sleep, json_ready, post_json
from shopper.tools.results import (
    Clock,
    FailureKind,
    PageRequest,
    PageService,
    Service,
    StoredResponse,
)

FIRECRAWL_FAILURES = MappingProxyType(
    {
        402: FailureKind.CREDITS_EXHAUSTED,
        403: FailureKind.BLOCKED,
        404: FailureKind.NOT_FOUND,
        408: FailureKind.TIMED_OUT,
    }
)


def firecrawl_retry_wait(retry_after: float | None) -> float:
    """A 429 is always retried once: after its Retry-After, up to the longest wait, or after the
    pause when it states none (docs/findings/task_1.12.md, "Decided", item 6)."""
    if retry_after is None:
        return FIRECRAWL_RETRY_PAUSE_SECONDS
    return min(retry_after, FIRECRAWL_MAX_RETRY_AFTER_SECONDS)


def firecrawl_service(
    client: httpx.AsyncClient,
    api_key: str,
    clock: Clock,
    sleep: Sleep = asyncio.sleep,
) -> PageService:
    """The live page service."""

    async def fetch(request: PageRequest) -> StoredResponse | FailureKind:
        parameters = json_ready(request.parameters)
        body = await post_json(
            client,
            FIRECRAWL_SCRAPE_URL,
            api_key=api_key,
            key_name=FIRECRAWL_KEY_NAME,
            body={"url": request.url, **parameters},
            timeout=FIRECRAWL_TIMEOUT_SECONDS,
            failures=FIRECRAWL_FAILURES,
            sleep=sleep,
            retry_wait=firecrawl_retry_wait,
        )
        if isinstance(body, FailureKind):
            return body
        if body.get("success") is not True or not isinstance(body.get("data"), dict):
            return FailureKind.UNAVAILABLE
        return StoredResponse(
            service=Service.FIRECRAWL,
            request={"url": request.url, "parameters": parameters},
            retrieved_at=clock(),
            response=body,
        )

    return fetch
