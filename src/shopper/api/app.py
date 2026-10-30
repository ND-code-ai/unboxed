"""The app, its lifespan and its routes (docs/service_architecture.md, "API surface")."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from langgraph.checkpoint.base import BaseCheckpointSaver
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shopper.agents.bundle import AgentBundle
from shopper.agents.default import DEFAULT_AGENTS
from shopper.api import runs
from shopper.api.error_log import log_error
from shopper.api.limits import StartLimit, TooManySessions, client_address, limit_line
from shopper.api.models import (
    AnswersRequest,
    ApiError,
    FixedRefusalCode,
    FixedResponseErrorCode,
    Health,
    RecalculateRequest,
    Recalculation,
    ResponseErrorCode,
    SessionView,
    StartRequest,
    StreamEvent,
    api_error,
    too_many_sessions_error,
)
from shopper.api.recalculation import recalculated
from shopper.api.runs import Events, Sessions
from shopper.api.sweep import sweeping, swept
from shopper.calc.display import whole_minutes
from shopper.config import (
    DEFAULT_FRONTEND_ORIGINS,
    DEFAULT_SESSIONS_PER_DAY,
    DEFAULT_SESSIONS_PER_IP_PER_HOUR,
    DEFAULT_TRUSTED_PROXY_HOPS,
    KEEP_ALIVE_SECONDS,
)
from shopper.graph.graph import build_graph
from shopper.llm import ChatModel
from shopper.tools.results import Clock, utc_now
from shopper.tools.sources import Sources
from shopper.tracing import UNTRACED, Tracer

# The status of each code a request is answered with before its stream starts.
_STATUS: dict[ResponseErrorCode, int] = {
    "session_not_found": 404,
    "session_running": 409,
    "session_not_paused": 409,
    "invalid_answers": 422,
    "invalid_request": 422,
    "input_too_long": 422,
    "reply_too_long": 422,
    "too_many_sessions": 429,
    "too_many_sessions_today": 429,
    "no_report_yet": 409,
    "no_options": 409,
    "unknown_option": 422,
    "invalid_assumptions": 422,
    "internal_error": 500,
}

EVENT_STREAM = "text/event-stream"
JSON = "application/json"
_STREAM_EVENT_REF = "#/components/schemas/StreamEvent"

router = APIRouter()
_LOG = logging.getLogger(__name__)


def create_app(
    chat: ChatModel,
    sources: Sources,
    checkpointer: AbstractAsyncContextManager[BaseCheckpointSaver],
    *,
    agents: AgentBundle = DEFAULT_AGENTS,
    keep_alive_seconds: float = KEEP_ALIVE_SECONDS,
    origins: Sequence[str] = DEFAULT_FRONTEND_ORIGINS,
    trace: Tracer = UNTRACED,
    tracing: bool = False,
    sessions_per_hour: int = DEFAULT_SESSIONS_PER_IP_PER_HOUR,
    sessions_per_day: int = DEFAULT_SESSIONS_PER_DAY,
    trusted_proxy_hops: int = DEFAULT_TRUSTED_PROXY_HOPS,
    clock: Clock = utc_now,
) -> FastAPI:
    """The app over one graph, built once by its lifespan on the checkpointer it opens; only pages
    on `origins` may call it from a browser, each run is traced by `trace` (`tracing` says whether
    that sends anything), a client IP may start `sessions_per_hour` sessions an hour, read behind
    `trusted_proxy_hops` proxies, and all clients together `sessions_per_day` a day. The lifespan
    sweeps out old sessions at startup and then hourly.

    A test passes the agents it wants, a keep-alive interval it can wait out and a clock it sets.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        async with checkpointer as saver:
            graph = build_graph(chat, saver, sources, agents)
            limit = StartLimit(
                sessions_per_hour,
                trusted_proxy_hops,
                started={},
                per_day=sessions_per_day,
                started_by_anyone=[],
            )
            app.state.sessions = Sessions(
                graph,
                keep_alive_seconds,
                trace,
                running={},
                chat=chat,
                agents=agents,
                limit=limit,
                clock=clock,
                tracing=tracing,
            )
            _LOG.info(limit_line(limit))
            await swept(saver, app.state.sessions.running, clock())
            sweeper = asyncio.create_task(sweeping(saver, app.state.sessions.running, clock))
            try:
                yield
            finally:
                sweeper.cancel()
                with suppress(asyncio.CancelledError):
                    await sweeper

    app = _routed(lifespan)
    app.add_exception_handler(RequestValidationError, _invalid_request)
    app.add_middleware(_internal_error_guard)
    # Added last, so it is outermost: an internal_error answer carries its headers too.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )
    return app


def openapi_schema() -> dict[str, Any]:
    """The schema the app serves at `/openapi.json`, built with no model, sources or database:
    the lifespan that needs them never runs."""
    return _routed(None).openapi()


def _routed(lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] | None) -> FastAPI:
    """The app with its routes and its schema, which is all the schema depends on."""
    app = FastAPI(title="True Cost Copilot", lifespan=lifespan)
    app.include_router(router)
    app.openapi = _event_streams(app.openapi)
    return app


def _sessions(request: Request) -> Sessions:
    return request.app.state.sessions


SessionsOfTheApp = Annotated[Sessions, Depends(_sessions)]


# A stream route's success, documented as the union its events' data take; `_event_streams`
# moves it under the stream's media type.
_STREAMED: dict[int | str, dict[str, Any]] = {
    200: {
        "model": StreamEvent,
        "description": "Server-Sent Events; each event's data is one StreamEvent, named by `event`",
    }
}


def _errors(*codes: ResponseErrorCode) -> dict[int | str, dict[str, Any]]:
    """A route's error responses: each status it can answer with, described by its codes, and
    `internal_error`, which any route can give."""
    by_status: dict[int, list[str]] = {}
    for code in (*codes, "internal_error"):
        by_status.setdefault(_STATUS[code], []).append(f"`{code}`")
    return {
        status: {"model": ApiError, "description": " or ".join(described)}
        for status, described in by_status.items()
    }


@router.post(
    "/sessions",
    responses=_STREAMED
    | _errors("invalid_request", "input_too_long", "too_many_sessions", "too_many_sessions_today"),
)
async def post_session(
    body: StartRequest, request: Request, sessions: SessionsOfTheApp
) -> Response:
    """Start a session under a new id and stream it to the pause, or to the report of a request
    that does not run."""
    connection = None if request.client is None else request.client.host
    forwarded_for = request.headers.getlist("x-forwarded-for")
    client = client_address(sessions.limit.trusted_proxy_hops, connection, forwarded_for)
    events = runs.start(sessions, str(uuid4()), body.input, client)
    if isinstance(events, TooManySessions):
        error = too_many_sessions_error(whole_minutes(events.wait))
        return JSONResponse(error.model_dump(), status_code=_STATUS["too_many_sessions"])
    return _streamed(events, sessions.keep_alive_seconds)


@router.post(
    "/sessions/{session_id}/answers",
    responses=_STREAMED
    | _errors(
        "session_not_found",
        "session_running",
        "session_not_paused",
        "invalid_answers",
        "invalid_request",
        "reply_too_long",
    ),
)
async def post_answers(
    session_id: str, body: AnswersRequest, sessions: SessionsOfTheApp
) -> Response:
    """Resume a paused session with the answers and the reply, or with neither for "skip all",
    and stream the reading of the reply and what it gave, the progress per agent and then the
    report."""
    events = await runs.answer(sessions, session_id, body)
    return _streamed(events, sessions.keep_alive_seconds)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionView,
    responses=_errors("session_not_found", "invalid_request"),
)
async def get_session(session_id: str, sessions: SessionsOfTheApp) -> SessionView | JSONResponse:
    """The session as it is now, so a client that lost its stream can find it again."""
    view = await runs.view(sessions, session_id)
    return _refused(view) if isinstance(view, str) else view


@router.post(
    "/sessions/{session_id}/recalculate",
    response_model=Recalculation,
    responses=_errors(
        "session_not_found",
        "no_report_yet",
        "no_options",
        "unknown_option",
        "invalid_assumptions",
        "invalid_request",
    ),
)
async def post_recalculate(
    session_id: str, body: RecalculateRequest, sessions: SessionsOfTheApp
) -> Recalculation | JSONResponse:
    """The report recalculated with the complete assumptions given: no agent runs and nothing
    is saved, so the report keeps its own."""
    recalculation = await recalculated(sessions.graph, session_id, body)
    return _refused(recalculation) if isinstance(recalculation, str) else recalculation


@router.get("/health")
async def health(sessions: SessionsOfTheApp) -> Health:
    """Liveness check for deployment, and whether the runs are traced, for the page's notice."""
    return Health(tracing=sessions.tracing)


def _streamed(events: Events | FixedRefusalCode, keep_alive_seconds: float) -> Response:
    """The run's events as a stream, or the code it was refused with before it started."""
    if isinstance(events, str):
        return _refused(events)
    return StreamingResponse(
        runs.stream(events, keep_alive_seconds),
        media_type=EVENT_STREAM,
        headers={"Cache-Control": "no-cache"},
    )


def _event_streams(build: Callable[[], dict[str, Any]]) -> Callable[[], dict[str, Any]]:
    """The app's OpenAPI schema with each success documented as a `StreamEvent` under the
    stream's media type: FastAPI documents a response model under application/json only."""

    def openapi() -> dict[str, Any]:
        schema = build()
        for path in schema["paths"].values():
            for operation in path.values():
                success = operation["responses"].get("200", {})
                content = success.get("content", {})
                if content.get(JSON, {}).get("schema") == {"$ref": _STREAM_EVENT_REF}:
                    success["content"] = {EVENT_STREAM: content[JSON]}
        return schema

    return openapi


def _refused(code: FixedResponseErrorCode) -> JSONResponse:
    return JSONResponse(api_error(code).model_dump(), status_code=_STATUS[code])


async def _invalid_request(request: Request, error: Exception) -> JSONResponse:
    """A body FastAPI's own validation rejects; its `detail` is left out, since it quotes the
    input."""
    return _refused("invalid_request")


def _internal_error_guard(app: ASGIApp) -> ASGIApp:
    """The app, answering anything a route raises with `internal_error` and logging it by its
    class only. Nothing is raised on to the server, whose own log would hold the traceback; an
    error once a response has started only ends it."""

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return
        started = False

        async def sending(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await app(scope, receive, sending)
        except Exception as error:
            session_id = scope.get("path_params", {}).get("session_id")
            log_error(error, "internal_error", session_id, None)
            if not started:
                await _refused("internal_error")(scope, receive, send)

    return guarded
