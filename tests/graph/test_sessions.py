"""The saved sessions, through the session functions on the assembled graph with a fake model
and the stub agents: reading one back, checking a resume before it runs, the sessions and answers
that cannot be resumed, resuming with a reply, and the factors not asked.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

import aiosqlite
import pytest
from graph_runs import (
    FRYING_PAN,
    FRYING_PAN_REPLY,
    assert_worked_example,
    brief_without_questions,
    chosen,
    graph_with,
    not_sure,
    recording,
    resume,
    row,
    start,
    thread,
)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.state import CompiledStateGraph

from fakes import UNUSED_SOURCES, extraction, fake_chat
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
from shopper.agents.brief.agent import CARE_CHOICES
from shopper.agents.bundle import AgentBundle, BriefOutput, ReplyUnreadError, TcoOutput
from shopper.agents.stubs import STUB_AGENTS
from shopper.agents.supervisor.agent import ModelCallError
from shopper.graph.graph import (
    BRIEF,
    ProgressStatus,
    build_graph,
    memory_checkpointer,
    state_serde,
)
from shopper.graph.sessions import (
    FinishedSession,
    InterruptedSession,
    InvalidAnswersError,
    PausedSession,
    ReplyRead,
    ReplyUnanswered,
    ResumedWithReply,
    SessionNotFoundError,
    SessionNotPausedError,
    SessionStart,
    check_resume,
    read_session,
    resume_session,
    resume_with_reply,
    start_session,
)
from shopper.llm import ChatError, ChatModel, ChatRequest
from shopper.state import (
    Agent,
    Answer,
    AnswerStatus,
    CheckItem,
    CheckReason,
    DecisionFactor,
    FactorKind,
    ProductOption,
    Question,
    Report,
    Request,
    Source,
    SourceKind,
    StatedIn,
)
from shopper.tools.brief_store import BriefStore
from shopper.tools.results import WebSearch

# --- Reading a saved session ---


def on_file[T](
    database: Path,
    chat: ChatModel,
    step: Callable[[CompiledStateGraph], Awaitable[T]],
    agents: AgentBundle = STUB_AGENTS,
) -> T:
    """One step on a graph saved in the SQLite file, opened anew as a restarted process would."""

    async def run() -> T:
        async with aiosqlite.connect(database) as connection:
            saver = AsyncSqliteSaver(connection, serde=state_serde())
            return await step(build_graph(chat, saver, UNUSED_SOURCES, agents))

    return asyncio.run(run())


def test_a_session_saved_in_a_sqlite_file_reads_back_as_paused_and_then_as_finished(
    tmp_path: Path,
) -> None:
    database = tmp_path / "sessions.sqlite"
    chat, _ = fake_chat([FRYING_PAN_REPLY])

    session = on_file(database, chat, lambda graph: start_session(graph, "s-1", FRYING_PAN))
    paused = on_file(database, chat, lambda graph: read_session(graph, "s-1"))
    report = on_file(database, chat, lambda graph: resume_session(graph, "s-1", ()))
    finished = on_file(database, chat, lambda graph: read_session(graph, "s-1"))

    assert paused == PausedSession(session=session)
    assert session.questions
    assert finished == FinishedSession(report=report)
    assert_worked_example(report)


async def tco_that_stops(*given: object) -> TcoOutput:
    raise RuntimeError("the process went away")


def test_a_run_stopped_partway_reads_back_as_interrupted(tmp_path: Path) -> None:
    database = tmp_path / "sessions.sqlite"
    chat, _ = fake_chat([FRYING_PAN_REPLY])
    agents = replace(STUB_AGENTS, tco=tco_that_stops)
    on_file(database, chat, lambda graph: start_session(graph, "s-1", FRYING_PAN), agents)

    with pytest.raises(RuntimeError):
        on_file(database, chat, lambda graph: resume_session(graph, "s-1", ()), agents)
    read = on_file(database, chat, lambda graph: read_session(graph, "s-1"))

    assert read == InterruptedSession()
    assert read.code == "run_stopped"


def test_a_session_whose_parsing_call_failed_reads_back_as_interrupted() -> None:
    graph, _ = graph_with(ChatError("service down"))
    with pytest.raises(ModelCallError):
        asyncio.run(start_session(graph, "s-1", FRYING_PAN))

    assert asyncio.run(read_session(graph, "s-1")) == InterruptedSession()


def test_a_request_that_did_not_run_reads_back_as_finished_with_its_report() -> None:
    graph, _ = graph_with(extraction("pizza", "not_a_product"))
    session = asyncio.run(start_session(graph, "s-1", "a pizza"))

    assert asyncio.run(read_session(graph, "s-1")) == FinishedSession(report=session.report)


def test_an_unknown_session_reads_back_as_not_found() -> None:
    graph, _ = graph_with()

    assert asyncio.run(read_session(graph, "no-such-session")) is None


def saved_before_a_model_changed() -> tuple[CompiledStateGraph, SessionStart]:
    """A paused session whose request was saved before its scope was a field."""
    graph, _ = graph_with(FRYING_PAN_REPLY)
    session = start(graph)
    older = Request.model_construct(original_text=FRYING_PAN)
    asyncio.run(graph.aupdate_state(thread(session.session_id), {"request": older}, as_node=BRIEF))
    return graph, session


def test_a_session_saved_before_a_model_changed_reads_back_as_not_found() -> None:
    graph, session = saved_before_a_model_changed()

    assert asyncio.run(read_session(graph, session.session_id)) is None


def test_a_session_saved_before_a_model_changed_cannot_be_resumed() -> None:
    graph, session = saved_before_a_model_changed()

    with pytest.raises(SessionNotFoundError):
        resume(graph, session)


# --- Checking a resume before it runs ---


def check(graph: CompiledStateGraph, session_id: str, *answers: Answer) -> None:
    asyncio.run(check_resume(graph, session_id, answers))


def test_checking_a_resume_runs_nothing() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)
    session = start(graph)
    hob, _ = session.questions

    check(graph, session.session_id, chosen(hob, "Induction"))

    assert asyncio.run(read_session(graph, session.session_id)) == PausedSession(session=session)


def test_checking_a_resume_raises_what_resuming_would() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)
    session = start(graph)
    hob, _ = session.questions

    with pytest.raises(SessionNotFoundError):
        check(graph, "no-such-session")
    with pytest.raises(ValueError, match="same factor"):
        check(graph, session.session_id, chosen(hob, "Gas"), not_sure(hob))
    resume(graph, session)
    with pytest.raises(SessionNotPausedError):
        check(graph, session.session_id)


# --- Sessions that cannot be resumed ---


def test_resuming_an_unknown_session_raises_its_own_error() -> None:
    graph, _ = graph_with()

    with pytest.raises(SessionNotFoundError):
        asyncio.run(resume_session(graph, "no-such-session", ()))


def test_resuming_a_finished_session_raises_its_own_error() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)
    session = start(graph)
    resume(graph, session)

    with pytest.raises(SessionNotPausedError):
        resume(graph, session)


def test_a_request_that_did_not_run_cannot_be_resumed() -> None:
    graph, _ = graph_with(extraction("pizza", "not_a_product"))
    session = start(graph, "a pizza")

    with pytest.raises(SessionNotPausedError):
        resume(graph, session)


def test_a_failed_supervisor_call_raises_the_typed_error_and_no_report_exists() -> None:
    graph, requests = graph_with(ChatError("service down"))

    # The session is saved under the caller's id, so a failed start is not lost.
    with pytest.raises(ModelCallError):
        asyncio.run(start_session(graph, "session-1", FRYING_PAN))

    snapshot = graph.get_state(thread("session-1"))
    assert snapshot.created_at is not None
    assert "report" not in snapshot.values
    assert "request" not in snapshot.values
    assert len(requests) == 1

    with pytest.raises(SessionNotPausedError):
        asyncio.run(resume_session(graph, "session-1", ()))
    assert len(requests) == 1


# --- Answers the caller may not give ---


def bad_answers(usage: Question, hob: Question) -> dict[str, tuple[Answer, ...]]:
    return {
        "a factor with no question": (Answer(factor_id="none", status=AnswerStatus.NOT_SURE),),
        "a choice that is not on its question": (
            Answer(factor_id=hob.factor_id, status=AnswerStatus.CHOSEN, choice_id="choice-9"),
        ),
        "two answers for one factor": (chosen(hob, "Gas"), not_sure(hob)),
        "status skipped": (Answer(factor_id=hob.factor_id, status=AnswerStatus.SKIPPED),),
        "status stated": (
            Answer(
                factor_id=hob.factor_id,
                status=AnswerStatus.STATED,
                stated_value="induction",
                stated_phrase="for induction",
            ),
        ),
        "its own uses per year": (
            chosen(usage, "About once a week").model_copy(update={"uses_per_year": 9}),
        ),
    }


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("a factor with no question", "has no question"),
        ("a choice that is not on its question", "is not on question"),
        ("two answers for one factor", "same factor"),
        ("status skipped", "chosen or not sure"),
        ("status stated", "chosen or not sure"),
        ("its own uses per year", "uses per year"),
    ],
)
def test_answers_the_caller_may_not_give_raise_and_the_session_can_still_be_resumed(
    case: str, message: str
) -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)
    session = start(graph)
    hob, usage = session.questions

    with pytest.raises(ValueError, match=message):
        resume(graph, session, *bad_answers(usage, hob)[case])
    report = resume(graph, session, chosen(usage, "About once a week"), chosen(hob, "Induction"))

    assert row(report, "Non-stick pan").cost_per_use == Decimal("0.20")


# --- Resuming with a reply ---


class Replying(NamedTuple):
    """A graph on the fake model, with the model the reply is read by."""

    graph: CompiledStateGraph
    chat: ChatModel
    requests: list[ChatRequest]


def replying(*readings: str | Exception, agents: AgentBundle = REPLY_AGENTS) -> Replying:
    """The graph, whose model answers the supervisor and then each reading in turn."""
    chat, requests = fake_chat([FRYING_PAN_REPLY, *readings])
    return Replying(
        build_graph(chat, memory_checkpointer(), UNUSED_SOURCES, agents), chat, requests
    )


def reply_to(
    run: Replying,
    session: SessionStart,
    reply: str,
    *answers: Answer,
    agents: AgentBundle = REPLY_AGENTS,
) -> ResumedWithReply | ReplyUnanswered:
    return asyncio.run(
        resume_with_reply(run.graph, session.session_id, answers, reply, run.chat, agents)
    )


def resumed_with(result: ResumedWithReply | ReplyUnanswered) -> Report:
    assert isinstance(result, ResumedWithReply)
    return result.report


def ids(report: Report) -> list[tuple[str, str | None]]:
    return [(answer.factor_id, answer.choice_id) for answer in report.answers]


def trail_of(report: Report) -> list[tuple[str, str | None]]:
    return [(entry.summary, entry.reason) for entry in report.trail]


def test_a_session_answered_only_by_a_reply_matches_one_answered_with_those_choices() -> None:
    by_choice = replying()
    by_reply = replying(READ_INDUCTION_WEEKLY)
    chosen_session, replied_session = start(by_choice.graph), start(by_reply.graph)
    hob, usage = chosen_session.questions

    with_choices = resume(
        by_choice.graph,
        chosen_session,
        chosen(hob, "Induction"),
        chosen(usage, "About once a week"),
    )
    with_reply = resumed_with(reply_to(by_reply, replied_session, INDUCTION_WEEKLY))

    assert with_reply.options == with_choices.options
    assert with_reply.comparison == with_choices.comparison
    assert [factor.id for factor in with_reply.factors] == [f.id for f in with_choices.factors]
    assert (
        ids(with_reply)
        == ids(with_choices)
        == [
            (hob.factor_id, "choice-3"),
            (usage.factor_id, "about_once_a_week"),
        ]
    )
    assert with_reply.check_before_you_buy == with_choices.check_before_you_buy
    assert with_reply.assumptions.uses_per_year == 50


def test_the_replys_answers_are_stated_in_the_reply_and_it_is_read_once() -> None:
    run = replying(READ_INDUCTION_WEEKLY)
    session = start(run.graph)

    result = reply_to(run, session, INDUCTION_WEEKLY)

    assert isinstance(result, ResumedWithReply)
    assert [(a.status, a.stated_in) for a in result.report.answers] == [
        (AnswerStatus.STATED, StatedIn.REPLY)
    ] * 2
    assert result.reply.answers == result.report.answers
    assert len(run.requests) == 2
    assert (
        'Stated in the reply: "on induction" as Hob compatibility: Induction',
        "the reply states it",
    ) in trail_of(result.report)


def test_a_reply_that_names_nothing_without_a_choice_leaves_the_session_paused() -> None:
    run = replying(READ_NOTHING_NAMED)
    session = start(run.graph)

    result = reply_to(run, session, NOTHING_NAMED)

    assert result == ReplyUnanswered(reply=ReplyRead(unanswered=True), has_questions=True)
    assert asyncio.run(read_session(run.graph, session.session_id)) == PausedSession(
        session=session
    )
    assert_worked_example(resume(run.graph, session))


def test_a_reply_that_names_nothing_with_a_choice_runs_with_its_phrase_on_the_trail() -> None:
    run = replying(READ_NOTHING_NAMED)
    session = start(run.graph)
    hob, _ = session.questions

    report = resumed_with(reply_to(run, session, NOTHING_NAMED, chosen(hob, "Induction")))

    assert ids(report) == [(hob.factor_id, "choice-3"), ("usage-1", None)]
    assert (
        f'Ignored the requirement "{NOTHING_NAMED}" in the reply',
        "it holds the category",
    ) in trail_of(report)
    assert ("The reply changed no answer", "nothing in it answers a factor") in trail_of(report)


def test_a_reply_whose_answer_loses_to_a_choice_says_so_on_the_trail() -> None:
    run = replying(reading(said(STUB_HOB_NUMBER, "on induction", choice=3)))
    session = start(run.graph)
    hob, _ = session.questions

    report = resumed_with(reply_to(run, session, "on induction", chosen(hob, "Gas")))

    assert ids(report) == [(hob.factor_id, "choice-1"), ("usage-1", None)]
    assert (
        'Ignored the requirement "on induction" in the reply',
        "a choice picked answers it",
    ) in trail_of(report)
    assert (
        "The reply changed no answer",
        "a choice picked or the request answers all it answers",
    ) in trail_of(report)


def test_a_reply_beats_a_not_sure_picked() -> None:
    run = replying(reading(said(STUB_HOB_NUMBER, "on induction", choice=3)))
    session = start(run.graph)
    hob, _ = session.questions

    report = resumed_with(reply_to(run, session, "on induction", not_sure(hob)))

    (answer, _) = report.answers
    assert (answer.status, answer.choice_id, answer.stated_in) == (
        AnswerStatus.STATED,
        "choice-3",
        StatedIn.REPLY,
    )


def test_no_idea_which_hob_leaves_it_on_the_check_list() -> None:
    run = replying(reading(said(STUB_HOB_NUMBER, "no idea which hob", not_sure=True)))
    session = start(run.graph)
    hob, _ = session.questions

    report = resumed_with(reply_to(run, session, "no idea which hob"))

    assert report.answers[0] == Answer(
        factor_id=hob.factor_id,
        status=AnswerStatus.NOT_SURE,
        stated_phrase="no idea which hob",
        stated_in=StatedIn.REPLY,
    )
    assert CheckItem(factor_id=hob.factor_id, reason=CheckReason.UNANSWERED) in (
        report.check_before_you_buy
    )


def test_i_meant_a_wok_leaves_the_session_paused_and_says_it_asks_to_change_the_request() -> None:
    run = replying(reading(said("new", "I meant a wok", changes="category")))
    session = start(run.graph)

    result = reply_to(run, session, "I meant a wok")

    assert result == ReplyUnanswered(
        reply=ReplyRead(asks_to_change_request=True, unanswered=True), has_questions=True
    )
    assert asyncio.run(read_session(run.graph, session.session_id)) == PausedSession(
        session=session
    )


def test_make_it_40_with_a_choice_keeps_the_budget_and_says_it_asks_to_change_it() -> None:
    run = replying(reading(said("new", "make it €40", changes="budget")))
    session = start(run.graph)
    hob, _ = session.questions

    result = reply_to(run, session, "make it €40", chosen(hob, "Induction"))

    assert isinstance(result, ResumedWithReply)
    assert result.reply.asks_to_change_request is True
    assert result.report.request == session.request
    assert result.report.request.budget == Decimal("50")


def test_a_reply_adds_a_factor_of_the_users_own_before_usage() -> None:
    run = replying(reading(said("new", "oven safe")))
    session = start(run.graph)

    result = reply_to(run, session, "oven safe")

    assert isinstance(result, ResumedWithReply)
    report = result.report
    assert [factor.id for factor in report.factors] == [
        "researched-1",
        "researched-2",
        "user-1",
        "usage-1",
    ]
    assert [factor.id for factor in result.reply.factors] == ["user-1"]
    assert ids(report) == [("user-1", None), ("researched-1", None), ("usage-1", None)]
    assert [answer.status for answer in report.answers] == [
        AnswerStatus.STATED,
        AnswerStatus.SKIPPED,
        AnswerStatus.SKIPPED,
    ]


def test_a_session_with_no_questions_still_has_its_reply_read() -> None:
    agents = replace(REPLY_AGENTS, brief=brief_without_questions)
    run = replying(reading(said("new", "oven safe")), agents=agents)
    session = start(run.graph)

    report = resumed_with(reply_to(run, session, "oven safe", agents=agents))

    assert session.questions == ()
    assert [factor.id for factor in report.factors] == ["user-1"]
    assert ids(report) == [("user-1", None)]


def test_a_reply_to_no_questions_that_adds_nothing_says_the_session_had_none() -> None:
    agents = replace(REPLY_AGENTS, brief=brief_without_questions)
    run = replying(READ_NOTHING_NAMED, agents=agents)
    session = start(run.graph)

    result = reply_to(run, session, NOTHING_NAMED, agents=agents)

    assert result == ReplyUnanswered(reply=ReplyRead(unanswered=True), has_questions=False)


def test_a_failed_reading_leaves_the_session_paused_and_a_second_resume_works() -> None:
    failed = ChatError("service down")
    run = replying(failed, failed, READ_INDUCTION_WEEKLY)
    session = start(run.graph)

    with pytest.raises(ReplyUnreadError):
        reply_to(run, session, INDUCTION_WEEKLY)
    paused = asyncio.run(read_session(run.graph, session.session_id))
    report = resumed_with(reply_to(run, session, INDUCTION_WEEKLY))

    assert paused == PausedSession(session=session)
    assert report.assumptions.uses_per_year == 50


def test_a_blank_reply_is_none_and_is_not_read() -> None:
    run = replying()
    session = start(run.graph)
    hob, usage = session.questions

    result = reply_to(run, session, "  \n", chosen(hob, "Induction"), chosen(usage, "Every day"))

    assert result == ResumedWithReply(reply=ReplyRead(), report=resumed_with(result))
    assert len(run.requests) == 1
    assert resumed_with(result).assumptions.uses_per_year == 365


def test_choices_the_caller_may_not_give_raise_before_the_reply_is_read() -> None:
    run = replying(READ_INDUCTION_WEEKLY)
    session = start(run.graph)
    hob, _ = session.questions

    with pytest.raises(InvalidAnswersError, match="same factor"):
        reply_to(run, session, INDUCTION_WEEKLY, chosen(hob, "Gas"), not_sure(hob))

    assert len(run.requests) == 1


def test_the_stub_reader_reads_the_choices_a_reply_names_and_calls_no_model() -> None:
    run = replying(agents=STUB_AGENTS)
    session = start(run.graph)
    hob, _ = session.questions

    report = resumed_with(
        reply_to(run, session, INDUCTION_WEEKLY, chosen(hob, "Gas"), agents=STUB_AGENTS)
    )

    assert len(run.requests) == 1
    assert ids(report) == [(hob.factor_id, "choice-1"), ("usage-1", "about_once_a_week")]
    assert report.assumptions.uses_per_year == 50
    assert ("Stub: the reply is read for the choices it names", None) in trail_of(report)


Heard = list[tuple[str, object]]


def heard_while_replying(
    run: Replying, session: SessionStart, reply: str, *answers: Answer
) -> tuple[ResumedWithReply | ReplyUnanswered, Heard]:
    """The result, and each callback in the order it was called: the reading's progress, what
    the reply gave, and the agents' progress."""
    heard: Heard = []
    result = asyncio.run(
        resume_with_reply(
            run.graph,
            session.session_id,
            answers,
            reply,
            run.chat,
            REPLY_AGENTS,
            progress=lambda agent, status: heard.append((agent, status)),
            reading=lambda status: heard.append(("reading", status)),
            replied=lambda read, request, factors: heard.append(("replied", read)),
        )
    )
    return result, heard


def test_the_reading_and_what_the_reply_gave_are_told_before_any_agent_starts() -> None:
    run = replying(READ_INDUCTION_WEEKLY)
    session = start(run.graph)

    result, heard = heard_while_replying(run, session, INDUCTION_WEEKLY)

    assert isinstance(result, ResumedWithReply)
    assert heard[:4] == [
        ("reading", ProgressStatus.STARTED),
        ("reading", ProgressStatus.FINISHED),
        ("replied", result.reply),
        (Agent.TCO, ProgressStatus.STARTED),
    ]
    assert result.reply.answers == result.report.answers


def test_what_a_reply_that_answers_nothing_gave_is_told_and_nothing_runs() -> None:
    run = replying(reading(said("new", "I meant a wok", changes="category")))
    session = start(run.graph)

    result, heard = heard_while_replying(run, session, "I meant a wok")

    assert heard == [
        ("reading", ProgressStatus.STARTED),
        ("reading", ProgressStatus.FINISHED),
        ("replied", ReplyRead(asks_to_change_request=True, unanswered=True)),
    ]
    assert result == ReplyUnanswered(
        reply=ReplyRead(asks_to_change_request=True, unanswered=True), has_questions=True
    )


def test_what_the_reply_gave_is_told_with_the_paused_sessions_request_and_factors() -> None:
    run = replying(reading(said("new", "oven safe")))
    session = start(run.graph)
    told: list[tuple[object, ...]] = []

    asyncio.run(
        resume_with_reply(
            run.graph,
            session.session_id,
            (),
            "oven safe",
            run.chat,
            REPLY_AGENTS,
            replied=lambda read, request, factors: told.append((read.factors, request, factors)),
        )
    )

    ((added, request, factors),) = told
    assert [factor.id for factor in added] == ["user-1"]
    assert request == session.request
    assert factors == session.factors


def test_a_blank_reply_tells_of_no_reading() -> None:
    run = replying()
    session = start(run.graph)

    _, heard = heard_while_replying(run, session, " ")

    assert heard
    assert all(isinstance(each, Agent) for each, _ in heard)


def test_a_reply_that_answers_only_what_a_choice_answers_says_it_answered_already() -> None:
    run = replying(reading(said(STUB_HOB_NUMBER, "on induction", choice=3)))
    session = start(run.graph)
    hob, _ = session.questions

    result = reply_to(run, session, "on induction", chosen(hob, "Gas"))

    assert isinstance(result, ResumedWithReply)
    assert result.reply == ReplyRead(answered_already=True)


def test_a_reply_that_answers_nothing_did_not_answer_already() -> None:
    run = replying(READ_NOTHING_NAMED)
    session = start(run.graph)
    hob, _ = session.questions

    result = reply_to(run, session, NOTHING_NAMED, chosen(hob, "Induction"))

    assert isinstance(result, ResumedWithReply)
    assert result.reply == ReplyRead()


def test_a_paused_session_saved_in_a_sqlite_file_is_resumed_with_a_reply(
    tmp_path: Path,
) -> None:
    database = tmp_path / "sessions.sqlite"
    chat, _ = fake_chat([FRYING_PAN_REPLY, READ_NOTHING_NAMED, READ_INDUCTION_WEEKLY])

    def answering(reply: str) -> Callable[[CompiledStateGraph], Awaitable[object]]:
        return lambda graph: resume_with_reply(graph, "s-1", (), reply, chat, REPLY_AGENTS)

    session = on_file(database, chat, lambda graph: start_session(graph, "s-1", FRYING_PAN))
    unanswered = on_file(database, chat, answering(NOTHING_NAMED), REPLY_AGENTS)
    paused = on_file(database, chat, lambda graph: read_session(graph, "s-1"))
    resumed_on_file = on_file(database, chat, answering(INDUCTION_WEEKLY), REPLY_AGENTS)
    finished = on_file(database, chat, lambda graph: read_session(graph, "s-1"))

    assert isinstance(unanswered, ReplyUnanswered)
    assert paused == PausedSession(session=session)
    report = resumed_with(resumed_on_file)
    assert finished == FinishedSession(report=report)
    assert [answer.stated_in for answer in report.answers] == [StatedIn.REPLY] * 2


# --- Factors not asked ---

SEASONING = DecisionFactor(
    id="researched-2",
    name="Seasoning",
    kind=FactorKind.CARE,
    why="A carbon steel pan needs seasoning.",
    source=Source(kind=SourceKind.URL, reference="https://stub.invalid/seasoning"),
)
SEASONING_QUESTION = Question(
    id=f"question-{SEASONING.id}",
    factor_id=SEASONING.id,
    text="Some frying pans need seasoning before first use. Is that fine with you?",
    reason=SEASONING.why,
    choices=CARE_CHOICES,
)
# The reading numbers the factors of the brief below: the hob 1, seasoning 2, usage 3.
SEASONING_NUMBER = 2


async def brief_with_seasoning_not_asked(
    request: Request,
    linked_product: ProductOption | None,
    chat: ChatModel,
    search: WebSearch,
    store: BriefStore,
) -> BriefOutput:
    """The stub brief, with a care factor phrased and not asked."""
    stub = await STUB_AGENTS.brief(request, linked_product, chat, search, store)
    # The stub's recurring cost is left out, so the factors are numbered as below.
    hob, _, usage = stub.factors
    return stub.model_copy(
        update={
            "factors": (hob, SEASONING, usage),
            "phrased_questions": (*stub.phrased_questions, SEASONING_QUESTION),
        }
    )


def test_option_research_is_given_every_phrased_question_asked_or_not() -> None:
    seen: dict[str, tuple[object, ...]] = {}
    agents = recording(replace(STUB_AGENTS, brief=brief_with_seasoning_not_asked), seen)
    graph, _ = graph_with(FRYING_PAN_REPLY, agents=agents)
    session = start(graph)
    hob, usage = session.questions

    resume(graph, session)

    assert seen["tco"][4] == (hob, SEASONING_QUESTION, usage)


def test_a_reply_answers_a_factor_not_asked_before_the_questions_answers() -> None:
    agents = replace(REPLY_AGENTS, brief=brief_with_seasoning_not_asked)
    run = replying(reading(said(SEASONING_NUMBER, "not season it", choice=2)), agents=agents)
    session = start(run.graph)

    report = resumed_with(reply_to(run, session, "I'd rather not season it", agents=agents))

    assert ids(report) == [
        (SEASONING.id, "care-avoid"),
        ("researched-1", None),
        ("usage-1", None),
    ]
