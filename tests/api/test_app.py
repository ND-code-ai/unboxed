"""The session API, through HTTP requests to the app, on a fake model, the fixture sources and the
stub agents, with its sessions saved in a SQLite file."""

import asyncio
import json
import logging
import threading
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple, get_args
from unittest.mock import MagicMock

import httpx
import langsmith
import pytest
from fastapi import FastAPI
from langgraph.checkpoint.base import BaseCheckpointSaver

from fakes import Clock, extraction, fake_chat, typing
from reply_readings import (
    INDUCTION_WEEKLY,
    NOTHING_NAMED,
    READ_INDUCTION_WEEKLY,
    READ_NOTHING_NAMED,
    REPLY_AGENTS,
    STUB_HOB_NUMBER,
    reading,
    said,
)
from shopper import wording
from shopper.agents.bundle import AgentBundle, BriefOutput, TcoOutput
from shopper.agents.stubs import HOB_FACTOR, STUB_AGENTS, stub_brief
from shopper.api.app import create_app
from shopper.api.checkpointer import saved_sessions
from shopper.api.models import RefusalCode, RunErrorCode, UnexpectedCode
from shopper.config import TracingSettings
from shopper.llm import ChatError, ChatModel
from shopper.state import ProductOption, Report, Request, Source, SourceKind, StatedBy
from shopper.terminal.cli import run
from shopper.terminal.report_text import printed_report
from shopper.tools.brief_store import BriefStore
from shopper.tools.results import Clock as ClockOfTheApp
from shopper.tools.results import WebSearch, utc_now
from shopper.tools.sources import fixture_sources
from shopper.tracing import UNTRACED, Tracer, tracer

FIXTURES = Path(__file__).parent.parent / "fixtures"
FRYING_PAN = "I need a new frying pan, budget 50 euro"
FRYING_PAN_REPLY = extraction("frying pan", "tuned", "50 euro", 50)
KEEP_ALIVE = ": keep-alive"
TRACING_ON = TracingSettings(api_key="test-key", project="tests")
Event = tuple[str, dict[str, Any]]


class Api(NamedTuple):
    app: FastAPI
    client: httpx.AsyncClient


def served[T](
    tmp_path: Path,
    scenario: Callable[[Api], Awaitable[T]],
    *replies: str | Exception,
    agents: AgentBundle = STUB_AGENTS,
    keep_alive_seconds: float = 60.0,
    database: Callable[[Path], AbstractAsyncContextManager[BaseCheckpointSaver]] = saved_sessions,
    origins: tuple[str, ...] = (),
    trace: Tracer = UNTRACED,
    clock: ClockOfTheApp = utc_now,
    trusted_proxy_hops: int = 0,
    sessions_per_hour: int = 30,
    sessions_per_day: int = 100,
    tracing: bool = False,
) -> T:
    """Run the scenario against the app, with its lifespan run here: httpx's ASGI transport does
    not run it."""

    async def run() -> T:
        chat, _ = fake_chat(replies)
        app = create_app(
            chat,
            fixture_sources(FIXTURES, tmp_path / "cache"),
            database(tmp_path / "sessions.sqlite"),
            agents=agents,
            keep_alive_seconds=keep_alive_seconds,
            origins=origins,
            trace=trace,
            clock=clock,
            trusted_proxy_hops=trusted_proxy_hops,
            sessions_per_hour=sessions_per_hour,
            sessions_per_day=sessions_per_day,
            tracing=tracing,
        )
        transport = httpx.ASGITransport(app=app)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        ):
            return await scenario(Api(app, client))

    return asyncio.run(run())


def events(stream: str) -> list[Event]:
    """The events of a Server-Sent Events stream, each its name and its data; comments left out."""
    parsed: list[Event] = []
    for block in stream.split("\n\n"):
        lines = block.splitlines()
        fields = dict(line.split(": ", 1) for line in lines if line.startswith(("event", "data")))
        if fields:
            parsed.append((fields["event"], json.loads(fields["data"])))
    return parsed


def names(streamed: list[Event]) -> list[str]:
    return [name for name, _ in streamed]


def progress(streamed: list[Event]) -> list[tuple[str, str, str]]:
    return [
        (data["agent"], data["status"], data["message"])
        for name, data in streamed
        if name == "progress"
    ]


def data_of(streamed: list[Event], name: str) -> dict[str, Any]:
    (data,) = [data for event, data in streamed if event == name]
    return data


def plain(line: dict[str, Any] | None) -> str | None:
    """A line as the API sends it, as plain text: its parts' words, without its controls."""
    if line is None:
        return None
    return "".join(part["text"] for part in line["parts"] if part["kind"] != "control")


def plains(lines: list[dict[str, Any]]) -> list[str | None]:
    return [plain(line) for line in lines]


async def start(api: Api, text: str = FRYING_PAN) -> httpx.Response:
    return await api.client.post("/sessions", json={"input": text})


async def started(api: Api) -> dict[str, Any]:
    """A frying pan session at its pause, as its start streamed it."""
    return (await started_with_lines(api))["session"]


async def started_with_lines(api: Api, text: str = FRYING_PAN) -> dict[str, Any]:
    """The `session` event of a session's start: the session and its lines."""
    return data_of(events((await start(api, text)).text), "session")


async def answer(
    api: Api, session_id: str, answers: list[dict[str, str]], reply: str | None = None
) -> httpx.Response:
    body: dict[str, Any] = {"answers": answers}
    if reply is not None:
        body["reply"] = reply
    return await api.client.post(f"/sessions/{session_id}/answers", json=body)


async def read(api: Api, session_id: str) -> httpx.Response:
    return await api.client.get(f"/sessions/{session_id}")


# --- Starting a session ---


def test_starting_a_session_streams_its_id_progress_what_was_understood_and_the_questions(
    tmp_path: Path,
) -> None:
    response = served(tmp_path, start, FRYING_PAN_REPLY)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    streamed = events(response.text)
    assert names(streamed) == [
        "session_started",
        "progress",
        "understood",
        "progress",
        "progress",
        "session",
    ]
    (_, started), _, (_, understood), *_, (_, session) = streamed
    assert session["session"]["session_id"] == started["session_id"]
    assert understood["request"]["category"] == "frying pan"
    assert progress(streamed) == [
        ("supervisor", "started", "Reading your request..."),
        ("brief", "started", "Researching what to ask about..."),
        ("brief", "finished", "Finished researching what to ask about."),
    ]
    assert [question["text"] for question in session["session"]["questions"]] == [
        "Which hob do you cook on?",
        "How often will you use it?",
    ]
    assert session["session"]["report"] is None


def test_each_event_names_itself_in_its_data_too(tmp_path: Path) -> None:
    async def scenario(api: Api) -> list[Event]:
        session = await started(api)
        return events((await answer(api, session["session_id"], [])).text)

    streamed = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert [data["event"] for _, data in streamed] == names(streamed)


def test_a_request_that_does_not_run_streams_the_session_with_its_report(tmp_path: Path) -> None:
    async def scenario(api: Api) -> tuple[list[Event], Any]:
        streamed = events((await start(api, "a pizza")).text)
        session_id = data_of(streamed, "session_started")["session_id"]
        return streamed, (await read(api, session_id)).json()

    streamed, saved = served(tmp_path, scenario, extraction("pizza", "not_a_product"))

    assert names(streamed) == ["session_started", "progress", "progress", "session"]
    assert progress(streamed)[-1] == ("supervisor", "finished", "Finished.")
    report = data_of(streamed, "session")["session"]["report"]
    assert report["request"]["scope"] == "not_a_product"
    assert saved == {
        "status": "finished",
        "report": report,
        "lines": {
            "declined": {
                "parts": [
                    {
                        "kind": "text",
                        "text": "This app covers durable products such as cookware, appliances "
                        """and tools. It can't help with "pizza".""",
                    }
                ]
            },
            "evidence_summary": None,
            "caveats": [],
            "warnings": [],
            "stated": [],
            "typical_costs": [],
            "options": [],
            "check": {"groups": [], "confirm_price": None},
            "trail": [],
        },
    }


# --- The lines beside the data (docs/adr/0008-api-sends-finished-lines.md) ---


@pytest.mark.parametrize(
    ("text", "reply", "line"),
    [
        (FRYING_PAN, FRYING_PAN_REPLY, "Looking for: frying pan · Budget: €50"),
        (
            "I need a new frying pan",
            extraction("frying pan", "tuned"),
            "Looking for: frying pan · Budget: none given",
        ),
    ],
    ids=["a budget", "no budget"],
)
def test_what_was_understood_is_one_line_ended_by_the_edit_control(
    tmp_path: Path, text: str, reply: str, line: str
) -> None:
    async def scenario(api: Api) -> tuple[list[Event], Any]:
        streamed = events((await start(api, text)).text)
        session_id = data_of(streamed, "session_started")["session_id"]
        return streamed, (await read(api, session_id)).json()

    streamed, paused = served(tmp_path, scenario, reply)

    understood = data_of(streamed, "understood")["line"]
    assert plain(understood) == line
    assert understood["parts"][-1] == {"kind": "control", "key": "edit"}
    assert plain(data_of(streamed, "session")["lines"]["understood"]) == line
    assert plain(paused["lines"]["understood"]) == line


def test_the_box_label_comes_with_what_was_understood_and_with_the_paused_session(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> tuple[list[Event], Any]:
        streamed = events((await start(api, FRYING_PAN)).text)
        session_id = data_of(streamed, "session_started")["session_id"]
        return streamed, (await read(api, session_id)).json()

    streamed, paused = served(tmp_path, scenario, FRYING_PAN_REPLY)

    label = "frying pan · €50"
    assert plain(data_of(streamed, "understood")["label"]) == label
    assert plain(data_of(streamed, "session")["lines"]["label"]) == label
    assert plain(paused["lines"]["label"]) == label


BLOCKED_LINK = "https://example.org/shop/blocked"


def test_a_link_that_gave_no_product_is_declined_in_its_session_and_when_read_back(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> tuple[list[Event], Any]:
        streamed = events((await start(api, BLOCKED_LINK)).text)
        session_id = data_of(streamed, "session_started")["session_id"]
        return streamed, (await read(api, session_id)).json()

    streamed, finished = served(tmp_path, scenario, extraction(None, "general"))

    declined = (
        "We couldn't read the product at your link. "
        "Name the product to start, for example 'a frying pan, budget €50'."
    )
    lines = data_of(streamed, "session")["lines"]
    assert plain(lines["declined"]) == declined
    assert lines["understood"] is None
    assert finished["status"] == "finished"
    assert plain(finished["lines"]["declined"]) == declined


def test_a_typical_yearly_cost_line_links_its_site_to_its_source(tmp_path: Path) -> None:
    lines = served(tmp_path, started_with_lines, FRYING_PAN_REPLY)["lines"]

    assert plains(lines["typical_costs"]) == ["Seasoning oil: typically €6 a year (stub.invalid)."]
    assert lines["typical_costs"][0]["parts"][1] == {
        "kind": "link",
        "text": "stub.invalid",
        "url": "https://stub.invalid/seasoning-oil",
    }


MAKER_SOURCE = Source(
    kind=SourceKind.URL, reference="https://www.tefal.nl/pannen", stated_by=StatedBy.MANUFACTURER
)


async def brief_by_the_maker(
    request: Request,
    linked_product: ProductOption | None,
    chat: ChatModel,
    search: WebSearch,
    store: BriefStore,
) -> BriefOutput:
    """The stub brief, its hob factor stated by the pan's maker."""
    stub = await stub_brief(request, linked_product, chat, search, store)
    hob = HOB_FACTOR.model_copy(update={"source": MAKER_SOURCE})
    return stub.model_copy(update={"factors": (hob, *stub.factors[1:])})


def test_a_question_about_a_factor_the_maker_states_has_a_source_line_that_says_so(
    tmp_path: Path,
) -> None:
    agents = replace(STUB_AGENTS, brief=brief_by_the_maker)

    lines = served(tmp_path, started_with_lines, FRYING_PAN_REPLY, agents=agents)["lines"]

    assert {question: plain(line) for question, line in lines["sources"].items()} == {
        "question-researched-1": "Source: tefal.nl (the manufacturer states)"
    }
    assert lines["sources"]["question-researched-1"]["parts"][1]["url"] == MAKER_SOURCE.reference


def test_input_over_the_limit_is_refused_before_anything_runs(tmp_path: Path) -> None:
    async def scenario(api: Api) -> httpx.Response:
        return await start(api, "a frying pan " * 200)

    response = served(tmp_path, scenario)

    assert response.status_code == 422
    assert response.json() == {
        "code": "input_too_long",
        "message": (
            "That is more text than the app can read. Try naming one product in a sentence or two."
        ),
    }


def test_the_input_and_the_reply_publish_their_limit_as_their_max_length(tmp_path: Path) -> None:
    async def scenario(api: Api) -> Any:
        return (await api.client.get("/openapi.json")).json()["components"]["schemas"]

    schemas = served(tmp_path, scenario)

    # The limit of `input_too_long` (wording.INPUT_TOO_LONG); the schema documents it, the app
    # refuses a longer text with its own code.
    assert schemas["StartRequest"]["properties"]["input"]["maxLength"] == 2000
    reply = schemas["AnswersRequest"]["properties"]["reply"]["anyOf"]
    assert {"type": "string", "maxLength": 2000} in reply


@pytest.mark.parametrize(
    "body",
    [{}, {"input": 5}, {"input": "a frying pan", "budget": 50}],
    ids=["no input", "input not a text", "a field it does not take"],
)
def test_a_body_the_app_cannot_read_is_refused_with_its_code_and_message(
    tmp_path: Path, body: dict[str, Any]
) -> None:
    async def scenario(api: Api) -> httpx.Response:
        return await api.client.post("/sessions", json=body)

    response = served(tmp_path, scenario)

    assert response.status_code == 422
    assert response.json() == {
        "code": "invalid_request",
        "message": (
            "The app couldn't read what the page sent, so nothing was run. "
            "Reload the page and start again."
        ),
    }


def test_a_failed_model_call_streams_its_error_and_the_session_reads_as_interrupted(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    async def scenario(api: Api) -> tuple[list[Event], Any]:
        streamed = events((await start(api)).text)
        session_id = data_of(streamed, "session_started")["session_id"]
        return streamed, (await read(api, session_id)).json()

    with caplog.at_level(logging.ERROR):
        streamed, saved = served(tmp_path, scenario, ChatError("service down"))

    assert names(streamed) == ["session_started", "progress", "error"]
    assert data_of(streamed, "error") == {
        "event": "error",
        "code": "model_call_failed",
        "message": (
            "The app couldn't read your request just now, so nothing was run. "
            "Try again in a moment."
        ),
    }
    assert saved == {"status": "interrupted", "code": "run_stopped"}
    session_id = data_of(streamed, "session_started")["session_id"]
    assert [record.getMessage() for record in caplog.records] == [
        f"ModelCallError: code model_call_failed, session {session_id}, agent supervisor"
    ]


# --- Answering, end to end, against the terminal app ---


def third_choices(session: dict[str, Any]) -> list[dict[str, str]]:
    """The answers that pick each question's third choice, as typing 3 does in the CLI."""
    return [
        {"factor_id": question["factor_id"], "status": "chosen", "choice_id": choice["id"]}
        for question in session["questions"]
        for choice in question["choices"][2:3]
    ]


def cli_report(tmp_path: Path, typed: tuple[str, ...]) -> list[str]:
    """The report lines the terminal app prints for the frying pan, with these lines typed; none
    is --skip-all."""
    chat, _ = fake_chat([FRYING_PAN_REPLY])
    sources = fixture_sources(FIXTURES, tmp_path / "cli-cache")
    printed: list[str] = []
    asyncio.run(
        run(
            FRYING_PAN,
            chat,
            sources,
            typing(*typed),
            skip_all=not typed,
            agents=STUB_AGENTS,
            record_report=printed.extend,
        )
    )
    return printed


@pytest.mark.parametrize("typed", [("3", "3"), ()], ids=["answered", "skip all"])
def test_a_session_answered_through_the_api_gives_the_report_the_cli_prints(
    tmp_path: Path, typed: tuple[str, ...]
) -> None:
    async def scenario(api: Api) -> list[Event]:
        session = await started(api)
        answers = third_choices(session) if typed else []
        return events((await answer(api, session["session_id"], answers)).text)

    streamed = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert names(streamed) == ["progress"] * 7 + ["report"]
    assert progress(streamed)[-1] == ("supervisor", "finished", "Finished.")
    report = Report.model_validate(data_of(streamed, "report")["report"])
    assert list(printed_report(report)) == cli_report(tmp_path, typed)
    # The worked example's cost per use, at about once a week (docs/architecture/calculations.md).
    assert ("Cost per use: €0.20" in printed_report(report)) == bool(typed)


def figures(option: dict[str, Any]) -> list[tuple[str | None, str | None, bool]]:
    """An option's figures in the terminal's order, each as its label, its value and whether
    it is missing."""
    names = ("price", "lifespan", "cost_per_year", "cost_per_use", "purchases", "horizon_cost")
    return [
        (plain(option[name]["label"]), plain(option[name]["value"]), option[name]["missing"])
        for name in (*names, "co2e")
    ]


def test_the_frying_pan_reports_lines_reach_the_api_by_section_and_by_option(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> tuple[list[Event], Any]:
        session = await started(api)
        answered = await answer(api, session["session_id"], third_choices(session))
        return events(answered.text), (await read(api, session["session_id"])).json()

    streamed, finished = served(tmp_path, scenario, FRYING_PAN_REPLY)

    lines = data_of(streamed, "report")["lines"]
    assert finished["lines"] == lines
    assert plain(lines["evidence_summary"]) == (
        "Lifespan sourced for 0 of 2 options. CO2e to make: not found for 2."
    )
    assert plains(lines["typical_costs"]) == ["Seasoning oil: typically €6 a year (stub.invalid)."]
    non_stick, carbon_steel = lines["options"]
    assert (non_stick["option_id"], plain(non_stick["name"])) == ("option-1", "Non-stick pan")
    assert figures(non_stick) == [
        ("Price", "€20", False),
        ("Lifespan", "2 years (rough estimate)", False),
        ("Cost per year", "€10", False),
        ("Cost per use", "€0.20", False),
        ("Purchases over 10 years", "5", False),
        ("Cost over 10 years", "€100", False),
        ("CO2e", "not available (no CO2e estimate for this option)", True),
    ]
    assert non_stick["lifespan"]["value"]["parts"][1] == {
        "kind": "confidence",
        "text": "rough estimate",
        "basis": "estimate",
    }
    (hob,) = non_stick["factor_values"]
    assert (hob["factor_id"], plain(hob["figure"]["value"]), hob["figure"]["missing"]) == (
        "researched-1",
        "could not be confirmed",
        True,
    )
    assert plains(non_stick["rests_on_state"]) == [
        "No durability evidence found",
        "Owner and tester reports not looked up",
    ]
    assert non_stick["savings"] is None
    assert plain(carbon_steel["savings"]) == (
        "Over 10 years: Carbon steel pan costs €60 less than Non-stick pan. A lifespan behind "
        "this is a rough estimate."
    )
    check = lines["check"]
    assert [(plain(group["label"]), plains(group["items"])) for group in check["groups"]] == [
        (
            "Not yet known",
            ["Seasoning oil: A carbon steel pan is oiled now and then to keep its seasoning."],
        ),
        (
            "Could not be confirmed",
            [
                "Hob compatibility: Not every pan works on every hob. "
                "(Non-stick pan, Carbon steel pan)"
            ],
        ),
    ]
    assert plain(check["confirm_price"]) == (
        "Confirm the current price: Prices change after the day each was seen."
    )
    supervisor = lines["trail"][0]
    assert (supervisor["agent"], plain(supervisor["by"]), plain(supervisor["line"])) == (
        "supervisor",
        "supervisor [small, nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B]",
        "decided: Understood as: frying pan; scope tuned; budget €50",
    )


# --- Recalculating with changed assumptions ---


async def no_agent(*given: object) -> Any:
    raise AssertionError("an agent ran")


# A bundle whose every agent fails the test if it runs.
NO_AGENTS = AgentBundle(
    brief=no_agent, tco=no_agent, lca=no_agent, second_hand=no_agent, reply=no_agent
)
WHAT_IF = {"horizon_years": 20, "uses_per_year": 52, "lifespan_overrides": {"option-1": 5}}


async def reported(api: Api) -> str:
    """The id of a frying pan session answered to its report, at about once a week."""
    session = await started(api)
    await answer(api, session["session_id"], third_choices(session))
    return session["session_id"]


async def recalculate(api: Api, session_id: str, body: dict[str, Any]) -> httpx.Response:
    return await api.client.post(f"/sessions/{session_id}/recalculate", json=body)


def test_recalculating_a_report_gives_new_numbers_and_their_lines_without_any_agent(
    tmp_path: Path,
) -> None:
    session_id = served(tmp_path, reported, FRYING_PAN_REPLY)

    # A second app on the same sessions, whose model has no reply to give and whose agents fail.
    response = served(tmp_path, lambda api: recalculate(api, session_id, WHAT_IF), agents=NO_AGENTS)

    assert response.status_code == 200
    recalculation = response.json()
    assert recalculation["assumptions"] == {
        "horizon_years": 20,
        "uses_per_year": 52,
        "lifespan_overrides": {"option-1": "5"},
    }
    non_stick, carbon_steel = recalculation["comparison"]["rows"]
    assert (non_stick["purchases"], non_stick["horizon_cost"]) == (4, "80")
    assert (carbon_steel["purchases"], carbon_steel["horizon_cost"]) == (1, "40")
    assert recalculation["evidence_summary"]["lifespans_user_set"] == 1
    lines = recalculation["lines"]
    assert plain(lines["evidence_summary"]) == (
        "Lifespan sourced for 0 of 2 options, set by you for 1. CO2e to make: not found for 2."
    )
    non_stick_lines, _ = lines["options"]
    assert figures(non_stick_lines) == [
        ("Price", "€20", False),
        ("Lifespan", "5 years (set by you)", False),
        ("Cost per year", "€4", False),
        ("Cost per use", "€0.08", False),
        ("Purchases over 20 years", "4", False),
        ("Cost over 20 years", "€80", False),
        ("CO2e", "not available (no CO2e estimate for this option)", True),
    ]
    # Only what it recomputes: the rest of the report's lines are the report's own.
    assert lines["caveats"] == lines["warnings"] == lines["trail"] == []


def test_recalculating_saves_nothing_so_the_report_keeps_its_own_assumptions(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> tuple[Any, Any]:
        session_id = await reported(api)
        before = (await read(api, session_id)).json()
        await recalculate(api, session_id, WHAT_IF)
        return before, (await read(api, session_id)).json()

    before, after = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert after == before


def test_recalculating_with_the_reports_own_assumptions_gives_its_own_figures(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> tuple[Any, Any]:
        session_id = await reported(api)
        finished = (await read(api, session_id)).json()
        own = finished["report"]["assumptions"]
        return finished, (await recalculate(api, session_id, own)).json()

    finished, recalculation = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert recalculation["comparison"] == finished["report"]["comparison"]
    assert recalculation["lines"]["options"] == finished["lines"]["options"]
    assert recalculation["lines"]["evidence_summary"] == finished["lines"]["evidence_summary"]


@pytest.mark.parametrize(
    "changed",
    [
        {"horizon_years": 0},
        {"horizon_years": 31},
        {"uses_per_year": 0},
        {"uses_per_year": 3651},
        {"lifespan_overrides": {"option-1": 0.09}},
        {"lifespan_overrides": {"option-1": 101}},
    ],
    ids=["horizon 0", "horizon 31", "no uses", "3,651 uses", "0.09 years", "101 years"],
)
def test_an_assumption_out_of_bounds_is_refused_with_its_code_and_message(
    tmp_path: Path, changed: dict[str, Any]
) -> None:
    async def scenario(api: Api) -> httpx.Response:
        return await recalculate(api, await reported(api), WHAT_IF | changed)

    response = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert response.status_code == 422
    assert response.json() == {
        "code": "invalid_assumptions",
        "message": "Some of these assumptions are outside what the app can calculate, so nothing "
        "was recalculated. Change them and try again.",
    }


def test_the_bounds_themselves_are_within_them(tmp_path: Path) -> None:
    async def scenario(api: Api) -> list[int]:
        session_id = await reported(api)
        bodies = [
            {"horizon_years": 1, "uses_per_year": 1, "lifespan_overrides": {"option-1": 0.1}},
            {"horizon_years": 30, "uses_per_year": 3650, "lifespan_overrides": {"option-2": 100}},
        ]
        return [(await recalculate(api, session_id, body)).status_code for body in bodies]

    assert served(tmp_path, scenario, FRYING_PAN_REPLY) == [200, 200]


def test_assumptions_that_are_not_complete_are_an_invalid_request(tmp_path: Path) -> None:
    async def scenario(api: Api) -> httpx.Response:
        return await recalculate(api, await reported(api), {"horizon_years": 20})

    response = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert (response.status_code, response.json()["code"]) == (422, "invalid_request")


def test_a_lifespan_for_an_option_the_report_does_not_have_is_refused(tmp_path: Path) -> None:
    async def scenario(api: Api) -> httpx.Response:
        body = WHAT_IF | {"lifespan_overrides": {"option-9": 5}}
        return await recalculate(api, await reported(api), body)

    response = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert response.status_code == 422
    assert response.json() == {
        "code": "unknown_option",
        "message": "A lifespan was set for an option that is not on this report, so nothing was "
        "recalculated. Set the lifespans again.",
    }


def test_a_session_with_no_report_yet_or_none_at_all_cannot_be_recalculated(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> list[httpx.Response]:
        paused = (await started(api))["session_id"]
        return [await recalculate(api, paused, WHAT_IF), await recalculate(api, "none", WHAT_IF)]

    paused, unknown = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert paused.status_code == 409
    assert paused.json() == {
        "code": "no_report_yet",
        "message": "This session has no report yet, so nothing was recalculated. "
        "Change the assumptions once the report is ready.",
    }
    assert (unknown.status_code, unknown.json()["code"]) == (404, "session_not_found")


def test_a_report_with_no_options_has_nothing_to_recalculate(tmp_path: Path) -> None:
    async def scenario(api: Api) -> httpx.Response:
        # A request that does not run is finished at once, with a report and no options.
        session = (await started_with_lines(api, "a pizza"))["session"]
        body = WHAT_IF | {"lifespan_overrides": {}}
        return await recalculate(api, session["session_id"], body)

    response = served(tmp_path, scenario, extraction("pizza", "not_a_product"))

    assert response.status_code == 409
    assert response.json() == {
        "code": "no_options",
        "message": "This report has no options, so there is nothing to recalculate. "
        "Start again with your request.",
    }


# --- The limit of sessions per client IP ---

PIZZA = "a pizza"
# A request that does not run, so a start spends one model call and no agent runs.
PIZZA_REPLY = extraction("pizza", "not_a_product")
NOON = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


async def start_from(api: Api, forwarded_for: str | None = None) -> httpx.Response:
    """A start whose request carries the `X-Forwarded-For` header given, if any."""
    headers = {} if forwarded_for is None else {"X-Forwarded-For": forwarded_for}
    return await api.client.post("/sessions", json={"input": PIZZA}, headers=headers)


async def thirty_one_starts(api: Api) -> list[int]:
    return [(await start_from(api)).status_code for _ in range(31)]


def test_the_31st_session_in_an_hour_from_one_client_is_refused(tmp_path: Path) -> None:
    statuses = served(tmp_path, thirty_one_starts, *[PIZZA_REPLY] * 30, clock=Clock(NOON))

    assert statuses == [200] * 30 + [429]


def test_the_refusal_says_when_the_oldest_session_leaves_the_hour(tmp_path: Path) -> None:
    clock = Clock(NOON)

    async def scenario(api: Api) -> list[httpx.Response]:
        await start_from(api)
        clock.now = NOON + timedelta(minutes=10)
        for _ in range(29):
            await start_from(api)
        refused_at_ten = await start_from(api)
        clock.now = NOON + timedelta(minutes=59, seconds=30)
        refused_at_last_minute = await start_from(api)
        clock.now = NOON + timedelta(hours=1)
        return [refused_at_ten, refused_at_last_minute, await start_from(api)]

    at_ten, at_last_minute, an_hour_on = served(
        tmp_path, scenario, *[PIZZA_REPLY] * 31, clock=clock
    )

    assert at_ten.status_code == 429
    assert at_ten.json() == {
        "code": "too_many_sessions",
        "message": "Many sessions were started from this connection in the last hour, so no new "
        "one was started. Try again in 50 minutes.",
    }
    assert at_last_minute.json()["message"].endswith("Try again in 1 minute.")
    assert an_hour_on.status_code == 200


def test_input_refused_as_too_long_is_not_counted(tmp_path: Path) -> None:
    async def scenario(api: Api) -> list[int]:
        for _ in range(30):
            await api.client.post("/sessions", json={"input": "x" * 5000})
        return [(await start_from(api)).status_code]

    assert served(tmp_path, scenario, PIZZA_REPLY, clock=Clock(NOON)) == [200]


def test_behind_a_trusted_proxy_a_forged_leftmost_address_does_not_avoid_the_limit(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> list[int]:
        # The proxy appends the address it saw; the client writes anything before it.
        statuses = [
            (await start_from(api, f"10.0.0.{n}, 203.0.113.7")).status_code for n in range(31)
        ]
        other_client = await start_from(api, "10.0.0.1, 198.51.100.4")
        return [*statuses, other_client.status_code]

    statuses = served(
        tmp_path, scenario, *[PIZZA_REPLY] * 31, clock=Clock(NOON), trusted_proxy_hops=1
    )

    assert statuses == [200] * 30 + [429, 200]


def test_with_fewer_forwarded_entries_than_trusted_proxies_the_leftmost_is_not_used(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> list[int]:
        # Each entry alone is the leftmost, which the client may have written; so every one of
        # these counts as the connection's own address.
        return [(await start_from(api, f"198.51.100.{n}")).status_code for n in range(31)]

    statuses = served(
        tmp_path, scenario, *[PIZZA_REPLY] * 30, clock=Clock(NOON), trusted_proxy_hops=2
    )

    assert statuses[-1] == 429


def test_with_no_proxy_trusted_the_forwarded_header_is_ignored(tmp_path: Path) -> None:
    async def scenario(api: Api) -> list[int]:
        return [(await start_from(api, f"198.51.100.{n}")).status_code for n in range(31)]

    statuses = served(tmp_path, scenario, *[PIZZA_REPLY] * 30, clock=Clock(NOON))

    assert statuses[-1] == 429


def test_past_the_daily_ceiling_every_client_is_refused_until_a_day_has_passed(
    tmp_path: Path,
) -> None:
    clock = Clock(NOON)

    async def scenario(api: Api) -> list[httpx.Response]:
        first = await start_from(api, "198.51.100.1")
        second = await start_from(api, "198.51.100.2")
        over = await start_from(api, "198.51.100.3")
        clock.now = NOON + timedelta(days=1)
        return [first, second, over, await start_from(api, "198.51.100.3")]

    first, second, over, a_day_on = served(
        tmp_path,
        scenario,
        *[PIZZA_REPLY] * 3,
        clock=clock,
        trusted_proxy_hops=1,
        sessions_per_day=2,
    )

    assert [first.status_code, second.status_code] == [200, 200]
    assert over.status_code == 429
    assert over.json() == {
        "code": "too_many_sessions_today",
        "message": "Many sessions were started on this app in the last day, so no new one was "
        "started. Try again tomorrow.",
    }
    assert a_day_on.status_code == 200


def test_a_start_refused_over_the_hour_takes_no_place_of_the_day(tmp_path: Path) -> None:
    async def scenario(api: Api) -> list[int]:
        return [
            (await start_from(api, "198.51.100.1")).status_code,
            (await start_from(api, "198.51.100.1")).status_code,
            # The refusal above took no place of the day's two, so this one fills the second.
            (await start_from(api, "198.51.100.2")).status_code,
        ]

    statuses = served(
        tmp_path,
        scenario,
        *[PIZZA_REPLY] * 2,
        clock=Clock(NOON),
        trusted_proxy_hops=1,
        sessions_per_hour=1,
        sessions_per_day=2,
    )

    assert statuses == [200, 429, 200]


def test_a_start_refused_over_the_day_takes_no_place_of_the_hour(tmp_path: Path) -> None:
    clock = Clock(NOON)

    async def scenario(api: Api) -> list[int]:
        counted = await start_from(api, "198.51.100.1")
        clock.now = NOON + timedelta(hours=23, minutes=30)
        over_the_day = await start_from(api, "198.51.100.2")
        # The day has room again, and this client's refusal half an hour ago is not in its hour.
        clock.now = NOON + timedelta(days=1)
        again = await start_from(api, "198.51.100.2")
        return [counted.status_code, over_the_day.status_code, again.status_code]

    statuses = served(
        tmp_path,
        scenario,
        *[PIZZA_REPLY] * 2,
        clock=clock,
        trusted_proxy_hops=1,
        sessions_per_hour=1,
        sessions_per_day=1,
    )

    assert statuses == [200, 429, 200]


def test_startup_says_whether_a_proxy_is_trusted(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    async def scenario(api: Api) -> None:
        return None

    with caplog.at_level(logging.INFO, logger="shopper"):
        served(tmp_path, scenario)
        served(tmp_path, scenario, trusted_proxy_hops=1)
        served(tmp_path, scenario, trusted_proxy_hops=2)

    said = [record.getMessage() for record in caplog.records]
    assert [message for message in said if message.startswith("Sessions per client IP")] == [
        "Sessions per client IP: 30 an hour; the client IP is the connection's own address",
        "Sessions per client IP: 30 an hour; the client IP is read from X-Forwarded-For, "
        "1 proxy trusted",
        "Sessions per client IP: 30 an hour; the client IP is read from X-Forwarded-For, "
        "2 proxies trusted",
    ]


# --- Answers that are refused before a run starts ---


async def answered_unknown(api: Api) -> httpx.Response:
    return await answer(api, "no-such-session", [])


async def answered_twice(api: Api) -> httpx.Response:
    session_id = (await started(api))["session_id"]
    await answer(api, session_id, [])
    return await answer(api, session_id, [])


async def answered_for_no_question(api: Api) -> httpx.Response:
    session_id = (await started(api))["session_id"]
    return await answer(api, session_id, [{"factor_id": "none", "status": "not_sure"}])


@pytest.mark.parametrize(
    ("scenario", "status", "code"),
    [
        (answered_unknown, 404, "session_not_found"),
        (answered_twice, 409, "session_not_paused"),
        (answered_for_no_question, 422, "invalid_answers"),
    ],
    ids=["unknown session", "finished session", "an answer for no question"],
)
def test_answers_that_cannot_be_used_are_refused_with_their_code_and_message(
    tmp_path: Path,
    scenario: Callable[[Api], Awaitable[httpx.Response]],
    status: int,
    code: str,
) -> None:
    response = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert response.status_code == status
    assert response.json() == {"code": code, "message": wording.ERRORS[code]}


def test_a_session_whose_answers_were_refused_can_still_be_answered(tmp_path: Path) -> None:
    async def scenario(api: Api) -> list[Event]:
        session = await started(api)
        await answer(api, session["session_id"], [{"factor_id": "none", "status": "not_sure"}])
        return events((await answer(api, session["session_id"], third_choices(session))).text)

    streamed = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert names(streamed)[-1] == "report"


async def tco_that_stops(*given: object) -> TcoOutput:
    raise RuntimeError("the process went away, holding the input")


def test_a_run_that_stops_streams_run_stopped_and_the_session_reads_as_interrupted(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    agents = replace(STUB_AGENTS, tco=tco_that_stops)

    async def scenario(api: Api) -> tuple[str, list[Event], Any]:
        session_id = (await started(api))["session_id"]
        streamed = events((await answer(api, session_id, [])).text)
        return session_id, streamed, (await read(api, session_id)).json()

    with caplog.at_level(logging.ERROR):
        session_id, streamed, saved = served(tmp_path, scenario, FRYING_PAN_REPLY, agents=agents)

    assert names(streamed) == ["progress", "error"]
    assert data_of(streamed, "error") == {
        "event": "error",
        "code": "run_stopped",
        "message": "The run stopped before your report was ready. Start again with your request.",
    }
    assert saved == {"status": "interrupted", "code": "run_stopped"}
    # The error is logged by its class, code, session and agent; its message can carry the input.
    assert [record.getMessage() for record in caplog.records] == [
        f"RuntimeError: code run_stopped, session {session_id}, agent tco"
    ]


# --- Answering with a reply ---


def steps(streamed: list[Event]) -> list[str]:
    return [data["step"] for name, data in streamed if name == "progress"]


def test_a_session_answered_only_by_a_reply_streams_its_reading_and_what_it_gave_first(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> list[Event]:
        session_id = (await started(api))["session_id"]
        return events((await answer(api, session_id, [], INDUCTION_WEEKLY)).text)

    streamed = served(
        tmp_path, scenario, FRYING_PAN_REPLY, READ_INDUCTION_WEEKLY, agents=REPLY_AGENTS
    )

    assert names(streamed) == ["progress", "progress", "reply_read"] + ["progress"] * 7 + ["report"]
    assert progress(streamed)[:3] == [
        ("brief", "started", "Reading your reply..."),
        ("brief", "finished", "Finished reading your reply."),
        ("tco", "started", "Finding options and their prices..."),
    ]
    assert steps(streamed) == ["reply"] * 2 + ["research"] * 7
    report = data_of(streamed, "report")["report"]
    read = data_of(streamed, "reply_read")
    assert {name: value for name, value in read.items() if name != "lines"} == {
        "event": "reply_read",
        "stated_answers": report["answers"],
        "factors": [],
        "asks_to_change_request": False,
        "answered_already": False,
    }
    assert plains(read["lines"]) == [
        'From your reply: Hob compatibility: Induction ("on induction")',
        'From your reply: About once a week, 50 uses a year ("about once a week")',
    ]
    assert [answer["stated_in"] for answer in report["answers"]] == ["reply"] * 2


def test_a_reply_that_adds_a_requirement_of_the_users_own_shows_it_from_the_reply(
    tmp_path: Path,
) -> None:
    async def scenario(api: Api) -> list[Event]:
        session_id = (await started(api))["session_id"]
        return events((await answer(api, session_id, [], "it must be oven safe")).text)

    streamed = served(
        tmp_path,
        scenario,
        FRYING_PAN_REPLY,
        reading(said("new", "oven safe", value="oven safe")),
        agents=REPLY_AGENTS,
    )

    assert plains(data_of(streamed, "reply_read")["lines"]) == ['From your reply: "oven safe"']
    assert names(streamed)[-1] == "report"


def test_a_reply_that_asks_to_change_the_request_says_so_in_what_it_gave(tmp_path: Path) -> None:
    async def scenario(api: Api) -> list[Event]:
        session = await started(api)
        answers = third_choices(session)[:1]
        return events((await answer(api, session["session_id"], answers, "make it €40")).text)

    streamed = served(
        tmp_path,
        scenario,
        FRYING_PAN_REPLY,
        reading(said("new", "make it €40", changes="budget")),
        agents=REPLY_AGENTS,
    )

    assert data_of(streamed, "reply_read")["asks_to_change_request"] is True
    assert plains(data_of(streamed, "reply_read")["lines"]) == [
        "A reply can't change what you're looking for or the budget, so the results are still "
        "for frying pan, budget €50. To change either, press Edit."
    ]
    assert data_of(streamed, "report")["report"]["request"]["budget"] == "50"


class NotGoingOn(NamedTuple):
    """A reply that leaves the session paused: what the model answers its reading with, the
    events of the stream, and the code and message it ends with."""

    readings: tuple[str | Exception, ...]
    streamed: list[str]
    code: str
    message: str


REPLY_UNANSWERED = NotGoingOn(
    (READ_NOTHING_NAMED,),
    ["progress", "progress", "reply_read", "error"],
    "reply_unanswered",
    "Nothing in your reply answered the open questions, so nothing was run. "
    "Answer in your own words or with the choices.",
)
REPLY_UNREAD = NotGoingOn(
    (ChatError("service down"), ChatError("service down")),
    ["progress", "error"],
    "reply_unread",
    "The app couldn't read your reply just now, so nothing was run. "
    "Send it again, or answer with the choices.",
)


@pytest.mark.parametrize(
    "case", [REPLY_UNANSWERED, REPLY_UNREAD], ids=["nothing answered", "the reading failed"]
)
def test_a_reply_that_does_not_go_on_leaves_the_session_paused_and_a_second_send_works(
    tmp_path: Path, case: NotGoingOn, caplog: pytest.LogCaptureFixture
) -> None:
    async def scenario(api: Api) -> tuple[Any, ...]:
        start = await started_with_lines(api)
        session_id = start["session"]["session_id"]
        streamed = events((await answer(api, session_id, [], NOTHING_NAMED)).text)
        paused = (await read(api, session_id)).json()
        again = events((await answer(api, session_id, third_choices(start["session"]))).text)
        return start, streamed, paused, again

    with caplog.at_level(logging.ERROR):
        start, streamed, paused, again = served(
            tmp_path, scenario, FRYING_PAN_REPLY, *case.readings, agents=REPLY_AGENTS
        )
    session = start["session"]

    assert names(streamed) == case.streamed
    assert data_of(streamed, "error") == {
        "event": "error",
        "code": case.code,
        "message": case.message,
    }
    if case is REPLY_UNANSWERED:
        assert data_of(streamed, "reply_read")["lines"] == []
    assert paused == {"status": "paused", "session": session, "lines": start["lines"]}
    assert names(again)[-1] == "report"
    logged = [record.getMessage() for record in caplog.records]
    if case is REPLY_UNREAD:
        session_id = session["session_id"]
        assert logged == [f"ReplyUnreadError: code reply_unread, session {session_id}, agent brief"]
    else:
        assert logged == []


async def brief_without_questions(
    request: Request,
    linked_product: ProductOption | None,
    chat: ChatModel,
    search: WebSearch,
    store: BriefStore,
) -> BriefOutput:
    """A brief whose research gave nothing to ask about."""
    return BriefOutput()


def test_an_unanswered_reply_to_no_questions_asks_for_a_requirement_and_cannot_change_the_request(
    tmp_path: Path,
) -> None:
    agents = replace(REPLY_AGENTS, brief=brief_without_questions)

    async def scenario(api: Api) -> list[Event]:
        session_id = (await started(api))["session_id"]
        return events((await answer(api, session_id, [], "make it €40")).text)

    streamed = served(
        tmp_path,
        scenario,
        FRYING_PAN_REPLY,
        reading(said("new", "make it €40", changes="budget")),
        agents=agents,
    )

    assert names(streamed) == ["progress", "progress", "reply_read", "error"]
    assert plains(data_of(streamed, "reply_read")["lines"]) == [
        "A reply can't change what you're looking for or the budget. To change either, press Edit."
    ]
    assert data_of(streamed, "error") == {
        "event": "error",
        "code": "reply_unanswered",
        "message": (
            "Nothing in your reply added a requirement, so nothing was run. "
            "Add one in your own words, or clear your reply and press Show my options."
        ),
    }


def test_a_reply_over_the_limit_is_refused_before_the_session_is_checked(tmp_path: Path) -> None:
    release = asyncio.Event()
    agents = replace(REPLY_AGENTS, tco=delayed(STUB_AGENTS.tco, release.wait))

    async def scenario(api: Api) -> httpx.Response:
        session_id = (await started(api))["session_id"]
        running = asyncio.create_task(answer(api, session_id, []))
        while (await read(api, session_id)).json()["status"] != "running":
            await asyncio.sleep(0.01)
        refused = await answer(api, session_id, [], "induction " * 300)
        release.set()
        await running
        return refused

    response = served(tmp_path, scenario, FRYING_PAN_REPLY, agents=agents)

    # A running session would be refused as session_running once the slot is asked for.
    assert response.status_code == 422
    assert response.json() == {
        "code": "reply_too_long",
        "message": (
            "That is more text than the app can read, so nothing was sent. "
            "Answer in a sentence or two."
        ),
    }


def test_an_answer_the_reply_gives_cannot_be_sent_as_a_given_answer(tmp_path: Path) -> None:
    async def scenario(api: Api) -> httpx.Response:
        session = await started(api)
        (hob, _) = session["questions"]
        stated = {"factor_id": hob["factor_id"], "status": "not_sure", "stated_in": "reply"}
        return await answer(api, session["session_id"], [stated])

    response = served(tmp_path, scenario, FRYING_PAN_REPLY)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


# --- No personal data in the logs ---

MARKER = "marker-7f3a9c"


async def tco_that_stops_holding_the_marker(*given: object) -> TcoOutput:
    raise RuntimeError(f"stopped on {FRYING_PAN} {MARKER}")


async def answered_with_the_marker(api: Api) -> None:
    streamed = events((await start(api, f"{FRYING_PAN} {MARKER}")).text)
    session_id = data_of(streamed, "session_started")["session_id"]
    await answer(api, session_id, [])
    await read(api, session_id)


async def refused_with_the_marker(api: Api) -> None:
    await api.client.post("/sessions", json={"input": MARKER, "note": MARKER})
    await api.client.post("/sessions", json={"input": MARKER * 200})
    session_id = (await started(api))["session_id"]
    await answer(api, session_id, [], MARKER * 200)


# A reply with the marker in a phrase kept as an answer and in one refused as a change to the
# request.
KEPT, REFUSED = f"on induction {MARKER}", f"I meant a wok {MARKER}"


async def replied_with_the_marker(api: Api) -> None:
    session_id = (await started(api))["session_id"]
    await answer(api, session_id, [], f"{KEPT}, {REFUSED}")
    await read(api, session_id)


READ_THE_MARKER = reading(
    said(STUB_HOB_NUMBER, KEPT, choice=3), said("new", REFUSED, changes="category")
)


@pytest.mark.parametrize(
    ("scenario", "replies", "agents"),
    [
        (answered_with_the_marker, [FRYING_PAN_REPLY], STUB_AGENTS),
        (
            answered_with_the_marker,
            [FRYING_PAN_REPLY],
            replace(STUB_AGENTS, tco=tco_that_stops_holding_the_marker),
        ),
        (answered_with_the_marker, [ChatError(f"{FRYING_PAN} {MARKER}")], STUB_AGENTS),
        (refused_with_the_marker, [FRYING_PAN_REPLY], STUB_AGENTS),
        (replied_with_the_marker, [FRYING_PAN_REPLY, READ_THE_MARKER], REPLY_AGENTS),
        (
            replied_with_the_marker,
            [FRYING_PAN_REPLY, *[ChatError(f"{KEPT}, {REFUSED}")] * 2],
            REPLY_AGENTS,
        ),
    ],
    ids=[
        "a session to its report",
        "a run that stops",
        "a failed model call",
        "refused bodies",
        "a reply to its report",
        "a reply not read",
    ],
)
def test_the_input_appears_in_no_log_record(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    scenario: Callable[[Api], Awaitable[None]],
    replies: list[str | Exception],
    agents: AgentBundle,
) -> None:
    with caplog.at_level(logging.DEBUG):
        served(tmp_path, scenario, *replies, agents=agents)

    assert caplog.records
    assert MARKER not in caplog.text
    assert not [record for record in caplog.records if MARKER in str(record.__dict__)]


def test_a_client_ip_appears_in_no_log_record(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    async def scenario(api: Api) -> list[int]:
        return [(await start_from(api, "198.51.100.77")).status_code for _ in range(31)]

    with caplog.at_level(logging.DEBUG):
        statuses = served(
            tmp_path, scenario, *[PIZZA_REPLY] * 30, clock=Clock(NOON), trusted_proxy_hops=1
        )

    assert statuses[-1] == 429
    assert caplog.records
    assert not [record for record in caplog.records if "198.51.100.77" in str(record.__dict__)]


# --- Reading a session ---


def test_a_session_reads_back_as_paused_and_then_as_finished(tmp_path: Path) -> None:
    async def scenario(api: Api) -> tuple[Any, ...]:
        start = await started_with_lines(api)
        session_id = start["session"]["session_id"]
        paused = (await read(api, session_id)).json()
        streamed = events((await answer(api, session_id, [])).text)
        finished = (await read(api, session_id)).json()
        return start, paused, data_of(streamed, "report"), finished

    start, paused, report, finished = served(tmp_path, scenario, FRYING_PAN_REPLY)

    # The views carry the lines of the events they stand for.
    assert paused == {"status": "paused", "session": start["session"], "lines": start["lines"]}
    assert finished == {"status": "finished", "report": report["report"], "lines": report["lines"]}


def test_an_unknown_session_is_not_found(tmp_path: Path) -> None:
    async def scenario(api: Api) -> httpx.Response:
        return await read(api, "no-such-session")

    response = served(tmp_path, scenario)

    assert response.status_code == 404
    assert response.json() == {
        "code": "session_not_found",
        "message": "We couldn't find this session. Start again with your request.",
    }


def test_a_session_older_than_7_days_is_swept_out_at_startup(tmp_path: Path) -> None:
    session_id = served(tmp_path, lambda api: started(api), FRYING_PAN_REPLY)["session_id"]

    # A restart a day later keeps it; one more than 7 days after it was saved deletes it.
    a_day_on = served(
        tmp_path, lambda api: read(api, session_id), clock=Clock(utc_now() + timedelta(days=1))
    )
    eight_days_on = served(
        tmp_path, lambda api: read(api, session_id), clock=Clock(utc_now() + timedelta(days=8))
    )

    assert a_day_on.json()["status"] == "paused"
    assert eight_days_on.status_code == 404


# --- An unexpected error before a stream ---


@asynccontextmanager
async def database_gone(path: Path) -> AsyncGenerator[BaseCheckpointSaver]:
    """The saved sessions, their database connection closed from the start, as when the file
    can no longer be read."""
    async with saved_sessions(path) as saver:
        await saver.conn.close()
        yield saver


@pytest.mark.parametrize(
    "scenario",
    [lambda api: read(api, "a-session"), lambda api: answer(api, "a-session", [])],
    ids=["reading a session", "answering a session"],
)
def test_an_unexpected_error_before_a_stream_gets_its_code_and_message(
    tmp_path: Path,
    scenario: Callable[[Api], Awaitable[httpx.Response]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR):
        response = served(tmp_path, scenario, database=database_gone)

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "The app couldn't answer just now. Try again in a moment.",
    }
    # The sweep at startup cannot read the sessions either.
    assert [record.getMessage() for record in caplog.records] == [
        "ValueError: code sweep_failed, session none, agent none",
        "ValueError: code internal_error, session a-session, agent none",
    ]


# --- A client that disconnects ---


async def disconnected(app: FastAPI, path: str, body: dict[str, Any], after: str) -> str:
    """POST straight to the ASGI app, read its stream up to the event named `after`, then go away
    as a client does; the stream read so far. httpx's ASGI transport cannot do this: it reads a
    whole response before returning it."""
    gone = asyncio.Event()
    pending = [{"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}]
    read_so_far: list[bytes] = []

    async def receive() -> dict[str, Any]:
        if pending:
            return pending.pop()
        await gone.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.body":
            read_so_far.append(message["body"])
            if f"event: {after}\n".encode() in b"".join(read_so_far):
                gone.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "client": ("test", 1),
        "server": ("test", 80),
    }
    await app(scope, receive, send)
    return b"".join(read_so_far).decode()


def delayed[**P, R](
    agent: Callable[P, Awaitable[R]], wait: Callable[[], Awaitable[object]]
) -> Callable[P, Awaitable[R]]:
    """The same agent, starting once `wait` is over: the test releases it, or time passes."""

    async def waiting(*args: P.args, **kwargs: P.kwargs) -> R:
        await wait()
        return await agent(*args, **kwargs)

    return waiting


async def settled(api: Api, session_id: str) -> dict[str, Any]:
    """The session once its run has ended."""
    for _ in range(500):
        view = (await read(api, session_id)).json()
        if view["status"] != "running":
            return view
        await asyncio.sleep(0.01)
    raise AssertionError(f"session {session_id} is still running")


def test_a_client_that_disconnects_during_the_start_finds_the_session_paused(
    tmp_path: Path,
) -> None:
    release = asyncio.Event()
    agents = replace(STUB_AGENTS, brief=delayed(STUB_AGENTS.brief, release.wait))

    async def scenario(api: Api) -> tuple[Any, ...]:
        streamed = await disconnected(
            api.app, "/sessions", {"input": FRYING_PAN}, "session_started"
        )
        session_id = data_of(events(streamed), "session_started")["session_id"]
        running = (await read(api, session_id)).json()
        release.set()
        return running, await settled(api, session_id)

    running, saved = served(tmp_path, scenario, FRYING_PAN_REPLY, agents=agents)

    assert running == {"status": "running"}
    assert saved["status"] == "paused"
    assert len(saved["session"]["questions"]) == 2


def test_a_client_that_disconnects_during_the_run_finds_the_session_finished(
    tmp_path: Path,
) -> None:
    release = asyncio.Event()
    agents = replace(STUB_AGENTS, tco=delayed(STUB_AGENTS.tco, release.wait))

    async def scenario(api: Api) -> tuple[Any, ...]:
        session_id = (await started(api))["session_id"]
        path = f"/sessions/{session_id}/answers"
        streamed = await disconnected(api.app, path, {"answers": []}, "progress")
        running = (await read(api, session_id)).json()
        release.set()
        return streamed, running, await settled(api, session_id)

    streamed, running, saved = served(tmp_path, scenario, FRYING_PAN_REPLY, agents=agents)

    assert progress(events(streamed)) == [("tco", "started", "Finding options and their prices...")]
    assert running == {"status": "running"}
    assert saved["status"] == "finished"
    assert len(saved["report"]["options"]) == 2


# --- Two answers at once ---


def test_two_answers_sent_at_once_give_one_run_and_one_session_running(tmp_path: Path) -> None:
    release = asyncio.Event()
    agents = replace(STUB_AGENTS, tco=delayed(STUB_AGENTS.tco, release.wait))

    async def scenario(api: Api) -> tuple[httpx.Response, list[httpx.Response]]:
        session_id = (await started(api))["session_id"]
        both = [asyncio.create_task(answer(api, session_id, [])) for _ in range(2)]
        # The run is held, so the request that answers first is the one refused.
        done, _ = await asyncio.wait(both, timeout=5, return_when=asyncio.FIRST_COMPLETED)
        assert done, "neither request was answered while the run was held"
        release.set()
        return done.pop().result(), [await request for request in both]

    refused, responses = served(tmp_path, scenario, FRYING_PAN_REPLY, agents=agents)

    assert refused.status_code == 409
    assert refused.json() == {
        "code": "session_running",
        "message": (
            "This session is already running, so nothing new was started. Wait for it to finish."
        ),
    }
    assert sorted(response.status_code for response in responses) == [200, 409]
    (ran,) = [response for response in responses if response.status_code == 200]
    assert names(events(ran.text))[-1] == "report"


# --- The keep-alive ---


def test_a_stream_with_nothing_to_send_for_the_interval_sends_a_keep_alive_comment(
    tmp_path: Path,
) -> None:
    agents = replace(STUB_AGENTS, brief=delayed(STUB_AGENTS.brief, lambda: asyncio.sleep(0.05)))

    response = served(tmp_path, start, FRYING_PAN_REPLY, agents=agents, keep_alive_seconds=0.01)

    assert KEEP_ALIVE in response.text.splitlines()
    # A comment is no event: the stream still ends with the session.
    assert names(events(response.text))[-1] == "session"


# --- The OpenAPI schema, the frontend's contract ---


def openapi(tmp_path: Path) -> dict[str, Any]:
    async def scenario(api: Api) -> httpx.Response:
        return await api.client.get("/openapi.json")

    return served(tmp_path, scenario).json()


def ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def error_responses(operation: dict[str, Any]) -> dict[str, Any]:
    return {
        status: response["content"]["application/json"]["schema"]
        for status, response in operation["responses"].items()
        if status != "200"
    }


def test_the_schema_documents_each_stream_as_events_of_the_stream_event_union(
    tmp_path: Path,
) -> None:
    schema = openapi(tmp_path)

    for path in ("/sessions", "/sessions/{session_id}/answers"):
        success = schema["paths"][path]["post"]["responses"]["200"]
        assert success["content"] == {"text/event-stream": {"schema": ref("StreamEvent")}}
    union = schema["components"]["schemas"]["StreamEvent"]
    assert union["discriminator"]["propertyName"] == "event"
    assert sorted(union["discriminator"]["mapping"]) == [
        "error",
        "progress",
        "reply_read",
        "report",
        "session",
        "session_started",
        "understood",
    ]


def test_the_answers_route_takes_given_answers_and_a_reply(tmp_path: Path) -> None:
    schemas = openapi(tmp_path)["components"]["schemas"]

    body = schemas["AnswersRequest"]["properties"]
    assert body["answers"]["items"] == ref("GivenAnswer")
    assert sorted(body) == ["answers", "reply"]
    given = schemas["GivenAnswer"]
    assert sorted(given["properties"]) == ["choice_id", "factor_id", "status"]
    assert given["properties"]["status"]["enum"] == ["chosen", "not_sure"]
    # The answers the API sends are one schema, now that none is taken.
    assert "Answer" in schemas
    assert "Answer-Input" not in schemas


def test_the_recalculate_route_publishes_its_bounds_and_names_the_recalculation(
    tmp_path: Path,
) -> None:
    schema = openapi(tmp_path)

    operation = schema["paths"]["/sessions/{session_id}/recalculate"]["post"]
    success = operation["responses"]["200"]["content"]
    assert success == {"application/json": {"schema": ref("Recalculation")}}
    body = schema["components"]["schemas"]["RecalculateRequest"]
    assert sorted(body["required"]) == ["horizon_years", "lifespan_overrides", "uses_per_year"]
    fields = body["properties"]
    assert (fields["horizon_years"]["minimum"], fields["horizon_years"]["maximum"]) == (1, 30)
    uses, _ = fields["uses_per_year"]["anyOf"]
    assert (uses["minimum"], uses["maximum"]) == (1, 3650)
    lifespan = fields["lifespan_overrides"]["additionalProperties"]
    assert (lifespan["minimum"], lifespan["maximum"]) == (0.1, 100)


def test_the_schema_names_the_session_view(tmp_path: Path) -> None:
    schema = openapi(tmp_path)

    success = schema["paths"]["/sessions/{session_id}"]["get"]["responses"]["200"]
    assert success["content"] == {"application/json": {"schema": ref("SessionView")}}
    view = schema["components"]["schemas"]["SessionView"]
    assert sorted(view["discriminator"]["mapping"]) == [
        "finished",
        "interrupted",
        "paused",
        "running",
    ]


def test_each_route_declares_its_error_responses_as_the_error_body(tmp_path: Path) -> None:
    paths = openapi(tmp_path)["paths"]

    error = ref("ApiError")
    assert error_responses(paths["/sessions"]["post"]) == {
        "422": error,
        "429": error,
        "500": error,
    }
    assert error_responses(paths["/sessions/{session_id}/answers"]["post"]) == {
        "404": error,
        "409": error,
        "422": error,
        "500": error,
    }
    assert error_responses(paths["/sessions/{session_id}"]["get"]) == {
        "404": error,
        "422": error,
        "500": error,
    }
    assert error_responses(paths["/sessions/{session_id}/recalculate"]["post"]) == {
        "404": error,
        "409": error,
        "422": error,
        "500": error,
    }
    assert error_responses(paths["/health"]["get"]) == {}


def test_the_tag_of_each_event_and_session_view_is_required_so_generated_types_narrow(
    tmp_path: Path,
) -> None:
    schemas = openapi(tmp_path)["components"]["schemas"]

    for union, tag in (("StreamEvent", "event"), ("SessionView", "status")):
        for member in schemas[union]["discriminator"]["mapping"].values():
            assert tag in schemas[member.rsplit("/", 1)[1]]["required"]


# --- Tracing ---


async def answered(api: Api) -> None:
    session = await started(api)
    await answer(api, session["session_id"], [])


def test_with_tracing_off_no_run_is_traced_though_the_environment_asks(tmp_path: Path) -> None:
    client = MagicMock(spec=langsmith.Client)

    # As when the process environment asks LangSmith to trace.
    with langsmith.tracing_context(enabled=True, client=client):
        served(tmp_path, answered, FRYING_PAN_REPLY, trace=tracer(None, client))

    assert client.method_calls == []


def test_with_tracing_on_the_start_and_the_answers_are_each_one_trace(tmp_path: Path) -> None:
    client = MagicMock(spec=langsmith.Client)

    served(tmp_path, answered, FRYING_PAN_REPLY, trace=tracer(TRACING_ON, client))

    created = [kwargs for method, _, kwargs in client.method_calls if method == "create_run"]
    sessions = [run_ for run_ in created if run_["name"] == "session"]
    assert [run_["inputs"] for run_ in sessions] == [
        {"input": FRYING_PAN},
        {"input": '{"answers":[]}'},
    ]
    nodes = {run_["name"]: run_["trace_id"] for run_ in created}
    assert nodes["parse_request"] == sessions[0]["trace_id"]
    assert nodes["tco"] == sessions[1]["trace_id"]
    assert {run_["session_name"] for run_ in sessions} == {"tests"}


def test_with_tracing_on_a_slow_flush_holds_up_no_response(tmp_path: Path) -> None:
    client = MagicMock(spec=langsmith.Client)
    release = threading.Event()
    finished = threading.Event()

    def slow_flush() -> None:
        release.wait(timeout=5)
        finished.set()

    client.flush.side_effect = slow_flush

    async def scenario(api: Api) -> bool:
        await start(api)
        answered_while_flushing = client.flush.called and not finished.is_set()
        release.set()
        return answered_while_flushing

    assert served(tmp_path, scenario, FRYING_PAN_REPLY, trace=tracer(TRACING_ON, client))


# --- CORS ---

FRONTEND = "https://copilot.example"


def preflight(origin: str) -> Callable[[Api], Awaitable[httpx.Response]]:
    """The browser's check before it posts a start from a page on `origin`."""

    async def scenario(api: Api) -> httpx.Response:
        return await api.client.options(
            "/sessions",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    return scenario


def test_the_frontend_may_call_the_api_from_its_own_origin(tmp_path: Path) -> None:
    response = served(tmp_path, preflight(FRONTEND), origins=(FRONTEND,))

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND


def test_a_page_on_any_other_origin_may_not(tmp_path: Path) -> None:
    response = served(tmp_path, preflight("https://elsewhere.example"), origins=(FRONTEND,))

    assert "access-control-allow-origin" not in response.headers


# --- The words of each code ---


def test_every_code_the_api_answers_with_has_its_message() -> None:
    codes = {*get_args(RefusalCode), *get_args(UnexpectedCode), *get_args(RunErrorCode)}

    assert codes <= set(wording.ERRORS)


# --- Health ---


def test_health_answers_ok(tmp_path: Path) -> None:
    async def scenario(api: Api) -> httpx.Response:
        return await api.client.get("/health")

    response = served(tmp_path, scenario)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "tracing": False}


def test_health_says_when_the_runs_are_traced(tmp_path: Path) -> None:
    async def scenario(api: Api) -> httpx.Response:
        return await api.client.get("/health")

    assert served(tmp_path, scenario, tracing=True).json()["tracing"] is True
