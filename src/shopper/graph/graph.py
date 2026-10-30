"""LangGraph wiring, the graph state built from the domain models, and a run of the graph with
its progress events.

The entry points take `state_serde` for a saved checkpointer, `memory_checkpointer`,
`build_graph` and the progress types from here; starting, reading and resuming a session under its
id is in sessions.py, which runs the graph through `run_graph`. Rules:
docs/architecture/agents.md ("The graph") and docs/architecture/sessions.md.
"""

import logging
from collections.abc import Callable, Sequence
from enum import Enum, StrEnum
from functools import partial
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from shopper import state as domain
from shopper.agents.bundle import (
    AgentBundle,
    BriefAgent,
    LcaAgent,
    SecondHandAgent,
    TcoAgent,
)
from shopper.agents.default import DEFAULT_AGENTS
from shopper.agents.linked_product.agent import read_link
from shopper.agents.supervisor import agent as supervisor
from shopper.config import (
    BRIEF_SEARCH_LIMIT,
    PASTED_LINK_FETCH_LIMIT,
    TCO_FETCH_LIMIT,
    TCO_SEARCH_LIMIT,
)
from shopper.graph.interview import (
    complete_answers,
    every_question,
    uses_per_year,
    with_own_factors,
)
from shopper.graph.report import assemble
from shopper.llm import ChatModel
from shopper.state import (
    SCOPES_THAT_DO_NOT_RUN,
    Agent,
    Answer,
    Assumptions,
    DecisionFactor,
    InterviewAnswers,
    LcaResult,
    Listing,
    ProductOption,
    Question,
    Report,
    Request,
    Scope,
    TrailEntry,
    Warning,
)
from shopper.tools.brief_store import brief_store
from shopper.tools.product_page import page_view
from shopper.tools.results import Service
from shopper.tools.search import search_view
from shopper.tools.sources import Sources
from shopper.tools.usage import USAGE_LOGGER, metered

PARSE_REQUEST = "parse_request"
READ_LINK = "read_link"
BRIEF = "brief"
INTERVIEW = "interview"
TCO = "tco"
LCA = "lca"
SECOND_HAND = "second_hand"
ASSEMBLE_REPORT = "assemble_report"
_USAGE_LOG = logging.getLogger(USAGE_LOGGER)

# Called with the request once it is known to run, before category research starts.
Understood = Callable[[Request], None]


class ProgressStatus(StrEnum):
    STARTED = "started"
    FINISHED = "finished"


# Called as an agent starts and as it finishes.
Progress = Callable[[Agent, ProgressStatus], None]

# An agent has started when its first node starts and finished when its last node ends; the
# supervisor's three nodes report as one agent, and `interview` is no agent.
_AGENT_NODES = {
    BRIEF: Agent.BRIEF,
    TCO: Agent.TCO,
    LCA: Agent.LCA,
    SECOND_HAND: Agent.SECOND_HAND,
}
_FIRST_NODES = {PARSE_REQUEST: Agent.SUPERVISOR, **_AGENT_NODES}
_LAST_NODES = {ASSEMBLE_REPORT: Agent.SUPERVISOR, **_AGENT_NODES}


def _joined[T](left: Sequence[T], right: Sequence[T]) -> tuple[T, ...]:
    """The reducer for the keys that parallel nodes both write: a new tuple of both sides."""
    return (*left, *right)


class State(TypedDict, total=False):
    """The keys mirror the parts of a report. A key is absent until its node has run.

    A collection is a `Sequence`, not a tuple: LangGraph hands a tuple back as a list once the
    state has been saved and reloaded. `phrased_questions` holds every question category research
    phrased, asked or not; it is never on a report, and a session saved before it existed has
    none.
    """

    input: str
    request: Request
    linked_product: ProductOption
    local_term: str | None
    factors: Sequence[DecisionFactor]
    questions: Sequence[Question]
    phrased_questions: Sequence[Question]
    answers: Sequence[Answer]
    options: Sequence[ProductOption]
    lca_results: Sequence[LcaResult]
    listings: Sequence[Listing]
    assumptions: Assumptions
    trail: Annotated[Sequence[TrailEntry], _joined]
    warnings: Annotated[Sequence[Warning], _joined]
    report: Report


def state_serde() -> JsonPlusSerializer:
    """The serializer every checkpointer saves the state with: it restores the domain models and
    enums of state.py by class."""
    return JsonPlusSerializer(allowed_msgpack_modules=_state_classes())


def memory_checkpointer() -> InMemorySaver:
    """An in-memory checkpointer for one process: the CLI and the tests."""
    return InMemorySaver(serde=state_serde())


def build_graph(
    chat: ChatModel,
    checkpointer: BaseCheckpointSaver,
    sources: Sources,
    agents: AgentBundle = DEFAULT_AGENTS,
) -> CompiledStateGraph:
    """Build the graph once per process, with the model client and the sources bound to its nodes.

    A node makes its agent a freshly limited view of each tool every time it runs, so the calls
    are counted per invocation and not kept in the state.
    """
    builder = StateGraph(State)
    builder.add_node(PARSE_REQUEST, partial(_parse_request, chat=chat))
    builder.add_node(READ_LINK, partial(_read_link, chat=chat, sources=sources))
    builder.add_node(BRIEF, partial(_brief, agent=agents.brief, chat=chat, sources=sources))
    builder.add_node(INTERVIEW, _interview)
    builder.add_node(TCO, partial(_tco, agent=agents.tco, chat=chat, sources=sources))
    builder.add_node(LCA, partial(_lca, agent=agents.lca, chat=chat))
    builder.add_node(SECOND_HAND, partial(_second_hand, agent=agents.second_hand, chat=chat))
    builder.add_node(ASSEMBLE_REPORT, _assemble_report)

    builder.add_edge(START, PARSE_REQUEST)
    builder.add_conditional_edges(
        PARSE_REQUEST, _after_parsing, [READ_LINK, BRIEF, ASSEMBLE_REPORT]
    )
    builder.add_conditional_edges(READ_LINK, _after_reading_the_link, [BRIEF, ASSEMBLE_REPORT])
    builder.add_edge(BRIEF, INTERVIEW)
    builder.add_edge(INTERVIEW, TCO)
    builder.add_edge(TCO, LCA)
    builder.add_edge(TCO, SECOND_HAND)
    builder.add_edge([LCA, SECOND_HAND], ASSEMBLE_REPORT)
    builder.add_edge(ASSEMBLE_REPORT, END)
    return builder.compile(checkpointer=checkpointer)


async def run_graph(
    graph: CompiledStateGraph,
    start_or_resume: State | Command,
    config: dict[str, Any],
    understood: Understood | None,
    progress: Progress | None,
) -> None:
    """Run the graph from the input or the resume command to the pause or to the end, telling
    the callbacks as it goes. The sessions in sessions.py call it; the entry points do not."""
    async for mode, chunk in graph.astream(
        start_or_resume, config, stream_mode=["updates", "tasks"]
    ):
        if mode == "updates":
            request = _request_to_research(chunk)
            if request is not None and understood is not None:
                understood(request)
        elif progress is not None:
            event = _progress_event(chunk)
            if event is not None:
                progress(*event)


def _progress_event(task: dict[str, Any]) -> tuple[Agent, ProgressStatus] | None:
    """The agent a task event starts or finishes; missing for a node that neither starts nor ends
    an agent, and for a node that raised."""
    if "result" not in task:
        agent = _FIRST_NODES.get(task["name"])
        return None if agent is None else (agent, ProgressStatus.STARTED)
    agent = _LAST_NODES.get(task["name"])
    if agent is None or task["error"] is not None:
        return None
    return agent, ProgressStatus.FINISHED


def _request_to_research(update: dict[str, Any]) -> Request | None:
    """The request a node's update hands on to category research; missing for any other update."""
    routes = {PARSE_REQUEST: _after_parsing, READ_LINK: _after_reading_the_link}
    for node, written in update.items():
        if node in routes and routes[node]({"request": written["request"]}) == BRIEF:
            return written["request"]
    return None


def _phrased(values: State) -> Sequence[Question]:
    return values.get("phrased_questions", ())


def _state_classes() -> tuple[tuple[str, str], ...]:
    """Every domain model and enum in state.py, as the checkpointer's allow-list.

    Collected by code, because a class missing from the list comes back as a plain dict.
    """
    return tuple(
        (value.__module__, value.__qualname__)
        for value in vars(domain).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel | Enum)
        and value.__module__ == domain.__name__
    )


async def _parse_request(state: State, *, chat: ChatModel) -> State:
    parsed = await supervisor.parse_request(state["input"], chat)
    return {"request": parsed.request, "trail": parsed.trail, "warnings": parsed.warnings}


def _after_parsing(state: State) -> str:
    """A link is read first; a request that does not run goes straight to the report.

    An unclear request with a link is read too: the page can name the product the text did not.
    """
    request = state["request"]
    if request.product_url is not None and (
        request.scope is Scope.UNCLEAR or request.scope not in SCOPES_THAT_DO_NOT_RUN
    ):
        return READ_LINK
    return _after_reading_the_link(state)


async def _read_link(state: State, *, chat: ChatModel, sources: Sources) -> State:
    fetch, credits = metered(page_view(sources, PASTED_LINK_FETCH_LIMIT))
    output = await read_link(state["request"], chat, fetch)
    _log_usage(Agent.SUPERVISOR, Service.FIRECRAWL, credits())
    product = {} if output.product is None else {"linked_product": output.product}
    return {
        "request": output.request,
        **product,
        "trail": output.trail,
        "warnings": output.warnings,
    }


def _after_reading_the_link(state: State) -> str:
    return ASSEMBLE_REPORT if state["request"].scope in SCOPES_THAT_DO_NOT_RUN else BRIEF


async def _brief(state: State, *, agent: BriefAgent, chat: ChatModel, sources: Sources) -> State:
    search, credits = metered(search_view(sources, BRIEF_SEARCH_LIMIT))
    store = brief_store(sources.cache_folder, sources.clock)
    output = await agent(state["request"], state.get("linked_product"), chat, search, store)
    _log_usage(Agent.BRIEF, Service.TAVILY, credits())
    return {
        "factors": output.factors,
        "questions": output.questions,
        "phrased_questions": output.phrased_questions,
        "answers": output.stated_answers,
        "local_term": output.local_term,
        "trail": output.trail,
        "warnings": output.warnings,
    }


def _interview(state: State) -> State:
    """Pause for the user's answers, then write the answers that count, every factor with the
    user's own from the reply, uses per year and the reply's trail entries.

    LangGraph runs this node again from its start on resume, so nothing happens before
    `interrupt()`.
    """
    given: InterviewAnswers = interrupt(INTERVIEW)
    questions = state.get("questions", ())
    answers = complete_answers(
        questions,
        state.get("answers", ()),
        given.given,
        from_reply=given.from_reply,
        phrased=_phrased(state),
    )
    factors = with_own_factors(state.get("factors", ()), given.factors)
    return {
        "factors": factors,
        "answers": answers,
        "assumptions": Assumptions(uses_per_year=uses_per_year(factors, questions, answers)),
        "trail": given.trail,
    }


async def _tco(state: State, *, agent: TcoAgent, chat: ChatModel, sources: Sources) -> State:
    search, credits = metered(search_view(sources, TCO_SEARCH_LIMIT))
    fetch, fetch_credits = metered(page_view(sources, TCO_FETCH_LIMIT))
    # Every question phrased, so a factor answered and not asked is read against its question.
    output = await agent(
        state["request"],
        state.get("linked_product"),
        state.get("local_term"),
        state.get("factors", ()),
        every_question(state.get("questions", ()), _phrased(state)),
        state.get("answers", ()),
        chat,
        search,
        fetch,
    )
    _log_usage(Agent.TCO, Service.TAVILY, credits())
    _log_usage(Agent.TCO, Service.FIRECRAWL, fetch_credits())
    return {"options": output.options, "trail": output.trail, "warnings": output.warnings}


async def _lca(state: State, *, agent: LcaAgent, chat: ChatModel) -> State:
    output = await agent(state.get("options", ()), chat)
    return {"lca_results": output.results, "trail": output.trail, "warnings": output.warnings}


async def _second_hand(state: State, *, agent: SecondHandAgent, chat: ChatModel) -> State:
    output = await agent(state["request"], state.get("answers", ()), state.get("options", ()), chat)
    return {"listings": output.listings, "trail": output.trail, "warnings": output.warnings}


def _log_usage(agent: Agent, service: Service, credits: int) -> None:
    _USAGE_LOG.info("%s credits used by %s: %d", service, agent, credits)


def _assemble_report(state: State) -> State:
    """Every outcome leaves the graph here. Writes no trail entry, because it decides nothing."""
    report = assemble(
        state["request"],
        state.get("trail", ()),
        state.get("warnings", ()),
        factors=state.get("factors", ()),
        questions=state.get("questions", ()),
        answers=state.get("answers", ()),
        options=state.get("options", ()),
        lca_results=state.get("lca_results", ()),
        listings=state.get("listings", ()),
        assumptions=state.get("assumptions", Assumptions()),
    )
    return {"report": report}
