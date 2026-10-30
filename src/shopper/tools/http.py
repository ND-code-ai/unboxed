"""One POST to a service, with the HTTP failures both services share.

Each service names the statuses of its own; the rest is the table in data_sources.md
("Failure kinds"): a 429 is retried once when it asks to wait 5 seconds or less (Firecrawl has a
rule of its own), a 5xx, a lost connection or an unreadable body is `unavailable`. A malformed
request and a rejected key are programmer errors and raise.
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from shopper.config import MAX_RETRY_AFTER_SECONDS
from shopper.tools.results import FailureKind

Sleep = Callable[[float], Awaitable[None]]
# How long to wait before the one retry of a 429, given the Retry-After it stated in seconds (or
# none); missing when it is not retried.
RetryWait = Callable[[float | None], float | None]


def shared_retry_wait(retry_after: float | None) -> float | None:
    """The rule both services share: retry only when asked to wait 5 seconds or less."""
    if retry_after is not None and retry_after <= MAX_RETRY_AFTER_SECONDS:
        return retry_after
    return None


class ServiceRequestError(RuntimeError):
    """The service rejected the request itself as malformed: a bug in the request."""


class RejectedKeyError(RuntimeError):
    """The service rejected the key; the message names the variable, never the value."""


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    api_key: str,
    key_name: str,
    body: Mapping[str, Any],
    timeout: float,
    failures: Mapping[int, FailureKind],
    sleep: Sleep,
    retry_wait: RetryWait = shared_retry_wait,
) -> dict[str, Any] | FailureKind:
    """The JSON body of a successful answer, or the failure; `failures` maps the service's own
    statuses, and `retry_wait` its rule for a 429."""
    for attempt in range(2):
        try:
            response = await client.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=timeout,
            )
        except httpx.TimeoutException:
            return FailureKind.TIMED_OUT
        except httpx.TransportError:
            return FailureKind.UNAVAILABLE
        if response.status_code == 429:
            wait = retry_wait(_retry_after(response))
            if attempt == 0 and wait is not None:
                await sleep(wait)
                continue
            return FailureKind.RATE_LIMITED
        return _answer(response, key_name, failures)
    return FailureKind.RATE_LIMITED


def _answer(
    response: httpx.Response, key_name: str, failures: Mapping[int, FailureKind]
) -> dict[str, Any] | FailureKind:
    status = response.status_code
    if status in failures:
        return failures[status]
    if status >= 500:
        return FailureKind.UNAVAILABLE
    if status == 401:
        raise RejectedKeyError(f"{key_name} was rejected. Check its value in .env.")
    if status != 200:
        raise ServiceRequestError(f"{response.request.url} answered {status}: {response.text}")
    try:
        body = response.json()
    except ValueError:
        return FailureKind.UNAVAILABLE
    return body if isinstance(body, dict) else FailureKind.UNAVAILABLE


def _retry_after(response: httpx.Response) -> float | None:
    """The seconds the service asks to wait, when it says so in seconds."""
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return None


def json_ready(parameters: Mapping[str, Any]) -> dict[str, Any]:
    """The parameters as JSON values: a tuple becomes a list."""
    return {
        name: list(value) if isinstance(value, tuple) else value
        for name, value in parameters.items()
    }
