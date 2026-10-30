"""The assembled graph, end to end on a fake model and the stub agents, through its entry points.

What a saved session reads back as, the sessions and answers that cannot be resumed, and resuming
with a reply are in test_sessions.py; what both files share is in graph_runs.py.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from graph_runs import (
    AGENT_NAMES,
    CENT,
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
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from fakes import UNUSED_SOURCES, answering_search_service, counted, extraction, fake_chat
from shopper.agents.bundle import AgentBundle, BriefOutput, TcoOutput
from shopper.agents.stubs import OIL_FACTOR, STUB_AGENTS
from shopper.config import SearchPurpose
from shopper.graph.graph import ProgressStatus, build_graph, memory_checkpointer
from shopper.graph.sessions import (
    PausedSession,
    SessionStart,
    read_session,
    resume_session,
    start_session,
)
from shopper.llm import ChatModel
from shopper.state import (
    Agent,
    Answer,
    AnswerStatus,
    Caveat,
    CaveatCode,
    CheckItem,
    CheckReason,
    DecisionFactor,
    EvidenceSummary,
    Figure,
    ProductOption,
    Question,
    Report,
    Request,
    Scope,
    TrailEntry,
    TrailKind,
    Warning,
    WarningCode,
)
from shopper.tools.brief_store import BriefStore
from shopper.tools.fixtures import fixture_page_service
from shopper.tools.results import FailureKind, PageFetch, PageRequest, SearchOutcome, WebSearch
from shopper.tools.sources import Sources, fixture_sources
from shopper.tools.usage import USAGE_LOGGER


def saved(graph: CompiledStateGraph, session: SessionStart) -> StateSnapshot:
    """The session's state as the checkpointer reloads it."""
    return graph.get_state(thread(session.session_id))


def both_answered(usage: Question, hob: Question) -> tuple[Answer, ...]:
    return (chosen(usage, "About once a week"), chosen(hob, "Induction"))


def hob_not_sure(usage: Question, hob: Question) -> tuple[Answer, ...]:
    return (chosen(usage, "About once a week"), not_sure(hob))


def all_skipped(usage: Question, hob: Question) -> tuple[Answer, ...]:
    return ()


THREE_RESUMES = pytest.mark.parametrize("answers_for", [both_answered, hob_not_sure, all_skipped])
AnswersFor = Callable[[Question, Question], tuple[Answer, ...]]


def resumed(answers_for: AnswersFor) -> tuple[Report, Question]:
    """The frying pan session resumed with these answers; also the hob question, for its factor."""
    graph, _ = graph_with(FRYING_PAN_REPLY)
    session = start(graph)
    hob, usage = session.questions
    return resume(graph, session, *answers_for(usage, hob)), hob


def test_starting_a_session_returns_the_request_and_no_report() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)

    session = start(graph)

    assert session.session_id
    assert session.request.original_text == FRYING_PAN
    assert session.request.category == "frying pan"
    assert session.request.scope is Scope.TUNED
    assert session.request.budget == Decimal("50")
    assert session.warnings == ()
    assert session.report is None


def test_a_session_is_saved_under_the_id_its_caller_gave() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)

    session = asyncio.run(start_session(graph, "session-1", FRYING_PAN))

    assert session.session_id == "session-1"
    assert asyncio.run(read_session(graph, "session-1")) == PausedSession(session=session)


def test_the_stubs_call_no_model() -> None:
    graph, requests = graph_with(FRYING_PAN_REPLY)

    resume(graph, start(graph))

    assert len(requests) == 1


def test_starting_a_session_returns_the_factors_the_questions_are_drawn_from() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)

    session = start(graph)

    asked = {question.factor_id for question in session.questions}
    assert asked <= {factor.id for factor in session.factors}
    # A recurring cost is not asked about.
    assert [factor.name for factor in session.factors] == [
        "Hob compatibility",
        "Seasoning oil",
        "Usage frequency",
    ]


# --- What was understood, before category research starts ---


def test_what_was_understood_is_given_before_category_research_starts() -> None:
    events: list[str] = []

    async def noting_brief(
        request: Request,
        linked_product: ProductOption | None,
        chat: ChatModel,
        search: WebSearch,
        store: BriefStore,
    ) -> BriefOutput:
        events.append("brief runs")
        return await STUB_AGENTS.brief(request, linked_product, chat, search, store)

    graph, _ = graph_with(FRYING_PAN_REPLY, agents=replace(STUB_AGENTS, brief=noting_brief))

    asyncio.run(
        start_session(
            graph, uuid4().hex, FRYING_PAN, lambda request: events.append(str(request.category))
        )
    )

    assert events == ["frying pan", "brief runs"]


def test_a_request_that_does_not_run_is_never_given_as_understood() -> None:
    understood: list[Request] = []
    graph, _ = graph_with(extraction("pizza", "not_a_product"))

    asyncio.run(start_session(graph, uuid4().hex, "a pizza", understood.append))

    assert understood == []


def test_a_pasted_link_is_given_as_understood_once_its_page_named_the_category(
    tmp_path: Path,
) -> None:
    understood: list[Request] = []
    graph, _ = link_graph(
        tmp_path, extraction(None, "unclear"), extraction("frying pan", "tuned"), PAGE_DETAILS
    )

    asyncio.run(start_session(graph, uuid4().hex, PAN_LINK, understood.append))

    assert [request.category for request in understood] == ["frying pan"]


# --- Progress ---

STARTED = ProgressStatus.STARTED
FINISHED = ProgressStatus.FINISHED
Event = tuple[Agent, ProgressStatus]


def noting(events: list[Event]) -> Callable[[Agent, ProgressStatus], None]:
    return lambda agent, status: events.append((agent, status))


def test_starting_a_session_reports_the_supervisor_and_the_brief() -> None:
    events: list[Event] = []
    graph, _ = graph_with(FRYING_PAN_REPLY)

    asyncio.run(start_session(graph, uuid4().hex, FRYING_PAN, progress=noting(events)))

    assert events == [(Agent.SUPERVISOR, STARTED), (Agent.BRIEF, STARTED), (Agent.BRIEF, FINISHED)]


def test_resuming_reports_each_agent_after_the_pause_and_the_supervisor_finishing() -> None:
    events: list[Event] = []
    graph, _ = graph_with(FRYING_PAN_REPLY)
    session = start(graph)

    asyncio.run(resume_session(graph, session.session_id, (), progress=noting(events)))

    tco, parallel, last = events[:2], events[2:6], events[6:]
    assert tco == [(Agent.TCO, STARTED), (Agent.TCO, FINISHED)]
    # The LCA and second-hand agents run at once.
    assert sorted(parallel) == sorted(
        [
            (Agent.LCA, STARTED),
            (Agent.LCA, FINISHED),
            (Agent.SECOND_HAND, STARTED),
            (Agent.SECOND_HAND, FINISHED),
        ]
    )
    assert last == [(Agent.SUPERVISOR, FINISHED)]


def test_a_request_that_does_not_run_reports_only_the_supervisor() -> None:
    events: list[Event] = []
    graph, _ = graph_with(extraction("pizza", "not_a_product"))

    asyncio.run(start_session(graph, uuid4().hex, "a pizza", progress=noting(events)))

    assert events == [(Agent.SUPERVISOR, STARTED), (Agent.SUPERVISOR, FINISHED)]


def test_reading_a_pasted_link_reports_the_supervisor_once(tmp_path: Path) -> None:
    events: list[Event] = []
    graph, _ = link_graph(tmp_path, extraction("frying pan", "tuned"), PAGE_DETAILS)

    asyncio.run(start_session(graph, uuid4().hex, PAN_LINK, progress=noting(events)))

    assert events == [(Agent.SUPERVISOR, STARTED), (Agent.BRIEF, STARTED), (Agent.BRIEF, FINISHED)]


# --- Credits ---


def test_each_agent_that_searches_logs_the_credits_of_its_analysis_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    outcomes: dict[str, list[list[SearchOutcome]]] = {}
    chat, _ = fake_chat([FRYING_PAN_REPLY, FRYING_PAN_REPLY])
    sources = Sources(
        search=answering_search_service(datetime(2026, 10, 13, tzinfo=UTC)),
        fetch_page=UNUSED_SOURCES.fetch_page,
        cache_folder=tmp_path,
    )
    # Each search costs one credit; the second session's searches come from the cache.
    graph = build_graph(chat, memory_checkpointer(), sources, searching(STUB_AGENTS, 2, outcomes))

    with caplog.at_level(logging.INFO, logger=USAGE_LOGGER):
        resume(graph, start(graph))
        resume(graph, start(graph))

    assert [record.getMessage() for record in caplog.records if record.name == USAGE_LOGGER] == [
        "tavily credits used by brief: 2",
        "tavily credits used by tco: 2",
        "firecrawl credits used by tco: 0",
        "tavily credits used by brief: 0",
        "tavily credits used by tco: 0",
        "firecrawl credits used by tco: 0",
    ]


def test_reading_a_pasted_link_logs_its_credits(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    graph, _ = link_graph(tmp_path, extraction("frying pan", "tuned"), PAGE_DETAILS)

    with caplog.at_level(logging.INFO, logger=USAGE_LOGGER):
        start(graph, PAN_LINK)

    usage = [record.getMessage() for record in caplog.records if record.name == USAGE_LOGGER]
    assert usage[0] == "firecrawl credits used by supervisor: 1"


# --- Resuming with the answers ---


@THREE_RESUMES
def test_every_resume_gives_the_figures_of_the_worked_example(answers_for: AnswersFor) -> None:
    report, _ = resumed(answers_for)

    assert_worked_example(report)


@THREE_RESUMES
def test_every_resume_gives_a_trail_with_the_supervisor_and_every_stub(
    answers_for: AnswersFor,
) -> None:
    report, _ = resumed(answers_for)

    supervisor, *stubs = report.trail
    assert supervisor.agent is Agent.SUPERVISOR
    assert sorted(entry.agent for entry in stubs) == sorted(
        [Agent.BRIEF, Agent.TCO, Agent.LCA, Agent.SECOND_HAND]
    )
    for entry in stubs:
        assert entry.kind is TrailKind.DECIDED
        assert entry.summary.startswith("Stub:")
        assert entry.model_tier is None
        assert entry.model is None


@pytest.mark.parametrize("answers_for", [both_answered, hob_not_sure])
def test_a_chosen_usage_gives_the_worked_examples_cost_per_use(answers_for: AnswersFor) -> None:
    report, _ = resumed(answers_for)

    assert report.assumptions.uses_per_year == 50
    assert row(report, "Non-stick pan").cost_per_use == Decimal("0.20")
    assert row(report, "Carbon steel pan").cost_per_use.quantize(CENT) == Decimal("0.03")


def test_skipping_every_answer_gives_no_cost_per_use() -> None:
    report, _ = resumed(all_skipped)

    assert [answer.status for answer in report.answers] == [AnswerStatus.SKIPPED] * 2
    assert report.assumptions.uses_per_year is None
    for name in ("Non-stick pan", "Carbon steel pan"):
        assert row(report, name).cost_per_use is None
        assert Figure.COST_PER_USE in row(report, name).missing_reasons


def test_both_questions_answered_leaves_one_unverified_item_per_option() -> None:
    report, hob = resumed(both_answered)

    first, second = report.options
    assert report.check_before_you_buy == (
        CheckItem(factor_id=hob.factor_id, option_id=first.id, reason=CheckReason.UNVERIFIED),
        CheckItem(factor_id=hob.factor_id, option_id=second.id, reason=CheckReason.UNVERIFIED),
        OIL_NOT_KNOWN,
        *prices_to_confirm(report),
    )


# The stub's recurring cost is not asked about, so it is always on the list as not yet known.
OIL_NOT_KNOWN = CheckItem(factor_id=OIL_FACTOR.id, reason=CheckReason.UNANSWERED)


def prices_to_confirm(report: Report) -> tuple[CheckItem, ...]:
    """The stub options are priced, so each has its price to confirm."""
    return tuple(
        CheckItem(option_id=option.id, reason=CheckReason.PRICE) for option in report.options
    )


@pytest.mark.parametrize("answers_for", [hob_not_sure, all_skipped])
def test_an_open_hob_question_leaves_one_unanswered_item(answers_for: AnswersFor) -> None:
    report, hob = resumed(answers_for)

    assert report.check_before_you_buy == (
        CheckItem(factor_id=hob.factor_id, reason=CheckReason.UNANSWERED),
        OIL_NOT_KNOWN,
        *prices_to_confirm(report),
    )


def test_the_evidence_summary_counts_two_estimated_lifespans_and_two_missing_footprints() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)

    report = resume(graph, start(graph))

    assert report.evidence_summary == EvidenceSummary(lifespans_estimated=2, footprints_missing=2)
    assert report.lca_results == ()
    assert report.listings == ()


# --- Requests that do not run ---


@pytest.mark.parametrize(
    ("text", "reply", "scope"),
    [
        ("a pizza", extraction("pizza", "not_a_product"), Scope.NOT_A_PRODUCT),
        ("asdf qwer", extraction(None, "unclear"), Scope.UNCLEAR),
        (
            "a frying pan and a spatula",
            extraction(None, "several_products"),
            Scope.SEVERAL_PRODUCTS,
        ),
    ],
    ids=["declined", "unclear", "several products"],
)
def test_a_request_that_does_not_run_is_a_report_with_no_pause(
    text: str, reply: str, scope: Scope
) -> None:
    graph, _ = graph_with(reply)

    session = start(graph, text)

    report = session.report
    assert report is not None
    assert report.request.scope is scope
    assert [entry.agent for entry in report.trail] == [Agent.SUPERVISOR]
    assert report == Report(request=session.request, trail=report.trail, warnings=report.warnings)
    assert session.questions == ()


# --- Caveats and warnings ---


def test_a_fridge_report_carries_the_energy_caveat() -> None:
    graph, _ = graph_with(extraction("fridge", "energy_heavy"))

    report = resume(graph, start(graph, "a fridge"))

    assert report.caveats == (Caveat(code=CaveatCode.ENERGY_HEAVY),)


def test_a_budget_warning_is_in_the_state_at_the_pause_and_on_the_report() -> None:
    graph, _ = graph_with(extraction("frying pan", "tuned", "5o euro"))

    session = start(graph, "a frying pan, budget 5o euro")
    paused = saved(graph, session)
    report = resume(graph, session)

    assert [warning.code for warning in session.warnings] == [WarningCode.BUDGET_UNREADABLE]
    assert tuple(paused.values["warnings"]) == session.warnings
    assert report.warnings == session.warnings
    assert report.request.budget is None


def test_a_budget_below_every_option_adds_the_nothing_within_budget_warning() -> None:
    graph, _ = graph_with(extraction("frying pan", "tuned", "10 euro", 10))

    session = start(graph, "a frying pan, budget 10 euro")
    report = resume(graph, session)

    (warning,) = report.warnings
    assert warning.code is WarningCode.NOTHING_WITHIN_BUDGET
    assert warning.message == "Nothing found within €10; the cheapest option is €20."
    assert session.warnings == ()
    assert row(report, "Non-stick pan").within_budget is False
    assert row(report, "Carbon steel pan").within_budget is False


def test_a_budget_of_30_marks_the_40_option_over_budget_without_a_warning() -> None:
    graph, _ = graph_with(extraction("frying pan", "tuned", "30 euro", 30))

    report = resume(graph, start(graph, "a frying pan, budget 30 euro"))

    assert row(report, "Non-stick pan").within_budget is True
    assert row(report, "Carbon steel pan").within_budget is False
    assert report.warnings == ()


# --- A brief with no questions ---


def test_a_brief_with_no_questions_still_pauses_and_resumes_with_no_answers() -> None:
    agents = replace(STUB_AGENTS, brief=brief_without_questions)
    graph, _ = graph_with(FRYING_PAN_REPLY, agents=agents)

    session = start(graph)
    report = resume(graph, session)

    assert session.report is None
    assert session.questions == ()
    assert_worked_example(report)
    assert report.answers == ()
    assert report.check_before_you_buy == prices_to_confirm(report)


async def brief_with_usage_stated(
    request: Request,
    linked_product: ProductOption | None,
    chat: ChatModel,
    search: WebSearch,
    store: BriefStore,
) -> BriefOutput:
    stub = await STUB_AGENTS.brief(request, linked_product, chat, search, store)
    hob, usage = stub.questions
    stated = Answer(
        factor_id=usage.factor_id,
        status=AnswerStatus.STATED,
        stated_value="every day",
        stated_phrase="I cook every day",
        uses_per_year=365,
    )
    return stub.model_copy(update={"questions": (hob,), "stated_answers": (stated,)})


def test_a_stated_usage_answer_reaches_the_assumptions() -> None:
    agents = replace(STUB_AGENTS, brief=brief_with_usage_stated)
    graph, _ = graph_with(FRYING_PAN_REPLY, agents=agents)

    session = start(graph)
    (hob,) = session.questions
    report = resume(graph, session, chosen(hob, "Induction"))

    assert report.assumptions.uses_per_year == 365
    assert [answer.status for answer in report.answers] == [
        AnswerStatus.STATED,
        AnswerStatus.CHOSEN,
    ]
    # €10.00 a year over 365 uses.
    assert row(report, "Non-stick pan").cost_per_use.quantize(Decimal("0.0001")) == Decimal(
        "0.0274"
    )


# --- What each agent is given ---


# Where each agent that searches is given its web search.
SEARCH_POSITION = {"brief": 3, "tco": 7}


def searching(
    agents: AgentBundle, searches: int, outcomes: dict[str, list[list[SearchOutcome]]]
) -> AgentBundle:
    """The same agents, each searching first for `searches` different search queries."""

    def wrap(name: str) -> Callable[..., Awaitable[object]]:
        async def agent(*given: object) -> object:
            search = given[SEARCH_POSITION[name]]
            assert callable(search)
            found = [
                await search(f"{name} search {number}", SearchPurpose.CATEGORY)
                for number in range(searches)
            ]
            outcomes.setdefault(name, []).append(found)
            return await getattr(agents, name)(*given)

        return agent

    return replace(agents, **{name: wrap(name) for name in SEARCH_POSITION})


@pytest.mark.parametrize(("name", "limit"), [("brief", 3), ("tco", 14)])
def test_each_agent_gets_a_fresh_search_limited_to_its_calls_per_analysis(
    tmp_path: Path, name: str, limit: int
) -> None:
    outcomes: dict[str, list[list[SearchOutcome]]] = {}
    chat, _ = fake_chat([FRYING_PAN_REPLY, FRYING_PAN_REPLY])
    sources = Sources(
        search=answering_search_service(datetime(2026, 10, 13, tzinfo=UTC)),
        fetch_page=UNUSED_SOURCES.fetch_page,
        cache_folder=tmp_path,
    )
    graph = build_graph(
        chat, memory_checkpointer(), sources, searching(STUB_AGENTS, limit + 1, outcomes)
    )

    resume(graph, start(graph))
    # A second session reruns every node; the cache answers its searches.
    resume(graph, start(graph))

    first, second = outcomes[name]
    assert [outcome.failure for outcome in first] == [None] * limit + [FailureKind.LIMIT_REACHED]
    assert [outcome.from_cache for outcome in second[:limit]] == [True] * limit
    assert second[limit].failure is None


def test_each_agent_is_given_the_request_and_what_the_agents_before_it_produced() -> None:
    seen: dict[str, tuple[object, ...]] = {}
    chat, _ = fake_chat([FRYING_PAN_REPLY])
    graph = build_graph(chat, memory_checkpointer(), UNUSED_SOURCES, recording(STUB_AGENTS, seen))
    session = start(graph)
    hob, usage = session.questions
    answers = (chosen(hob, "Induction"), chosen(usage, "About once a week"))

    report = resume(graph, session, *answers)

    assert len(report.options) == 2
    assert seen["brief"][:3] == (session.request, None, chat)
    # The stub brief finds no local category term. Its one phrased question is asked, so the
    # questions option research is given are the ones asked.
    assert seen["tco"][:7] == (
        session.request,
        None,
        None,
        session.factors,
        session.questions,
        answers,
        chat,
    )
    assert seen["lca"] == (report.options, chat)
    assert seen["second_hand"] == (session.request, answers, report.options, chat)


async def brief_with_a_local_term(
    request: Request,
    linked_product: ProductOption | None,
    chat: ChatModel,
    search: WebSearch,
    store: BriefStore,
) -> BriefOutput:
    stub = await STUB_AGENTS.brief(request, linked_product, chat, search, store)
    return stub.model_copy(update={"local_term": "koekenpan"})


def test_the_local_category_term_of_category_research_reaches_option_research() -> None:
    seen: dict[str, tuple[object, ...]] = {}
    agents = recording(replace(STUB_AGENTS, brief=brief_with_a_local_term), seen)
    chat, _ = fake_chat([FRYING_PAN_REPLY])
    graph = build_graph(chat, memory_checkpointer(), UNUSED_SOURCES, agents)

    resume(graph, start(graph))

    assert seen["tco"][2] == "koekenpan"


def warning(agents: AgentBundle) -> AgentBundle:
    """The same agents, each adding one warning that names it."""

    def wrap(name: str) -> Callable[..., Awaitable[object]]:
        async def agent(*given: object) -> object:
            output = await getattr(agents, name)(*given)
            # No agent has a warning code of its own yet, so any code will do.
            added = Warning(code=WarningCode.BUDGET_UNREADABLE, message=f"from {name}")
            return output.model_copy(update={"warnings": (added,)})

        return agent

    return replace(agents, **{name: wrap(name) for name in AGENT_NAMES})


def test_the_warnings_and_trail_entries_of_every_agent_reach_the_report() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY, agents=warning(STUB_AGENTS))

    report = resume(graph, start(graph))

    assert sorted(warning.message for warning in report.warnings) == [
        "from brief",
        "from lca",
        "from second_hand",
        "from tco",
    ]
    assert sorted(entry.agent for entry in report.trail) == sorted(
        [Agent.SUPERVISOR, Agent.BRIEF, Agent.TCO, Agent.LCA, Agent.SECOND_HAND]
    )


async def tco_without_options(
    request: Request,
    linked_product: ProductOption | None,
    local_term: str | None,
    factors: Sequence[DecisionFactor],
    questions: Sequence[Question],
    answers: Sequence[Answer],
    chat: ChatModel,
    search: WebSearch,
    fetch: PageFetch,
) -> TcoOutput:
    return TcoOutput()


def test_a_report_with_no_options_has_no_comparison() -> None:
    agents = replace(STUB_AGENTS, tco=tco_without_options)
    graph, _ = graph_with(FRYING_PAN_REPLY, agents=agents)
    session = start(graph)
    hob, usage = session.questions

    report = resume(graph, session, chosen(usage, "About once a week"), chosen(hob, "Induction"))

    assert report.options == ()
    assert report.comparison is None
    assert report.evidence_summary == EvidenceSummary()
    assert report.warnings == ()
    assert report.check_before_you_buy == (OIL_NOT_KNOWN,)
    assert len(report.answers) == 2


# --- What is saved ---


def test_the_state_reloaded_after_a_pause_holds_model_instances() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)

    session = start(graph)
    values = saved(graph, session).values

    assert values["request"] == session.request
    assert type(values["request"]) is Request
    assert tuple(values["questions"]) == session.questions
    assert all(type(question) is Question for question in values["questions"])
    assert all(type(factor) is DecisionFactor for factor in values["factors"])
    assert all(type(entry) is TrailEntry for entry in values["trail"])
    assert "report" not in values


def test_the_report_saved_at_the_end_equals_the_one_returned() -> None:
    graph, _ = graph_with(FRYING_PAN_REPLY)
    session = start(graph)
    hob, usage = session.questions

    report = resume(graph, session, chosen(usage, "About once a week"), chosen(hob, "Induction"))
    finished = saved(graph, session)

    assert type(finished.values["report"]) is Report
    assert finished.values["report"] == report


# --- A pasted link ---

FIXTURES = Path(__file__).parent.parent / "fixtures"
PAN_LINK = "https://example.org/shop/de-buyer-mineral-b-28"
BLOCKED_LINK = "https://example.org/shop/blocked"
PAGE_DETAILS = json.dumps(
    {
        "materials": [{"name": "carbon steel", "form": None}],
        "weight_amount": 2.1,
        "weight_unit": "kg",
    }
)


def link_graph(
    cache: Path, *replies: str | Exception, agents: AgentBundle = STUB_AGENTS
) -> tuple[CompiledStateGraph, list[PageRequest]]:
    """A graph on the recorded pages, noting each page request that reached the service."""
    chat, _ = fake_chat(replies)
    fetch_page, fetched = counted(fixture_page_service(FIXTURES))
    sources = replace(fixture_sources(FIXTURES, cache), fetch_page=fetch_page)
    return build_graph(chat, memory_checkpointer(), sources, agents), fetched


@pytest.mark.parametrize(
    ("link", "replies", "given"),
    [
        (PAN_LINK, (PAGE_DETAILS,), "De Buyer Mineral B koekenpan 28 cm"),
        (BLOCKED_LINK, (), None),
    ],
    ids=["a link that was read", "a link that could not be read"],
)
def test_the_brief_agent_is_given_the_linked_product_only_when_the_link_was_read(
    tmp_path: Path, link: str, replies: tuple[str, ...], given: str | None
) -> None:
    seen: dict[str, tuple[object, ...]] = {}
    agents = recording(STUB_AGENTS, seen)
    graph, _ = link_graph(tmp_path, extraction("frying pan", "tuned"), *replies, agents=agents)

    start(graph, f"{link} a frying pan")

    linked_product = seen["brief"][1]
    assert getattr(linked_product, "name", None) == given


def test_a_pasted_link_becomes_the_first_option_on_the_report(tmp_path: Path) -> None:
    graph, _ = link_graph(tmp_path, extraction("frying pan", "tuned"), PAGE_DETAILS)

    report = resume(graph, start(graph, f"{PAN_LINK} budget 60 euro"))

    linked, *others = report.options
    assert linked.name == "De Buyer Mineral B koekenpan 28 cm"
    assert linked.price == Decimal("54.95")
    assert linked.link == PAN_LINK
    assert linked.weight_kg == Decimal("2.1")
    assert [option.name for option in others] == ["Non-stick pan", "Carbon steel pan"]
    assert any(entry.option_id == linked.id for entry in report.comparison.rows)


def test_a_second_session_with_the_same_link_makes_no_network_call(tmp_path: Path) -> None:
    replies = (extraction("frying pan", "tuned"), PAGE_DETAILS)
    first, first_fetched = link_graph(tmp_path, *replies)
    second, second_fetched = link_graph(tmp_path, *replies)

    start(first, PAN_LINK)
    session = start(second, PAN_LINK)

    assert len(first_fetched) == 1
    assert second_fetched == []
    assert saved(second, session).values["linked_product"].name == (
        "De Buyer Mineral B koekenpan 28 cm"
    )


def test_a_link_with_no_category_takes_it_from_the_product_name(tmp_path: Path) -> None:
    graph, _ = link_graph(
        tmp_path, extraction(None, "unclear"), extraction("frying pan", "tuned"), PAGE_DETAILS
    )

    session = start(graph, PAN_LINK)

    assert session.request.category == "frying pan"
    assert session.request.scope is Scope.TUNED
    assert session.report is None
    assert session.questions


def test_an_unreadable_link_with_a_category_continues_with_its_warning(tmp_path: Path) -> None:
    graph, _ = link_graph(tmp_path, extraction("frying pan", "tuned"))

    session = start(graph, f"{BLOCKED_LINK} a frying pan")
    report = resume(graph, session)

    assert [warning.code for warning in session.warnings] == [WarningCode.LINK_UNREADABLE]
    assert [warning.code for warning in report.warnings] == [WarningCode.LINK_UNREADABLE]
    assert [option.name for option in report.options] == ["Non-stick pan", "Carbon steel pan"]


def test_an_unreadable_link_with_no_category_ends_the_session(tmp_path: Path) -> None:
    graph, _ = link_graph(tmp_path, extraction(None, "general"))

    session = start(graph, BLOCKED_LINK)

    assert session.request.scope is Scope.UNCLEAR
    assert session.request.product_url == BLOCKED_LINK
    assert session.questions == ()
    assert session.report is not None
    assert session.report.options == ()


def test_a_link_in_a_request_that_is_declined_is_not_fetched() -> None:
    # UNUSED_SOURCES fails the test on any page fetch.
    graph, _ = graph_with(extraction("car", "not_a_product"))

    session = start(graph, f"{PAN_LINK} I want this car")

    assert session.report is not None
