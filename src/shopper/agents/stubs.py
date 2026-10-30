"""Stub agents: fixed data so the graph runs end to end before the real agents exist.

They ignore the category and the answers, call no model and no tool, and say in the trail that
they are stubs. Each is replaced by its real agent in a later task. The stub reader reads only
the choices a reply names, so the page can be checked on a reply.
"""

import re
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from shopper.agents.brief.usage_frequency import USAGE_FACTOR, usage_question
from shopper.agents.bundle import (
    AgentBundle,
    BriefOutput,
    LcaOutput,
    ReplyOutput,
    SecondHandOutput,
    TcoOutput,
)
from shopper.llm import ChatModel
from shopper.state import (
    Agent,
    Answer,
    AnswerStatus,
    Choice,
    DecisionFactor,
    FactorKind,
    FactorValue,
    Fit,
    ProductOption,
    Question,
    Request,
    Source,
    SourceKind,
    StatedIn,
    TrailEntry,
    TrailKind,
)
from shopper.tools.brief_store import BriefStore
from shopper.tools.results import PageFetch, WebSearch

STUB_LABEL = "Stub value"
STUB_ESTIMATE = Source(kind=SourceKind.MODEL_ESTIMATE, reference="stub", label=STUB_LABEL)

HOB_FACTOR = DecisionFactor(
    id="researched-1",
    name="Hob compatibility",
    kind=FactorKind.COMPATIBILITY,
    why="Not every pan works on every hob.",
    source=Source(
        kind=SourceKind.URL, reference="https://stub.invalid/hob-compatibility", label=STUB_LABEL
    ),
)
OIL_SOURCE = Source(
    kind=SourceKind.URL, reference="https://stub.invalid/seasoning-oil", label=STUB_LABEL
)
# A recurring cost is not asked about; its typical yearly cost is shown above the questions.
OIL_FACTOR = DecisionFactor(
    id="researched-2",
    name="Seasoning oil",
    kind=FactorKind.RECURRING_COST,
    why="A carbon steel pan is oiled now and then to keep its seasoning.",
    source=OIL_SOURCE,
    typical_yearly_cost=Decimal("6"),
    typical_yearly_cost_source=OIL_SOURCE,
)
# The real question about how often the product is used, with the frequencies code offers by
# default.
USAGE_QUESTION = usage_question()
HOB_QUESTION = Question(
    id=f"question-{HOB_FACTOR.id}",
    factor_id=HOB_FACTOR.id,
    text="Which hob do you cook on?",
    reason="Not every pan works on every hob.",
    choices=(
        Choice(id="choice-1", text="Gas"),
        Choice(id="choice-2", text="Electric"),
        Choice(id="choice-3", text="Induction"),
    ),
)
HOB_NOT_CHECKED = FactorValue(factor_id=HOB_FACTOR.id, fit=Fit.UNVERIFIED, source=STUB_ESTIMATE)
# The two options of the frying pan worked example in docs/architecture/calculations.md.
STUB_SEEN_ON = date(2026, 10, 1)
NON_STICK_PAN = ProductOption(
    id="option-1",
    name="Non-stick pan",
    price=Decimal("20"),
    price_source=STUB_ESTIMATE,
    price_seen_on=STUB_SEEN_ON,
    lifespan_years=Decimal("2"),
    lifespan_source=STUB_ESTIMATE,
    factor_values=(HOB_NOT_CHECKED,),
)
CARBON_STEEL_PAN = ProductOption(
    id="option-2",
    name="Carbon steel pan",
    price=Decimal("40"),
    price_source=STUB_ESTIMATE,
    price_seen_on=STUB_SEEN_ON,
    lifespan_years=Decimal("30"),
    lifespan_source=STUB_ESTIMATE,
    factor_values=(HOB_NOT_CHECKED,),
)


async def stub_brief(
    request: Request,
    linked_product: ProductOption | None,
    chat: ChatModel,
    search: WebSearch,
    store: BriefStore,
) -> BriefOutput:
    return BriefOutput(
        factors=(HOB_FACTOR, OIL_FACTOR, USAGE_FACTOR),
        questions=(HOB_QUESTION, USAGE_QUESTION),
        phrased_questions=(HOB_QUESTION,),
        trail=(_entry(Agent.BRIEF, "Stub: three fixed factors and two questions, not researched"),),
    )


async def stub_tco(
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
    """The two fixed pans, after the linked product when there is one."""
    linked = () if linked_product is None else (linked_product,)
    return TcoOutput(
        options=(*linked, NON_STICK_PAN, CARBON_STEEL_PAN),
        trail=(_entry(Agent.TCO, "Stub: two fixed frying pans, not searched for"),),
    )


async def stub_lca(options: Sequence[ProductOption], chat: ChatModel) -> LcaOutput:
    """No result for any option: a made-up CO2e figure is never returned."""
    return LcaOutput(trail=(_entry(Agent.LCA, "Stub: CO2e is not estimated yet"),))


async def stub_second_hand(
    request: Request,
    answers: Sequence[Answer],
    options: Sequence[ProductOption],
    chat: ChatModel,
) -> SecondHandOutput:
    return SecondHandOutput(
        trail=(_entry(Agent.SECOND_HAND, "Stub: used listings are not searched yet"),)
    )


async def stub_reply(
    request: Request,
    reply: str,
    factors: Sequence[DecisionFactor],
    questions: Sequence[Question],
    phrased: Sequence[Question],
    stated: Sequence[Answer],
    local_term: str | None,
    chat: ChatModel,
) -> ReplyOutput:
    """An answer, as the reply states it, to each question one of whose choices the reply names
    in its words; nothing else is read, so the reply adds no factor."""
    answers = tuple(
        answer for question in questions if (answer := _named_choice(question, reply)) is not None
    )
    trail = _entry(Agent.BRIEF, "Stub: the reply is read for the choices it names")
    return ReplyOutput(answers=answers, trail=(trail,))


def _named_choice(question: Question, reply: str) -> Answer | None:
    """The first of the question's choices whose words stand in the reply as whole words,
    whatever their case, with the reply's own words as its phrase."""
    for choice in question.choices:
        named = re.search(rf"\b{re.escape(choice.text)}\b", reply, re.IGNORECASE)
        if named is not None:
            return Answer(
                factor_id=question.factor_id,
                status=AnswerStatus.STATED,
                choice_id=choice.id,
                stated_value=choice.text,
                stated_phrase=named.group(),
                uses_per_year=choice.uses_per_year,
                stated_in=StatedIn.REPLY,
            )
    return None


def _entry(agent: Agent, summary: str) -> TrailEntry:
    return TrailEntry(agent=agent, kind=TrailKind.DECIDED, summary=summary)


STUB_AGENTS = AgentBundle(
    brief=stub_brief,
    tco=stub_tco,
    lca=stub_lca,
    second_hand=stub_second_hand,
    reply=stub_reply,
)
