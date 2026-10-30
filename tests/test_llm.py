import asyncio
from collections.abc import Callable, Sequence

import httpx
import pytest
from pydantic import BaseModel

from shopper.agents.shared.trail import by_model, entry
from shopper.config import model_ids
from shopper.llm import (
    ChatError,
    ChatRequest,
    ChatTimeoutError,
    Completion,
    LlmFailure,
    complete,
    complete_structured,
    nebius_chat,
)
from shopper.state import Agent, TrailKind


class Parsed(BaseModel):
    product: str
    budget_eur: float | None


def test_structured_completion_returns_an_instance_of_the_schema() -> None:
    chat, requests = fake_chat(['{"product": "frying pan", "budget_eur": 50}'])

    result = asyncio.run(complete_structured(chat, "small", "A pan, 50 euro.", Parsed))

    assert isinstance(result, Completion)
    assert result.value == Parsed(product="frying pan", budget_eur=50.0)
    assert requests[0].json_schema is not None
    assert set(requests[0].json_schema["properties"]) == {"product", "budget_eur"}


def fake_chat(replies: Sequence[str | Exception]):
    """A chat model that returns the given replies in order and records what it was asked."""
    requests: list[ChatRequest] = []
    remaining = list(replies)

    async def chat(request: ChatRequest) -> str:
        requests.append(request)
        reply = remaining.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return chat, requests


def test_complete_returns_the_text_from_the_model_of_the_requested_tier() -> None:
    chat, requests = fake_chat(["A frying pan."])

    result = asyncio.run(complete(chat, "medium", "Name a pan."))

    assert result == Completion(
        tier="medium", model="nvidia/nemotron-3-super-120b-a12b", value="A frying pan."
    )
    assert requests[0].model == "nvidia/nemotron-3-super-120b-a12b"
    assert requests[0].messages[-1] == {"role": "user", "content": "Name a pan."}


def test_the_request_the_completion_and_the_trail_name_the_model_the_environment_chose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "shopper.llm.MODEL_IDS", model_ids({"NEBIUS_MODEL_MEDIUM": "nvidia/other-medium"})
    )
    chat, requests = fake_chat(['{"product": "pan", "budget_eur": null}'])

    result = asyncio.run(complete_structured(chat, "medium", "A pan.", Parsed))

    assert isinstance(result, Completion)
    assert requests[0].model == "nvidia/other-medium"
    written = entry(Agent.BRIEF, TrailKind.FOUND, "Read the results")
    assert by_model(written, result).model == "nvidia/other-medium"


def test_a_timeout_is_returned_as_a_failure_not_raised() -> None:
    chat, _ = fake_chat([ChatTimeoutError("no answer in 60 s")])

    result = asyncio.run(complete(chat, "small", "Name a pan."))

    assert isinstance(result, LlmFailure)
    assert result.kind == "timeout"
    assert result.tier == "small"


def test_a_service_error_is_returned_as_a_failure_with_its_detail() -> None:
    chat, _ = fake_chat([ChatError("429 rate limited")])

    result = asyncio.run(complete(chat, "small", "Name a pan."))

    assert isinstance(result, LlmFailure)
    assert result.kind == "error"
    assert "429" in result.detail


def test_invalid_output_is_retried_once_with_the_validation_error_in_the_prompt() -> None:
    chat, requests = fake_chat(
        ['{"product": "frying pan"}', '{"product": "frying pan", "budget_eur": null}']
    )

    result = asyncio.run(complete_structured(chat, "small", "A pan.", Parsed))

    assert isinstance(result, Completion)
    assert result.value == Parsed(product="frying pan", budget_eur=None)
    assert len(requests) == 2
    assert "budget_eur" in requests[1].messages[-1]["content"]


def test_output_that_is_invalid_twice_is_a_failure_and_is_not_tried_a_third_time() -> None:
    chat, requests = fake_chat(["not json", "still not json", '{"product": "x", "budget_eur": 1}'])

    result = asyncio.run(complete_structured(chat, "small", "A pan.", Parsed))

    assert isinstance(result, LlmFailure)
    assert result.kind == "invalid_output"
    assert len(requests) == 2


def test_json_wrapped_in_a_code_fence_is_accepted() -> None:
    chat, _ = fake_chat(['\n```json\n{"product": "frying pan", "budget_eur": 50}\n```'])

    result = asyncio.run(complete_structured(chat, "small", "A pan.", Parsed))

    assert isinstance(result, Completion)
    assert result.value.product == "frying pan"


def test_a_temperature_is_passed_on_to_the_model_and_left_unset_by_default() -> None:
    chat, requests = fake_chat(['{"product": "pan", "budget_eur": null}', "A frying pan."])

    asyncio.run(complete_structured(chat, "small", "A pan.", Parsed, temperature=0))
    asyncio.run(complete(chat, "small", "Name a pan."))

    assert requests[0].temperature == 0
    assert requests[1].temperature is None


def test_a_call_may_ask_for_little_reasoning_and_reasons_in_full_by_default() -> None:
    chat, requests = fake_chat(['{"product": "pan", "budget_eur": null}', "A frying pan."])

    asyncio.run(complete_structured(chat, "medium", "A pan.", Parsed, low_effort=True))
    asyncio.run(complete(chat, "small", "Name a pan."))

    assert [request.low_effort for request in requests] == [True, False]


def test_a_call_may_have_a_longer_answer_and_more_time_than_the_defaults() -> None:
    chat, requests = fake_chat(['{"product": "pan", "budget_eur": null}', "A frying pan."])

    asyncio.run(
        complete_structured(chat, "medium", "A pan.", Parsed, max_tokens=16000, timeout=150.0)
    )
    asyncio.run(complete(chat, "small", "Name a pan."))

    assert (requests[0].max_tokens, requests[0].timeout) == (16000, 150.0)
    assert (requests[1].max_tokens, requests[1].timeout) == (4000, 60.0)


# --- A call that times out, through the real client (task 1.11) ---
# The `openai` client in `nebius_chat` sends a request that timed out once more
# (docs/architecture/models.md, "The client").

Handler = Callable[[httpx.Request], httpx.Response]
PAN_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 0,
    "model": "nvidia/nemotron-3-super-120b-a12b",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": '{"product": "pan", "budget_eur": null}'},
            "finish_reason": "stop",
        }
    ],
}


def timing_out(times: int) -> tuple[Handler, list[httpx.Request]]:
    """A transport handler that times out on the first `times` requests and then answers."""
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) <= times:
            raise httpx.ReadTimeout("no answer", request=request)
        return httpx.Response(200, json=PAN_REPLY)

    return handle, seen


def call_with(handle: Handler) -> Completion[Parsed] | LlmFailure:
    async def call() -> Completion[Parsed] | LlmFailure:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
            chat = nebius_chat("test-key", http_client=http_client)
            return await complete_structured(chat, "medium", "A pan.", Parsed)

    return asyncio.run(call())


def test_a_call_that_times_out_once_is_sent_again_and_answers() -> None:
    handle, seen = timing_out(1)

    result = call_with(handle)

    assert result == Completion(
        tier="medium",
        model="nvidia/nemotron-3-super-120b-a12b",
        value=Parsed(product="pan", budget_eur=None),
    )
    assert len(seen) == 2


def test_a_call_that_times_out_twice_is_a_timeout_and_is_not_sent_a_third_time() -> None:
    handle, seen = timing_out(2)

    result = call_with(handle)

    assert isinstance(result, LlmFailure)
    assert result.kind == "timeout"
    assert len(seen) == 2
