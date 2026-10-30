"""What the graph's tests share (test_graph.py and test_sessions.py): the graph on a fake model
and the stub agents, the frying pan session started on it and resumed, the answers picked for its
questions, the worked example its report gives, a brief with no questions, and agents that note
what they were given. Rules: docs/architecture/agents.md ("The graph") and
docs/architecture/sessions.md.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

from langgraph.graph.state import CompiledStateGraph

from fakes import UNUSED_SOURCES, extraction, fake_chat
from shopper.agents.bundle import AgentBundle, BriefOutput
from shopper.agents.stubs import STUB_AGENTS
from shopper.graph.graph import build_graph, memory_checkpointer
from shopper.graph.sessions import SessionStart, resume_session, start_session
from shopper.llm import ChatModel, ChatRequest
from shopper.state import (
    Answer,
    AnswerStatus,
    ComparisonRow,
    ProductOption,
    Question,
    Report,
    Request,
)
from shopper.tools.brief_store import BriefStore
from shopper.tools.results import WebSearch

CENT = Decimal("0.01")
AGENT_NAMES = ("brief", "tco", "lca", "second_hand")
FRYING_PAN = "I need a new frying pan, budget 50 euro"
FRYING_PAN_REPLY = extraction("frying pan", "tuned", "50 euro", 50)


def graph_with(
    *replies: str | Exception, agents: AgentBundle = STUB_AGENTS
) -> tuple[CompiledStateGraph, list[ChatRequest]]:
    chat, requests = fake_chat(replies)
    return build_graph(chat, memory_checkpointer(), UNUSED_SOURCES, agents), requests


def start(graph: CompiledStateGraph, text: str = FRYING_PAN) -> SessionStart:
    return asyncio.run(start_session(graph, uuid4().hex, text))


def resume(graph: CompiledStateGraph, session: SessionStart, *answers: Answer) -> Report:
    return asyncio.run(resume_session(graph, session.session_id, answers))


def thread(session_id: str) -> dict[str, dict[str, str]]:
    """The session id is the thread id."""
    return {"configurable": {"thread_id": session_id}}


def chosen(question: Question, text: str) -> Answer:
    choice = next(choice for choice in question.choices if choice.text == text)
    return Answer(factor_id=question.factor_id, status=AnswerStatus.CHOSEN, choice_id=choice.id)


def not_sure(question: Question) -> Answer:
    return Answer(factor_id=question.factor_id, status=AnswerStatus.NOT_SURE)


def row(report: Report, option_name: str) -> ComparisonRow:
    option = next(option for option in report.options if option.name == option_name)
    return next(row for row in report.comparison.rows if row.option_id == option.id)


def assert_worked_example(report: Report) -> None:
    """The frying pan worked example of docs/architecture/calculations.md, without cost per use."""
    non_stick = row(report, "Non-stick pan")
    carbon_steel = row(report, "Carbon steel pan")
    assert report.comparison.baseline_option_id == non_stick.option_id
    assert non_stick.cost_per_year == Decimal("10.00")
    assert non_stick.purchases == 5
    assert non_stick.horizon_cost == Decimal("100")
    assert carbon_steel.cost_per_year.quantize(CENT) == Decimal("1.33")
    assert carbon_steel.purchases == 1
    assert carbon_steel.horizon_cost == Decimal("40")
    assert carbon_steel.savings == Decimal("60")


async def brief_without_questions(
    request: Request,
    linked_product: ProductOption | None,
    chat: ChatModel,
    search: WebSearch,
    store: BriefStore,
) -> BriefOutput:
    return BriefOutput()


def recording(agents: AgentBundle, seen: dict[str, tuple[object, ...]]) -> AgentBundle:
    """The same agents, each noting what it was called with; a sequence is noted as a tuple."""

    def wrap(name: str) -> Callable[..., Awaitable[object]]:
        async def agent(*given: object) -> object:
            seen[name] = tuple(tuple(g) if isinstance(g, list | tuple) else g for g in given)
            return await getattr(agents, name)(*given)

        return agent

    return replace(agents, **{name: wrap(name) for name in AGENT_NAMES})
