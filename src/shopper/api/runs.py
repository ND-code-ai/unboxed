"""Runs of the graph, each an asyncio task, and the streams that read their events.

A run is never the response's own generator, so it finishes when its client disconnects; the
stream reads the run's events from a queue (docs/service_architecture.md, "API surface").
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

from shopper.agents.bundle import AgentBundle, ReplyUnreadError
from shopper.agents.supervisor.agent import ModelCallError, input_too_long
from shopper.api.error_log import log_error
from shopper.api.limits import StartLimit, TooManySessions, admitted
from shopper.api.models import (
    AnswersRequest,
    Event,
    FixedRefusalCode,
    ProgressStep,
    RunErrorCode,
    RunningSession,
    SessionStartedEvent,
    SessionView,
    error_event,
    given_answers,
    progress_event,
    reply_read_event,
    reply_unanswered_event,
    report_event,
    saved_view,
    session_event,
    understood_event,
)
from shopper.graph.graph import Progress, ProgressStatus
from shopper.graph.sessions import (
    InvalidAnswersError,
    ReplyUnanswered,
    SessionNotFoundError,
    SessionNotPausedError,
    check_resume,
    read_session,
    resume_with_reply,
    start_session,
)
from shopper.llm import ChatModel
from shopper.state import Agent, Answer, Request
from shopper.tools.results import Clock
from shopper.tracing import Tracer

# A run's events, and None once it has ended.
Events = asyncio.Queue[Event | None]
# An agent starting or finishing, as a run's progress callback was given it.
AgentProgress = tuple[Agent, ProgressStatus]
# A run's progress callback: an agent starting or finishing a step of its work.
StepProgress = Callable[[Agent, ProgressStatus, ProgressStep], None]

KEEP_ALIVE = ": keep-alive\n\n"


@dataclass(frozen=True)
class Sessions:
    """The graph and the sessions running in this process.

    `running` is the lock per session: a session in it has a run going, or its answers are being
    checked before one starts (no task yet). One worker process, so one list. `trace` sets the
    tracing context of each run, so LangSmith never traces because the environment asks it to.
    `chat` and `agents` are the graph's model client and bundle, for reading a reply before the
    graph resumes. `limit` counts the sessions each client starts, by the `clock`. `tracing` says
    whether `trace` sends anything, which the page asks to show its notice.
    """

    graph: CompiledStateGraph
    keep_alive_seconds: float
    trace: Tracer
    running: dict[str, asyncio.Task[None] | None]
    chat: ChatModel
    agents: AgentBundle
    limit: StartLimit
    clock: Clock
    tracing: bool


def start(
    sessions: Sessions, session_id: str, input: str, client: str
) -> Events | FixedRefusalCode | TooManySessions:
    """Start a new session's run, its id sent first; refused for input over the supervisor's
    limit, and then when the client has started as many as the limit in the last hour or anyone
    as many as the ceiling in the last day. A session counts once it is started, a declined one
    too, since it spends a model call."""
    if input_too_long(input):
        return "input_too_long"
    refused = admitted(sessions.limit, client, sessions.clock())
    if refused is not None:
        return refused
    events: Events = asyncio.Queue()
    events.put_nowait(SessionStartedEvent(session_id=session_id))

    def understood(request: Request) -> None:
        events.put_nowait(understood_event(request))

    async def run(progress: StepProgress) -> Event:
        started = start_session(
            sessions.graph, session_id, input, understood=understood, progress=_research(progress)
        )
        return session_event(await started)

    _run_task(sessions, session_id, events, input, run)
    return events


async def answer(
    sessions: Sessions, session_id: str, body: AnswersRequest
) -> Events | FixedRefusalCode:
    """Resume a paused session with the answers and the reply, read first; no answers and no
    reply is "skip all".

    Refused before a run starts for a reply over the supervisor's limit, then when the session is
    running, unknown or not paused, or when the answers do not fit its questions. The slot is
    taken before the saved state is checked, since the check waits on the database and a second
    request may come in meanwhile. A reply that cannot be read, or that answers nothing when no
    answer was picked, ends the run with its code and leaves the session paused.
    """
    reply = body.reply or ""
    if input_too_long(reply):
        return "reply_too_long"
    if session_id in sessions.running:
        return "session_running"
    answers = given_answers(body)
    sessions.running[session_id] = None
    try:
        refused = await _refused_resume(sessions.graph, session_id, answers)
    except BaseException:
        del sessions.running[session_id]
        raise
    if refused is not None:
        del sessions.running[session_id]
        return refused
    events: Events = asyncio.Queue()

    async def run(progress: StepProgress) -> Event:
        resumed = await resume_with_reply(
            sessions.graph,
            session_id,
            answers,
            reply,
            sessions.chat,
            sessions.agents,
            _research(progress),
            reading=lambda status: progress(Agent.BRIEF, status, "reply"),
            replied=lambda read, request, factors: events.put_nowait(
                reply_read_event(read, request, factors)
            ),
        )
        if isinstance(resumed, ReplyUnanswered):
            return reply_unanswered_event(resumed)
        return report_event(resumed.report)

    _run_task(sessions, session_id, events, body.model_dump_json(exclude_none=True), run)
    return events


async def view(sessions: Sessions, session_id: str) -> SessionView | FixedRefusalCode:
    """The session as it is now: running when it is in the running list, otherwise as it is
    saved; not found for an unknown id, an expired one included."""
    if session_id in sessions.running:
        return SessionView(RunningSession())
    saved = await read_session(sessions.graph, session_id)
    return "session_not_found" if saved is None else saved_view(saved)


async def _refused_resume(
    graph: CompiledStateGraph, session_id: str, answers: Sequence[Answer]
) -> FixedRefusalCode | None:
    """The code resuming the session with these answers is refused with; none when it can run."""
    try:
        await check_resume(graph, session_id, answers)
    except SessionNotFoundError:
        return "session_not_found"
    except SessionNotPausedError:
        return "session_not_paused"
    except InvalidAnswersError:
        return "invalid_answers"
    return None


def _research(progress: StepProgress) -> Progress:
    """The graph's progress callback: every agent's work in the graph is research."""
    return lambda agent, status: progress(agent, status, "research")


def _progress_to(events: Events, seen: list[AgentProgress]) -> StepProgress:
    """The progress callback that sends each agent starting and finishing a step as an event,
    and keeps it in `seen` for the log of a run that stops."""

    def sent(agent: Agent, status: ProgressStatus, step: ProgressStep) -> None:
        seen.append((agent, status))
        events.put_nowait(progress_event(agent, status, step))

    return sent


def _agent_at_stop(seen: Sequence[AgentProgress]) -> Agent | None:
    """The agent a run stopped in: the last one that started and had not finished."""
    finished = {agent for agent, status in seen if status is ProgressStatus.FINISHED}
    running = [
        agent
        for agent, status in seen
        if status is ProgressStatus.STARTED and agent not in finished
    ]
    return running[-1] if running else None


async def _traced(trace: Tracer, input_text: str, run: Awaitable[Event]) -> Event:
    """The run, traced as one trace of its own under the input it was given; inside its task, so
    the tracing context is the task's."""
    with trace(input_text):
        return await run


def _run_task(
    sessions: Sessions,
    session_id: str,
    events: Events,
    trace_input: str,
    run: Callable[[StepProgress], Awaitable[Event]],
) -> None:
    """Run in a task that holds the session's slot until it ends, its progress sent as events
    and kept for the log of a run that stops, and traced under `trace_input`."""
    seen: list[AgentProgress] = []
    traced = _traced(sessions.trace, trace_input, run(_progress_to(events, seen)))
    task = asyncio.create_task(_run_in_slot(sessions, session_id, traced, events, seen))
    sessions.running[session_id] = task


async def _run_in_slot(
    sessions: Sessions,
    session_id: str,
    run: Awaitable[Event],
    events: Events,
    seen: Sequence[AgentProgress],
) -> None:
    """Run to the end, sending its last event or the code it stopped with, then free the slot
    and end the events."""
    try:
        events.put_nowait(await run)
    except Exception as error:
        code = _stop_code(error)
        log_error(error, code, session_id, _agent_at_stop(seen))
        events.put_nowait(error_event(code))
    finally:
        del sessions.running[session_id]
        events.put_nowait(None)


def _stop_code(error: Exception) -> RunErrorCode:
    """The code a run that raised ends with."""
    if isinstance(error, ModelCallError):
        return "model_call_failed"
    if isinstance(error, ReplyUnreadError):
        return "reply_unread"
    return "run_stopped"


async def stream(events: Events, keep_alive_seconds: float) -> AsyncIterator[str]:
    """The run's events as Server-Sent Events, with a keep-alive comment whenever nothing came
    for the interval."""
    while True:
        try:
            event = await asyncio.wait_for(events.get(), keep_alive_seconds)
        except TimeoutError:
            yield KEEP_ALIVE
            continue
        if event is None:
            return
        yield f"event: {event.event}\ndata: {event.model_dump_json()}\n\n"
