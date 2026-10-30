"""The Firecrawl client at the HTTP layer, with an injected transport: one test per failure kind."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from fakes import Clock, TransportHandler, transport_answers
from shopper.config import FIRECRAWL_MAX_RETRY_AFTER_SECONDS, FIRECRAWL_RETRY_PAUSE_SECONDS
from shopper.tools.firecrawl import firecrawl_service
from shopper.tools.http import RejectedKeyError, ServiceRequestError
from shopper.tools.product_page import page_request
from shopper.tools.results import FailureKind, Service, StoredResponse

NOON = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
URL = "https://example.org/shop/kettle"
BODY = {
    "success": True,
    "data": {
        "markdown": "# Kettle",
        "rawHtml": "<html></html>",
        "metadata": {"statusCode": 200, "creditsUsed": 1},
    },
}

Handler = TransportHandler


def fetched(handler: Handler) -> tuple[StoredResponse | FailureKind, list[float]]:
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    async def run() -> StoredResponse | FailureKind:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = firecrawl_service(client, "fc-test", Clock(NOON), sleep)
            return await service(page_request(URL))

    return asyncio.run(run()), waits


def test_a_fetch_asks_for_markdown_and_raw_html_and_stores_the_response() -> None:
    handler, seen = transport_answers(httpx.Response(200, json=BODY))

    stored, _ = fetched(handler)

    (sent,) = seen
    assert sent.url == "https://api.firecrawl.dev/v2/scrape"
    assert sent.headers["Authorization"] == "Bearer fc-test"
    assert json.loads(sent.content) == {"url": URL, "formats": ["markdown", "rawHtml"]}
    assert isinstance(stored, StoredResponse)
    assert stored.service is Service.FIRECRAWL
    assert stored.request["url"] == URL
    assert stored.retrieved_at == NOON
    assert stored.response["data"]["markdown"] == "# Kettle"


@pytest.mark.parametrize(
    ("status", "failure"),
    [
        (403, FailureKind.BLOCKED),
        (404, FailureKind.NOT_FOUND),
        (408, FailureKind.TIMED_OUT),
        (402, FailureKind.CREDITS_EXHAUSTED),
        (500, FailureKind.UNAVAILABLE),
        (502, FailureKind.UNAVAILABLE),
    ],
)
def test_each_failing_status_has_its_failure_kind(status: int, failure: FailureKind) -> None:
    handler, _ = transport_answers(httpx.Response(status, json={"success": False, "error": "x"}))

    assert fetched(handler)[0] is failure


def test_a_429_with_a_short_retry_after_is_retried_once_then_rate_limited() -> None:
    handler, seen = transport_answers(
        httpx.Response(429, headers={"Retry-After": "5"}),
        httpx.Response(429, headers={"Retry-After": "5"}),
    )

    result, waits = fetched(handler)

    assert result is FailureKind.RATE_LIMITED
    assert waits == [5.0]
    assert len(seen) == 2


def test_a_429_with_no_retry_after_is_retried_once_after_the_pause() -> None:
    handler, seen = transport_answers(httpx.Response(429), httpx.Response(200, json=BODY))

    result, waits = fetched(handler)

    assert isinstance(result, StoredResponse)
    assert waits == [FIRECRAWL_RETRY_PAUSE_SECONDS]
    assert len(seen) == 2


def test_a_429_asking_a_longer_wait_than_other_services_is_still_retried_after_it() -> None:
    # A run of reads met Firecrawl's limit in task 1.12; the page is worth the wait.
    handler, _ = transport_answers(
        httpx.Response(429, headers={"Retry-After": "20"}), httpx.Response(200, json=BODY)
    )

    result, waits = fetched(handler)

    assert isinstance(result, StoredResponse)
    assert waits == [20.0]


def test_a_429_asking_more_than_the_longest_wait_waits_only_that_long() -> None:
    handler, _ = transport_answers(
        httpx.Response(429, headers={"Retry-After": "600"}),
        httpx.Response(429, headers={"Retry-After": "600"}),
    )

    result, waits = fetched(handler)

    assert result is FailureKind.RATE_LIMITED
    assert waits == [FIRECRAWL_MAX_RETRY_AFTER_SECONDS]


def test_no_answer_in_time_is_timed_out() -> None:
    handler, _ = transport_answers(httpx.ReadTimeout("slow"))

    assert fetched(handler)[0] is FailureKind.TIMED_OUT


@pytest.mark.parametrize(
    "response",
    [
        httpx.ConnectError("refused"),
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json={"success": False, "error": "failed"}),
    ],
)
def test_a_lost_connection_or_an_unreadable_body_is_unavailable(
    response: httpx.Response | Exception,
) -> None:
    handler, _ = transport_answers(response)

    assert fetched(handler)[0] is FailureKind.UNAVAILABLE


def test_a_malformed_request_is_a_programmer_error() -> None:
    handler, _ = transport_answers(
        httpx.Response(400, json={"success": False, "error": "Invalid url"})
    )

    with pytest.raises(ServiceRequestError, match="Invalid url"):
        fetched(handler)


def test_a_rejected_key_raises_naming_the_variable() -> None:
    handler, _ = transport_answers(
        httpx.Response(401, json={"success": False, "error": "Unauthorized"})
    )

    with pytest.raises(RejectedKeyError, match="FIRECRAWL_API_KEY"):
        fetched(handler)
