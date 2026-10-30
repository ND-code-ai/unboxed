"""Tavily search over plain HTTP: one POST to /search, no SDK (data_sources.md, "Tavily")."""

import asyncio
from types import MappingProxyType

import httpx

from shopper.config import TAVILY_KEY_NAME, TAVILY_SEARCH_URL, TAVILY_TIMEOUT_SECONDS
from shopper.tools.http import Sleep, json_ready, post_json
from shopper.tools.results import (
    Clock,
    FailureKind,
    SearchRequest,
    SearchService,
    Service,
    StoredResponse,
)

# 432: the plan's limit; 433: the pay-as-you-go limit, which stays off.
TAVILY_FAILURES = MappingProxyType(
    {432: FailureKind.CREDITS_EXHAUSTED, 433: FailureKind.CREDITS_EXHAUSTED}
)


def tavily_service(
    client: httpx.AsyncClient,
    api_key: str,
    clock: Clock,
    sleep: Sleep = asyncio.sleep,
) -> SearchService:
    """The live search service."""

    async def search(request: SearchRequest) -> StoredResponse | FailureKind:
        parameters = json_ready(request.parameters)
        body = await post_json(
            client,
            TAVILY_SEARCH_URL,
            api_key=api_key,
            key_name=TAVILY_KEY_NAME,
            body={"query": request.search_query, **parameters},
            timeout=TAVILY_TIMEOUT_SECONDS,
            failures=TAVILY_FAILURES,
            sleep=sleep,
        )
        if isinstance(body, FailureKind):
            return body
        if not isinstance(body.get("results"), list):
            return FailureKind.UNAVAILABLE
        return StoredResponse(
            service=Service.TAVILY,
            request={
                "search_query": request.search_query,
                "purpose": request.purpose,
                "parameters": parameters,
            },
            retrieved_at=clock(),
            response=body,
        )

    return search
