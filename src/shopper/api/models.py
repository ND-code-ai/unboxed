"""What the API takes and gives: request bodies, the events of a stream, the views of a session
and the error body. The events and views carry their lines beside the data, built as the API
answers (docs/adr/0008-api-sends-finished-lines.md)."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, RootModel, WithJsonSchema, model_validator

from shopper import wording
from shopper.agents.supervisor.agent import MAX_INPUT_CHARACTERS
from shopper.config import (
    RECALCULATE_HORIZON_YEARS,
    RECALCULATE_LIFESPAN_YEARS,
    RECALCULATE_USES_PER_YEAR,
)
from shopper.graph.graph import ProgressStatus
from shopper.graph.sessions import (
    FinishedSession,
    InterruptedSession,
    PausedSession,
    ReplyRead,
    ReplyUnanswered,
    SavedSession,
    SessionStart,
)
from shopper.lines import (
    SessionLines,
    box_label_line,
    reply_lines,
    session_lines,
    understood_line,
)
from shopper.report_lines import ReportLines, report_lines_of
from shopper.state import (
    Agent,
    Answer,
    AnswerStatus,
    Assumptions,
    Comparison,
    DecisionFactor,
    DomainModel,
    EvidenceSummary,
    Report,
    Request,
)
from shopper.wording import Line

# The codes a request is refused with before its stream starts, or instead of its answer, whose
# message is fixed.
FixedRefusalCode = Literal[
    "session_not_found",
    "session_running",
    "session_not_paused",
    "invalid_answers",
    "invalid_request",
    "input_too_long",
    "reply_too_long",
    "no_report_yet",
    "no_options",
    "unknown_option",
    "invalid_assumptions",
    "too_many_sessions_today",
]
# Every code a request is refused with; the message of `too_many_sessions` holds the wait.
RefusalCode = Literal[FixedRefusalCode, "too_many_sessions"]
# The code of anything unexpected before a stream starts, such as a database error.
UnexpectedCode = Literal["internal_error"]
# The codes of a response that is not a success.
ResponseErrorCode = RefusalCode | UnexpectedCode
# The codes whose message `api_error` gives.
FixedResponseErrorCode = FixedRefusalCode | UnexpectedCode
# The codes of a run that ended once its stream had started: the first two leave the session
# interrupted, the reply's two leave it paused.
RunErrorCode = Literal["model_call_failed", "run_stopped", "reply_unread", "reply_unanswered"]
# Which work of an agent a progress event is about: the brief agent researches the category and
# reads the reply; every other agent's work is research.
ProgressStep = Literal["research", "reply"]
# A text the supervisor's limit applies to: published as its `maxLength` for the page, and not
# enforced here, so a longer one is refused with its own code (`input_too_long`, `reply_too_long`).
CappedText = Annotated[str, WithJsonSchema({"type": "string", "maxLength": MAX_INPUT_CHARACTERS})]


def _bounded[T](low: T, high: T) -> WithJsonSchema:
    """A number's bounds, published as its `minimum` and `maximum` for the page; not enforced
    here, so a number outside them is refused with `invalid_assumptions`."""
    if isinstance(low, int) and isinstance(high, int):
        return WithJsonSchema({"type": "integer", "minimum": low, "maximum": high})
    return WithJsonSchema({"type": "number", "minimum": float(low), "maximum": float(high)})


def _capped(code: RefusalCode) -> str:
    """A capped text's description, which the page's generated types carry as its comment."""
    return f"At most {MAX_INPUT_CHARACTERS} characters (`maxLength`); a longer one is `{code}`."


class StartRequest(DomainModel):
    """The input: one text that may hold a need, a product URL and a budget."""

    input: CappedText = Field(description=_capped("input_too_long"))


class GivenAnswer(DomainModel):
    """An answer the user picked: a choice, or "not sure", which has none."""

    factor_id: str
    status: Literal["chosen", "not_sure"]
    choice_id: str | None = None

    @model_validator(mode="after")
    def _choice_matches_status(self) -> Self:
        if (self.choice_id is None) == (self.status == "chosen"):
            raise ValueError("a chosen answer has a choice, a not-sure answer none")
        return self


class AnswersRequest(DomainModel):
    """The user's answers and their reply in their own words, which a blank one is not; no
    answers and no reply is "skip all"."""

    answers: tuple[GivenAnswer, ...] = ()
    reply: CappedText | None = Field(default=None, description=_capped("reply_too_long"))


class RecalculateRequest(DomainModel):
    """The complete assumptions to recalculate a report with, not a change to them: the horizon,
    the uses per year (none when not known) and a lifespan for any of its options."""

    horizon_years: Annotated[int, _bounded(*RECALCULATE_HORIZON_YEARS)]
    uses_per_year: Annotated[int, _bounded(*RECALCULATE_USES_PER_YEAR)] | None
    lifespan_overrides: dict[
        str, Annotated[Decimal, Field(allow_inf_nan=False), _bounded(*RECALCULATE_LIFESPAN_YEARS)]
    ]


def given_answers(body: AnswersRequest) -> tuple[Answer, ...]:
    """The answers the user picked, as the session functions take them."""
    return tuple(
        Answer(
            factor_id=given.factor_id, status=AnswerStatus(given.status), choice_id=given.choice_id
        )
        for given in body.answers
    )


class ApiError(DomainModel):
    """The body of every response that is not a success."""

    code: ResponseErrorCode
    message: str


def api_error(code: FixedResponseErrorCode) -> ApiError:
    return ApiError(code=code, message=wording.ERRORS[code])


def too_many_sessions_error(minutes: int) -> ApiError:
    """`too_many_sessions`, with the whole minutes until a session can start."""
    return ApiError(code="too_many_sessions", message=wording.too_many_sessions(minutes))


class Health(DomainModel):
    """The API is up, and whether it traces its runs, so the page can say what is logged."""

    status: Literal["ok"] = "ok"
    tracing: bool


class RunningSession(DomainModel):
    """A session with a run going in this process; only the API knows."""

    status: Literal["running"] = "running"


class PausedSessionView(DomainModel):
    """A saved session waiting for the user's answers, with the lines of its `session` event."""

    status: Literal["paused"] = "paused"
    session: SessionStart
    lines: SessionLines


class FinishedSessionView(DomainModel):
    """A saved session that holds its report, with the lines of a `report` event."""

    status: Literal["finished"] = "finished"
    report: Report
    lines: ReportLines


class SessionView(
    RootModel[
        Annotated[
            RunningSession | PausedSessionView | FinishedSessionView | InterruptedSession,
            Field(discriminator="status"),
        ]
    ]
):
    """A session as it is now: running, or else as it is saved. An interrupted session is
    final: the page offers to start again with the text kept."""

    model_config = ConfigDict(frozen=True)


class Recalculation(DomainModel):
    """A report recalculated with other assumptions: the assumptions used, the new comparison
    and evidence summary, and beside them the lines of what changed with them, the evidence
    summary and the options. Nothing of it is saved."""

    assumptions: Assumptions
    comparison: Comparison
    evidence_summary: EvidenceSummary
    lines: ReportLines


def saved_view(saved: SavedSession) -> SessionView:
    """A saved session as the API sends it: paused or finished with its lines."""
    if isinstance(saved, PausedSession):
        lines = session_lines(saved.session)
        return SessionView(PausedSessionView(session=saved.session, lines=lines))
    if isinstance(saved, FinishedSession):
        lines = report_lines_of(saved.report)
        return SessionView(FinishedSessionView(report=saved.report, lines=lines))
    return SessionView(saved)


# --- The events of a stream; `event` names each on its `event:` line and in its data ---


class SessionStartedEvent(DomainModel):
    event: Literal["session_started"] = "session_started"
    session_id: str


class UnderstoodEvent(DomainModel):
    """The request, once it is known to run, the line that shows it, and the same words as the
    page's box carries them on its first label."""

    event: Literal["understood"] = "understood"
    request: Request
    line: Line
    label: Line


class ProgressEvent(DomainModel):
    event: Literal["progress"] = "progress"
    agent: Agent
    status: ProgressStatus
    step: ProgressStep
    message: str


class ReplyReadEvent(DomainModel):
    """What the reply gave once it is read, before any agent runs: its answers that count, the
    factors of the user's own it adds, whether it asked to change the request, and whether it
    answered only what a choice picked or the request already answers; then its lines for the
    thread."""

    event: Literal["reply_read"] = "reply_read"
    stated_answers: tuple[Answer, ...]
    factors: tuple[DecisionFactor, ...]
    asks_to_change_request: bool
    answered_already: bool
    lines: tuple[Line, ...]


class SessionEvent(DomainModel):
    """The session at the pause, or with its report for a request that does not run, and its
    lines."""

    event: Literal["session"] = "session"
    session: SessionStart
    lines: SessionLines


class ReportEvent(DomainModel):
    event: Literal["report"] = "report"
    report: Report
    lines: ReportLines


class ErrorEvent(DomainModel):
    """A run that ended without its last event once its stream had started."""

    event: Literal["error"] = "error"
    code: RunErrorCode
    message: str


# Any event of a stream, as a run sends it.
Event = (
    SessionStartedEvent
    | UnderstoodEvent
    | ProgressEvent
    | ReplyReadEvent
    | SessionEvent
    | ReportEvent
    | ErrorEvent
)


class StreamEvent(RootModel[Annotated[Event, Field(discriminator="event")]]):
    """The data of one event of a stream, named for the OpenAPI schema the frontend's types are
    generated from."""

    model_config = ConfigDict(frozen=True)


def progress_event(
    agent: Agent, status: ProgressStatus, step: ProgressStep = "research"
) -> ProgressEvent:
    """An agent starting or finishing its step, with its line from wording.py."""
    started = status is ProgressStatus.STARTED
    if step == "reply":
        message = wording.READING_REPLY if started else wording.FINISHED_READING_REPLY
    else:
        message = (wording.STARTED if started else wording.FINISHED)[agent]
    return ProgressEvent(agent=agent, status=status, step=step, message=message)


def understood_event(request: Request) -> UnderstoodEvent:
    return UnderstoodEvent(
        request=request, line=understood_line(request), label=box_label_line(request)
    )


def session_event(session: SessionStart) -> SessionEvent:
    return SessionEvent(session=session, lines=session_lines(session))


def reply_read_event(
    read: ReplyRead, request: Request, factors: Sequence[DecisionFactor]
) -> ReplyReadEvent:
    """What the reply gave, as the stream sends it: its answers that count as `stated_answers`,
    and its lines, which name the paused session's factors and those the reply adds."""
    return ReplyReadEvent(
        stated_answers=read.answers,
        factors=read.factors,
        asks_to_change_request=read.asks_to_change_request,
        answered_already=read.answered_already,
        lines=reply_lines(read, request, factors),
    )


def report_event(report: Report) -> ReportEvent:
    return ReportEvent(report=report, lines=report_lines_of(report))


def error_event(code: RunErrorCode) -> ErrorEvent:
    return ErrorEvent(code=code, message=wording.ERRORS[code])


def reply_unanswered_event(unanswered: ReplyUnanswered) -> ErrorEvent:
    """`reply_unanswered`, worded for a session with questions or with none."""
    message = wording.reply_unanswered(has_questions=unanswered.has_questions)
    return ErrorEvent(code="reply_unanswered", message=message)
