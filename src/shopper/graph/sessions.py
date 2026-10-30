"""The sessions the graph runs, each saved under its id: starting one, reading it or its report
back, checking a resume before it runs, and resuming it with the answers or with the user's
reply.

The entry points take every session function, what they return and the session errors from here;
graph.py builds the graph they run. Rules: docs/architecture/sessions.md.
"""

from collections.abc import Callable, Sequence
from typing import Any, Literal

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, StateSnapshot
from pydantic import TypeAdapter, ValidationError

from shopper.agents.bundle import AgentBundle, ReplyOutput
from shopper.agents.default import DEFAULT_AGENTS
from shopper.graph.graph import (
    INTERVIEW,
    Progress,
    ProgressStatus,
    State,
    Understood,
    run_graph,
)
from shopper.graph.interview import answered_already, complete_answers, kept_from_reply, with_reply
from shopper.llm import ChatModel
from shopper.state import (
    Answer,
    DecisionFactor,
    DomainModel,
    InterviewAnswers,
    Question,
    Report,
    Request,
    Warning,
)

_STATE = TypeAdapter(State)


class SessionStart(DomainModel):
    """What a new session returns: the questions with the decision factors they are drawn from
    and the answers the request states, or the report for a request that does not run."""

    session_id: str
    request: Request
    warnings: tuple[Warning, ...] = ()
    factors: tuple[DecisionFactor, ...] = ()
    questions: tuple[Question, ...] = ()
    stated_answers: tuple[Answer, ...] = ()
    report: Report | None = None


class PausedSession(DomainModel):
    """A saved session waiting for the user's answers."""

    status: Literal["paused"] = "paused"
    session: SessionStart


class FinishedSession(DomainModel):
    """A saved session that holds its report."""

    status: Literal["finished"] = "finished"
    report: Report


class InterruptedSession(DomainModel):
    """A saved session that neither waits for answers nor holds a report: its run stopped
    partway, on a restart or an unexpected exception, or its parsing call failed."""

    status: Literal["interrupted"] = "interrupted"
    code: Literal["run_stopped"] = "run_stopped"


# What reading a saved session gives.
SavedSession = PausedSession | FinishedSession | InterruptedSession


class SessionNotFoundError(Exception):
    """No session has this id."""


class SessionNotPausedError(Exception):
    """The session is not waiting for answers: it is finished, or its parsing call failed."""


class SessionHasNoReportError(Exception):
    """The session holds no report: it waits for answers, or its run stopped."""


class InvalidAnswersError(ValueError):
    """The answers do not fit the session's questions; a database error is never one."""


class ReplyRead(DomainModel):
    """What the reply gave, as it counts: its answers that count, the factors of the user's own
    it adds, and whether it asked to change the request, which a reply never does.

    `answered_already` says that it changed no answer because a choice picked or the request
    already answers all it answers; it changed none either when it answered nothing.
    `unanswered` says that no answer was picked and it gave none, so nothing is resumed.
    """

    answers: tuple[Answer, ...] = ()
    factors: tuple[DecisionFactor, ...] = ()
    asks_to_change_request: bool = False
    answered_already: bool = False
    unanswered: bool = False


class ResumedWithReply(DomainModel):
    """A session resumed with the user's answers and their reply: what the reply gave, and the
    report."""

    status: Literal["resumed"] = "resumed"
    reply: ReplyRead
    report: Report


class ReplyUnanswered(DomainModel):
    """No answer was picked and the reply gave none: nothing was resumed, and the session is
    still paused. `has_questions` says whether it paused with questions to answer."""

    status: Literal["unanswered"] = "unanswered"
    reply: ReplyRead
    has_questions: bool


# The reading of the reply starting or finishing.
Reading = Callable[[ProgressStatus], None]
# What the reply gave, once it is read, with the paused session's request and decision factors.
Replied = Callable[[ReplyRead, Request, tuple[DecisionFactor, ...]], None]


async def start_session(
    graph: CompiledStateGraph,
    session_id: str,
    input: str,
    understood: Understood | None = None,
    progress: Progress | None = None,
) -> SessionStart:
    """Start a new session and run it up to the pause, or to the report when nothing runs.

    `session_id` is a new id the caller made, so it knows the session even when the start
    raises. `understood` is called with the request once it is known to run, before category
    research starts, so the caller can show it while the research runs. `progress` is called as
    each agent starts and finishes. Raises the supervisor's InputTooLongError and ModelCallError
    unchanged; no report exists then.
    """
    config = _config(session_id)
    await run_graph(graph, {"input": input}, config, understood, progress)
    return _session_start(session_id, (await graph.aget_state(config)).values)


async def read_session(graph: CompiledStateGraph, session_id: str) -> SavedSession | None:
    """The saved session: paused, finished with its report, or interrupted; missing for an
    unknown id. Whether a run is going on now only the caller knows."""
    saved = await _saved_state(graph, session_id)
    if saved is None:
        return None
    snapshot, values = saved
    if _waits_for_answers(snapshot):
        return PausedSession(session=_session_start(session_id, values))
    if "report" in values:
        return FinishedSession(report=values["report"])
    return InterruptedSession()


async def read_report(graph: CompiledStateGraph, session_id: str) -> Report:
    """The saved session's report. Raises SessionNotFoundError for an unknown id and
    SessionHasNoReportError for a session that is paused or interrupted."""
    saved = await read_session(graph, session_id)
    if saved is None:
        raise SessionNotFoundError(session_id)
    if not isinstance(saved, FinishedSession):
        raise SessionHasNoReportError(session_id)
    return saved.report


async def _saved_state(
    graph: CompiledStateGraph, session_id: str
) -> tuple[StateSnapshot, State] | None:
    """The session's snapshot and its state, valid under today's models; missing when nothing is
    saved under the id, or when a model changed after it was saved.

    The checkpointer gives such a model back built without validation, so the state is checked
    here, through its plain values.
    """
    snapshot = await graph.aget_state(_config(session_id))
    if snapshot.created_at is None:
        return None
    try:
        return snapshot, _STATE.validate_python(_STATE.dump_python(snapshot.values))
    except ValidationError:
        return None


def _session_start(session_id: str, values: State) -> SessionStart:
    """What a session holds once it has paused, or finished without pausing."""
    return SessionStart(
        session_id=session_id,
        request=values["request"],
        warnings=tuple(values.get("warnings", ())),
        factors=tuple(values.get("factors", ())),
        questions=tuple(values.get("questions", ())),
        stated_answers=tuple(values.get("answers", ())),
        report=values.get("report"),
    )


def _waits_for_answers(snapshot: StateSnapshot) -> bool:
    """Waiting means the pending step is `interview` and it holds an interrupt."""
    return snapshot.next == (INTERVIEW,) and bool(snapshot.interrupts)


async def resume_session(
    graph: CompiledStateGraph,
    session_id: str,
    answers: Sequence[Answer],
    progress: Progress | None = None,
) -> Report:
    """Resume a paused session with the user's answers; none at all is "skip all".

    `progress` is called as each agent starts and finishes. Raises what `check_resume` raises,
    before the graph runs.
    """
    await check_resume(graph, session_id, answers)
    return await _resumed(graph, session_id, InterviewAnswers(given=tuple(answers)), progress)


async def resume_with_reply(
    graph: CompiledStateGraph,
    session_id: str,
    answers: Sequence[Answer],
    reply: str,
    chat: ChatModel,
    agents: AgentBundle = DEFAULT_AGENTS,
    progress: Progress | None = None,
    *,
    reading: Reading | None = None,
    replied: Replied | None = None,
) -> ResumedWithReply | ReplyUnanswered:
    """Resume a paused session with the user's answers and their reply, which the bundle's
    reader reads first with the saved factors, questions and stated answers. A blank reply is
    none; no answers and no reply is "skip all".

    Raises what `check_resume` raises, before the reply is read, and the reader's
    ReplyUnreadError. Then, and when no answer was picked and the reply gave none, nothing is
    resumed: the session stays paused and can be answered again.

    `reading` is called as the reading of a reply starts and as it finishes, and `replied` with
    what the reply gave once it is read, before any agent starts, so the caller can show it while
    the agents run; it is given the paused session's request and factors too, which the reply's
    lines name. `progress` is called as each agent after the pause starts and finishes.
    """
    values = await _paused_state(graph, session_id, answers)
    if not reply.strip():
        resume = InterviewAnswers(given=tuple(answers))
        report = await _resumed(graph, session_id, resume, progress)
        return ResumedWithReply(reply=ReplyRead(), report=report)
    questions, stated = values.get("questions", ()), values.get("answers", ())
    phrased = values.get("phrased_questions", ())
    request, factors = values["request"], tuple(values.get("factors", ()))
    _tell(reading, ProgressStatus.STARTED)
    read = await agents.reply(
        request, reply, factors, questions, phrased, stated, values.get("local_term"), chat
    )
    _tell(reading, ProgressStatus.FINISHED)
    if not answers and not read.answers and not read.factors:
        unanswered = _reply_read(read, (), unanswered=True)
        _tell(replied, unanswered, request, factors)
        return ReplyUnanswered(reply=unanswered, has_questions=bool(questions))
    resume = _checked(lambda: with_reply(questions, stated, answers, read, phrased))
    gave = _reply_read(read, kept_from_reply(questions, stated, answers, read, phrased))
    _tell(replied, gave, request, factors)
    report = await _resumed(graph, session_id, resume, progress)
    return ResumedWithReply(reply=gave, report=report)


def _tell[*Told](callback: Callable[[*Told], None] | None, *told: *Told) -> None:
    if callback is not None:
        callback(*told)


def _reply_read(
    read: ReplyOutput, kept: Sequence[Answer], *, unanswered: bool = False
) -> ReplyRead:
    """What the reply gave, with its answers that count."""
    return ReplyRead(
        answers=tuple(kept),
        factors=read.factors,
        asks_to_change_request=read.asks_to_change_request,
        answered_already=answered_already(read, kept),
        unanswered=unanswered,
    )


async def _resumed(
    graph: CompiledStateGraph,
    session_id: str,
    resume: InterviewAnswers,
    progress: Progress | None,
) -> Report:
    """Run the paused session from the interview to its report."""
    config = _config(session_id)
    await run_graph(graph, Command(resume=resume), config, None, progress)
    return (await graph.aget_state(config)).values["report"]


async def check_resume(
    graph: CompiledStateGraph, session_id: str, answers: Sequence[Answer]
) -> None:
    """Check that the session can be resumed with these answers, running nothing, so a caller
    can refuse before a run starts.

    Raises SessionNotFoundError for an unknown session or one that no longer loads,
    SessionNotPausedError for one that is not waiting for answers, and InvalidAnswersError for
    answers the caller may not give. The session stays paused after an InvalidAnswersError and can
    be resumed again.
    """
    await _paused_state(graph, session_id, answers)


async def _paused_state(
    graph: CompiledStateGraph, session_id: str, answers: Sequence[Answer]
) -> State:
    """The saved state of a session waiting for answers that these answers fit; raises as
    `check_resume` says.

    Checked before the graph runs: an answer the node rejected would be saved as its resume value
    and handed to it again on the next resume.
    """
    saved = await _saved_state(graph, session_id)
    if saved is None:
        raise SessionNotFoundError(session_id)
    snapshot, values = saved
    if not _waits_for_answers(snapshot):
        raise SessionNotPausedError(session_id)
    questions, stated = values.get("questions", ()), values.get("answers", ())
    _checked(lambda: complete_answers(questions, stated, answers))
    return values


def _checked[T](placing: Callable[[], T]) -> T:
    """What placing the answers gives; InvalidAnswersError for answers that do not fit."""
    try:
        return placing()
    except ValueError as error:
        raise InvalidAnswersError(str(error)) from error


def _config(session_id: str) -> dict[str, Any]:
    """The session id is the LangGraph thread id."""
    return {"configurable": {"thread_id": session_id}}
