"""The stub agents' fixed data, called directly. They ignore what they are given."""

import asyncio

from fakes import UNUSED_SOURCES, fake_chat
from shopper.agents.stubs import STUB_AGENTS
from shopper.state import (
    Agent,
    Answer,
    AnswerStatus,
    FactorKind,
    Fit,
    Request,
    Scope,
    SourceKind,
    StatedIn,
    TrailEntry,
    TrailKind,
)
from shopper.tools.brief_store import brief_store
from shopper.tools.product_page import page_view
from shopper.tools.search import search_view

REQUEST = Request(original_text="a kettle", category="kettle", scope=Scope.TUNED)
CHAT, REQUESTS = fake_chat([])
SEARCH = search_view(UNUSED_SOURCES, 0)
FETCH = page_view(UNUSED_SOURCES, 0)
STORE = brief_store(UNUSED_SOURCES.cache_folder, UNUSED_SOURCES.clock)

BRIEF = asyncio.run(STUB_AGENTS.brief(REQUEST, None, CHAT, SEARCH, STORE))
TCO = asyncio.run(
    STUB_AGENTS.tco(REQUEST, None, None, BRIEF.factors, BRIEF.questions, (), CHAT, SEARCH, FETCH)
)
LCA = asyncio.run(STUB_AGENTS.lca(TCO.options, CHAT))
SECOND_HAND = asyncio.run(STUB_AGENTS.second_hand(REQUEST, (), TCO.options, CHAT))


def test_the_brief_asks_usage_frequency_and_hob_compatibility() -> None:
    hob, usage = BRIEF.questions

    # The four usage frequencies that code offers when no model picked any.
    assert usage.text == "How often will you use it?"
    assert [(choice.text, choice.uses_per_year) for choice in usage.choices] == [
        ("Every day", 365),
        ("A few times a week", 150),
        ("About once a week", 50),
        ("About once a month", 12),
    ]
    assert [choice.text for choice in hob.choices] == ["Gas", "Electric", "Induction"]
    hob_factor, _, usage_factor = BRIEF.factors
    assert [question.factor_id for question in (hob, usage)] == [hob_factor.id, usage_factor.id]
    assert BRIEF.stated_answers == ()


def test_the_hob_factor_has_a_stub_url_and_the_usage_factor_no_source() -> None:
    hob, _, usage = BRIEF.factors

    assert usage.source is None
    assert hob.source.reference.startswith("https://stub.invalid/")
    assert hob.source.label == "Stub value"


def test_the_brief_has_a_recurring_cost_with_a_typical_yearly_cost_and_its_source() -> None:
    _, oil, _ = BRIEF.factors

    assert oil.kind is FactorKind.RECURRING_COST
    assert oil.typical_yearly_cost == 6
    assert oil.typical_yearly_cost_source.reference == "https://stub.invalid/seasoning-oil"


def read_reply(reply: str) -> tuple[Answer, ...]:
    return asyncio.run(
        STUB_AGENTS.reply(REQUEST, reply, BRIEF.factors, BRIEF.questions, (), (), None, CHAT)
    ).answers


def test_the_reader_answers_each_question_whose_choice_the_reply_names() -> None:
    hob, usage = BRIEF.questions

    assert read_reply("We cook on INDUCTION, about once a week") == (
        Answer(
            factor_id=hob.factor_id,
            status=AnswerStatus.STATED,
            choice_id="choice-3",
            stated_value="Induction",
            stated_phrase="INDUCTION",
            stated_in=StatedIn.REPLY,
        ),
        Answer(
            factor_id=usage.factor_id,
            status=AnswerStatus.STATED,
            choice_id="about_once_a_week",
            stated_value="About once a week",
            stated_phrase="about once a week",
            uses_per_year=50,
            stated_in=StatedIn.REPLY,
        ),
    )


def test_the_reader_reads_nothing_from_a_reply_that_names_no_choice() -> None:
    assert read_reply("a frying pan please") == ()


def test_the_reader_reads_a_choice_only_as_whole_words() -> None:
    assert read_reply("a gasket-free lid, nothing that needs electricity") == ()


def test_the_tco_stub_gives_the_two_pans_with_estimated_lifespans() -> None:
    lifespan_sources = [option.lifespan_source for option in TCO.options]

    assert [option.name for option in TCO.options] == ["Non-stick pan", "Carbon steel pan"]
    assert all(source.kind is SourceKind.MODEL_ESTIMATE for source in lifespan_sources)
    assert all(source.reference == "stub" for source in lifespan_sources)
    assert all(source.label == "Stub value" for source in lifespan_sources)


def test_each_pan_has_an_unverified_hob_compatibility_value() -> None:
    hob = BRIEF.factors[0]

    for option in TCO.options:
        (value,) = option.factor_values
        assert value.factor_id == hob.id
        assert value.fit is Fit.UNVERIFIED
        assert value.source.label == "Stub value"


def test_the_lca_stub_returns_no_result_and_no_warning() -> None:
    assert LCA.results == ()
    assert LCA.warnings == ()


def test_the_second_hand_stub_returns_no_listings_and_says_so() -> None:
    (entry,) = SECOND_HAND.trail

    assert SECOND_HAND.listings == ()
    assert entry.summary == "Stub: used listings are not searched yet"


def test_every_stub_writes_one_decided_entry_that_says_it_is_a_stub() -> None:
    entries: list[TrailEntry] = [*BRIEF.trail, *TCO.trail, *LCA.trail, *SECOND_HAND.trail]

    assert [entry.agent for entry in entries] == [
        Agent.BRIEF,
        Agent.TCO,
        Agent.LCA,
        Agent.SECOND_HAND,
    ]
    for entry in entries:
        assert entry.kind is TrailKind.DECIDED
        assert entry.summary.startswith("Stub:")
        assert entry.model_tier is None
        assert entry.model is None


def test_no_stub_calls_the_model() -> None:
    assert REQUESTS == []
