"""The Tavily client at the HTTP layer, with an injected transport: one test per failure kind."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from fakes import Clock, TransportHandler, transport_answers
from shopper.config import SearchPurpose
from shopper.tools.http import RejectedKeyError, ServiceRequestError
from shopper.tools.results import FailureKind, SearchRequest, Service, StoredResponse
from shopper.tools.search import search_request
from shopper.tools.tavily import tavily_service

NOON = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
REQUEST = search_request("frying pan buying guide what to look for", SearchPurpose.CATEGORY)
BODY = {
    "query": "frying pan buying guide what to look for",
    "results": [{"url": "https://example.org/a", "title": "A", "content": "Text", "score": 0.5}],
    "usage": {"credits": 1},
}

Handler = TransportHandler


def searched(
    handler: Handler, request: SearchRequest = REQUEST
) -> tuple[StoredResponse | FailureKind, list[float]]:
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    async def run() -> StoredResponse | FailureKind:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = tavily_service(client, "tvly-test", Clock(NOON), sleep)
            return await service(request)

    return asyncio.run(run()), waits


def test_a_search_posts_the_query_and_parameters_and_stores_the_response() -> None:
    handler, seen = transport_answers(httpx.Response(200, json=BODY))

    stored, _ = searched(handler)

    (sent,) = seen
    body = json.loads(sent.content)
    assert sent.url == "https://api.tavily.com/search"
    assert sent.headers["Authorization"] == "Bearer tvly-test"
    assert body["query"] == "frying pan buying guide what to look for"
    assert body["search_depth"] == "basic"
    assert body["include_answer"] is False
    assert "linkedin.com" in body["exclude_domains"]
    assert isinstance(stored, StoredResponse)
    assert stored.service is Service.TAVILY
    assert stored.request["search_query"] == "frying pan buying guide what to look for"
    assert stored.request["purpose"] == "category"
    assert stored.retrieved_at == NOON
    assert stored.response["results"][0]["url"] == "https://example.org/a"


def test_a_429_with_a_short_retry_after_is_retried_once() -> None:
    handler, seen = transport_answers(
        httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(200, json=BODY)
    )

    stored, waits = searched(handler)

    assert isinstance(stored, StoredResponse)
    assert waits == [2.0]
    assert len(seen) == 2


def test_a_second_429_is_rate_limited() -> None:
    handler, seen = transport_answers(
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.Response(429, headers={"Retry-After": "1"}),
    )

    assert searched(handler)[0] is FailureKind.RATE_LIMITED
    assert len(seen) == 2


@pytest.mark.parametrize("headers", [{"Retry-After": "30"}, {}, {"Retry-After": "soon"}])
def test_a_429_asking_to_wait_long_or_not_saying_is_rate_limited_at_once(
    headers: dict[str, str],
) -> None:
    handler, seen = transport_answers(httpx.Response(429, headers=headers))

    result, waits = searched(handler)

    assert result is FailureKind.RATE_LIMITED
    assert waits == []
    assert len(seen) == 1


def test_no_answer_in_time_is_timed_out_with_no_retry() -> None:
    handler, seen = transport_answers(httpx.ReadTimeout("slow"))

    assert searched(handler)[0] is FailureKind.TIMED_OUT
    assert len(seen) == 1


@pytest.mark.parametrize("status", [432, 433])
def test_a_plan_or_spending_limit_is_credits_exhausted(status: int) -> None:
    handler, _ = transport_answers(httpx.Response(status, json={"detail": {"error": "limit"}}))

    assert searched(handler)[0] is FailureKind.CREDITS_EXHAUSTED


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(503),
        httpx.ConnectError("refused"),
        httpx.Response(200, content=b"<html>not json</html>"),
        httpx.Response(200, json={"no": "results"}),
    ],
)
def test_a_server_error_a_lost_connection_or_an_unreadable_body_is_unavailable(
    response: httpx.Response | Exception,
) -> None:
    handler, _ = transport_answers(response)

    assert searched(handler)[0] is FailureKind.UNAVAILABLE


@pytest.mark.parametrize("status", [400, 422])
def test_a_malformed_request_is_a_programmer_error(status: int) -> None:
    handler, _ = transport_answers(
        httpx.Response(status, json={"detail": {"error": "bad country"}})
    )

    with pytest.raises(ServiceRequestError, match="bad country"):
        searched(handler)


def test_a_rejected_key_raises_naming_the_variable() -> None:
    handler, _ = transport_answers(httpx.Response(401, json={"detail": {"error": "Unauthorized"}}))

    with pytest.raises(RejectedKeyError, match="TAVILY_API_KEY"):
        searched(handler)
