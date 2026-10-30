import asyncio
import json
import threading
import time
from unittest.mock import MagicMock

import httpx
import langsmith
from pydantic import BaseModel

from fakes import UNUSED_SOURCES, extraction, transport_answers
from shopper.agents.stubs import STUB_AGENTS
from shopper.config import TracingSettings
from shopper.llm import Completion, complete_structured, nebius_chat
from shopper.terminal.cli import run
from shopper.tracing import traced

FRYING_PAN = "I need a new frying pan, budget 50 euro"


def completion(content: str) -> httpx.Response:
    """A chat completion as the Nebius API returns it, with its token counts."""
    return httpx.Response(
        200,
        json={
            "id": "c1",
            "object": "chat.completion",
            "created": 0,
            "model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
        },
    )


def frying_pan_run(settings: TracingSettings | None, client: MagicMock) -> list[httpx.Request]:
    """A --skip-all frying pan run through the real model client, its replies from a transport.

    Returns the requests the model client sent.
    """
    handle, seen = transport_answers(completion(extraction("frying pan", "tuned", "50 euro", 50)))

    async def session() -> int:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
            chat = nebius_chat("test-key", http_client=http_client)
            with traced(settings, FRYING_PAN, client=client) as record_report:
                return await run(
                    FRYING_PAN,
                    chat,
                    UNUSED_SOURCES,
                    skip_all=True,
                    agents=STUB_AGENTS,
                    record_report=record_report,
                )

    assert asyncio.run(session()) == 0
    return seen


def test_with_tracing_off_no_trace_is_sent() -> None:
    client = MagicMock(spec=langsmith.Client)

    # As when the process environment asks LangSmith to trace.
    with langsmith.tracing_context(enabled=True, client=client):
        seen = frying_pan_run(None, client)

    assert client.method_calls == []
    assert "langsmith_extra" not in json.loads(seen[0].content)


TRACING_ON = TracingSettings(api_key="test-key", project="tests")


def posted_runs(client: MagicMock) -> dict[str, dict]:
    """Each run the client was given, by name, with what its update filled in."""
    runs: dict[str, dict] = {}
    by_id: dict[object, dict] = {}
    for method, _, kwargs in client.method_calls:
        if method == "create_run":
            by_id[kwargs["id"]] = runs[kwargs["name"]] = dict(kwargs)
        elif method == "update_run":
            filled = {key: value for key, value in kwargs.items() if value is not None}
            by_id[kwargs["run_id"]].update(filled)
    return runs


def test_with_tracing_on_the_session_is_one_trace_with_a_run_per_node() -> None:
    client = MagicMock(spec=langsmith.Client)

    frying_pan_run(TRACING_ON, client)

    runs = posted_runs(client)
    nodes = {"parse_request", "brief", "interview", "tco", "lca", "second_hand", "assemble_report"}
    assert nodes <= set(runs)
    assert len({run_["trace_id"] for run_ in runs.values()}) == 1
    assert runs["session"]["session_name"] == "tests"


def test_a_terminal_run_waits_until_its_trace_is_handed_over() -> None:
    client = MagicMock(spec=langsmith.Client)
    handed_over = threading.Event()

    def slow_flush() -> None:
        time.sleep(0.2)
        handed_over.set()

    client.flush.side_effect = slow_flush

    frying_pan_run(TRACING_ON, client)

    assert handed_over.is_set()


def test_with_tracing_on_the_session_output_is_the_printed_report() -> None:
    client = MagicMock(spec=langsmith.Client)

    frying_pan_run(TRACING_ON, client)

    report = posted_runs(client)["session"]["outputs"]["report"]
    assert (
        "Lifespan sourced for 0 of 2 options. CO2e to make: not found for 2." in report.splitlines()
    )
    assert "Over 10 years: Carbon steel pan costs €60 less than Non-stick pan." in report


def test_with_tracing_on_a_model_call_is_a_child_run_of_its_node_with_its_request() -> None:
    client = MagicMock(spec=langsmith.Client)

    frying_pan_run(TRACING_ON, client)

    runs = posted_runs(client)
    call = runs["nebius_chat · Extraction"]
    assert call["parent_run_id"] == runs["parse_request"]["id"]
    metadata = call["extra"]["metadata"]
    assert metadata["tier"] == "small"
    assert call["tags"] == ["small", "full-reasoning"]
    assert metadata["ls_model_name"] == "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    assert {"messages", "max_tokens", "timeout", "temperature"} <= set(call["inputs"])
    assert call["outputs"]["usage_metadata"]["total_tokens"] == 150


class Pan(BaseModel):
    name: str


def test_a_low_effort_call_sends_and_traces_the_reasoning_settings() -> None:
    client = MagicMock(spec=langsmith.Client)
    handle, seen = transport_answers(completion('{"name": "carbon steel pan"}'))

    async def low_effort_call() -> object:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
            chat = nebius_chat("test-key", http_client=http_client)
            with traced(TRACING_ON, "a pan", client=client):
                return await complete_structured(chat, "medium", "A pan.", Pan, low_effort=True)

    assert isinstance(asyncio.run(low_effort_call()), Completion)
    low_effort = {"enable_thinking": True, "low_effort": True}
    assert json.loads(seen[0].content)["chat_template_kwargs"] == low_effort
    call = posted_runs(client)["nebius_chat · Pan"]
    assert call["inputs"]["extra_body"] == {"chat_template_kwargs": low_effort}
    assert call["extra"]["metadata"]["tier"] == "medium"
    assert call["tags"] == ["medium", "little-reasoning"]
