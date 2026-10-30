"""The reply's reader, called directly: a fake model and the factors of a paused session."""

import asyncio
from collections.abc import Sequence
from decimal import Decimal
from typing import NamedTuple

import pytest

from fakes import fake_chat
from reply_readings import reading, said
from shopper.agents.brief.agent import CARE_CHOICES
from shopper.agents.brief.reply import read_reply
from shopper.agents.brief.usage_frequency import USAGE_FACTOR, usage_question
from shopper.agents.bundle import ReplyOutput, ReplyUnreadError
from shopper.config import MODEL_IDS
from shopper.llm import ChatError, ChatRequest
from shopper.state import (
    Answer,
    AnswerStatus,
    Choice,
    DecisionFactor,
    FactorKind,
    Question,
    Request,
    Scope,
    Source,
    SourceKind,
    StatedIn,
    TrailEntry,
    TrailKind,
)

WEB = Source(kind=SourceKind.URL, reference="https://example.org/frying-pan-guide")


def researched(number: int, name: str, kind: FactorKind) -> DecisionFactor:
    return DecisionFactor(
        id=f"researched-{number}", name=name, kind=kind, why="It decides the fit.", source=WEB
    )


def question(factor: DecisionFactor, text: str, *choices: str) -> Question:
    return Question(
        id=f"question-{factor.id}",
        factor_id=factor.id,
        text=text,
        reason=factor.why,
        choices=tuple(
            Choice(id=f"choice-{number}", text=choice)
            for number, choice in enumerate(choices, start=1)
        ),
    )


HOB = researched(1, "Hob compatibility", FactorKind.COMPATIBILITY)
SIZE = researched(2, "Pan size", FactorKind.REQUIREMENT)
SEASONING = researched(3, "Seasoning", FactorKind.CARE)
COATING = researched(4, "Coating", FactorKind.REQUIREMENT)
OIL = researched(5, "Seasoning oil", FactorKind.RECURRING_COST)
LID = researched(6, "Lid", FactorKind.REQUIREMENT)
MADE_IN_ITALY = DecisionFactor(
    id="user-1",
    name="made in Italy",
    kind=FactorKind.REQUIREMENT,
    why="You asked for this.",
    source=Source(kind=SourceKind.USER, reference="made in Italy"),
)
# The reading numbers the factors in this order: hob 1 to usage 8.
FACTORS = (HOB, SIZE, SEASONING, COATING, OIL, LID, MADE_IN_ITALY, USAGE_FACTOR)
HOB_NUMBER, SIZE_NUMBER, SEASONING_NUMBER, COATING_NUMBER = 1, 2, 3, 4
OIL_NUMBER, LID_NUMBER, USAGE_NUMBER = 5, 6, 8

HOB_QUESTION = question(HOB, "Which hob do you cook on?", "Gas", "Electric", "Induction")
SIZE_QUESTION = question(SIZE, "Which size of pan do you need?", "Small", "28 cm", "Large")
SEASONING_QUESTION = Question(
    id=f"question-{SEASONING.id}",
    factor_id=SEASONING.id,
    text="Some frying pans need seasoning before first use. Is that fine with you?",
    reason=SEASONING.why,
    choices=CARE_CHOICES,
)
USAGE_QUESTION = usage_question()
ASKED = (HOB_QUESTION, USAGE_QUESTION)
# Every question the brief phrased: the hob's was asked, the size's and the seasoning's were not.
PHRASED = (HOB_QUESTION, SIZE_QUESTION, SEASONING_QUESTION)
LINK = "https://example.org/pans/dishwasher-safe-pan"
REQUEST = Request(
    original_text="a frying pan with a lid, made in Italy",
    category="frying pan",
    budget=Decimal(50),
    scope=Scope.TUNED,
)
REQUEST_STATED = (
    Answer(
        factor_id=LID.id,
        status=AnswerStatus.STATED,
        stated_value="with a lid",
        stated_phrase="with a lid",
    ),
    Answer(
        factor_id=MADE_IN_ITALY.id,
        status=AnswerStatus.STATED,
        stated_value="made in Italy",
        stated_phrase="made in Italy",
    ),
)


class Read(NamedTuple):
    output: ReplyOutput
    requests: list[ChatRequest]


def read(
    reply: str,
    *replies: str | Exception,
    request: Request = REQUEST,
    factors: Sequence[DecisionFactor] = FACTORS,
    stated: Sequence[Answer] = REQUEST_STATED,
    local_term: str = "koekenpan",
) -> Read:
    chat, requests = fake_chat(replies)
    output = asyncio.run(
        read_reply(request, reply, factors, ASKED, PHRASED, stated, local_term, chat)
    )
    return Read(output, requests)


def from_reply(
    factor: DecisionFactor,
    value: str,
    phrase: str,
    *,
    choice_id: str | None = None,
    uses_per_year: int | None = None,
) -> Answer:
    return Answer(
        factor_id=factor.id,
        status=AnswerStatus.STATED,
        choice_id=choice_id,
        stated_value=value,
        stated_phrase=phrase,
        uses_per_year=uses_per_year,
        stated_in=StatedIn.REPLY,
    )


def excluded(output: ReplyOutput) -> list[tuple[str, str | None]]:
    return [(entry.summary, entry.reason) for entry in output.trail if is_excluded(entry)]


def is_excluded(entry: TrailEntry) -> bool:
    return entry.kind is TrailKind.EXCLUDED


# --- Answers to the questions asked ---


def test_an_answer_to_a_question_asked_is_stated_in_the_reply_with_its_choice() -> None:
    ran = read("I cook on induction", reading(said(HOB_NUMBER, "on induction", choice=3)))

    assert ran.output.answers == (
        from_reply(HOB, "Induction", "on induction", choice_id="choice-3"),
    )
    assert ran.output.trail[0].summary == (
        'Stated in the reply: "on induction" as Hob compatibility: Induction'
    )


@pytest.mark.parametrize(
    ("phrase", "frequency", "choice_id", "uses"),
    [
        ("about once a week", "about_once_a_week", "about_once_a_week", 50),
        ("three times a day", "several_times_a_day", None, 1000),
    ],
    ids=["a frequency offered", "a frequency not offered"],
)
def test_a_usage_the_reply_states_takes_the_choice_that_offers_it_and_its_uses_per_year(
    phrase: str, frequency: str, choice_id: str | None, uses: int
) -> None:
    ran = read(f"I cook {phrase}", reading(said(USAGE_NUMBER, phrase, frequency=frequency)))

    (answer,) = ran.output.answers
    assert (answer.choice_id, answer.uses_per_year, answer.stated_in) == (
        choice_id,
        uses,
        StatedIn.REPLY,
    )


def test_no_idea_which_hob_is_a_not_sure_answer_that_keeps_its_phrase() -> None:
    ran = read(
        "no idea which hob, it came with the flat",
        reading(said(HOB_NUMBER, "no idea which hob", not_sure=True)),
    )

    assert ran.output.answers == (
        Answer(
            factor_id=HOB.id,
            status=AnswerStatus.NOT_SURE,
            stated_phrase="no idea which hob",
            stated_in=StatedIn.REPLY,
        ),
    )


@pytest.mark.parametrize(
    ("factor", "phrase"),
    [(SIZE_NUMBER, "any size"), ("new", "the rest I don't mind")],
    ids=["a factor not asked", "no factor"],
)
def test_not_sure_about_anything_but_a_question_asked_goes_to_the_trail_only(
    factor: int | str, phrase: str
) -> None:
    ran = read(phrase, reading(said(factor, phrase, not_sure=True)))

    assert (ran.output.answers, ran.output.factors) == ((), ())
    assert excluded(ran.output) == [
        (
            f'Ignored the requirement "{phrase}" in the reply',
            "only a question asked is answered not sure",
        )
    ]


# --- Factors not asked ---


def test_a_factor_phrased_but_not_asked_takes_its_questions_choice() -> None:
    ran = read("a 28 cm one", reading(said(SIZE_NUMBER, "28 cm", choice=2)))

    assert ran.output.answers == (from_reply(SIZE, "28 cm", "28 cm", choice_id="choice-2"),)


def test_a_factor_not_phrased_takes_a_value_of_its_own() -> None:
    ran = read("no teflon please", reading(said(COATING_NUMBER, "no teflon", value="no teflon")))

    assert ran.output.answers == (from_reply(COATING, "no teflon", "no teflon"),)


def test_a_factor_the_request_already_answers_goes_to_the_trail_only() -> None:
    ran = read("a glass lid", reading(said(LID_NUMBER, "a glass lid", value="glass lid")))

    assert ran.output.answers == ()
    assert ran.output.answered_by_the_request is True
    assert excluded(ran.output) == [
        ('Ignored the requirement "a glass lid" in the reply', "the request already answers it")
    ]


def test_a_recurring_cost_goes_to_the_trail_only() -> None:
    ran = read("cheap oil", reading(said(OIL_NUMBER, "cheap oil", value="cheap oil")))

    assert ran.output.answers == ()
    assert ran.output.answered_by_the_request is False
    assert excluded(ran.output) == [
        ('Ignored the requirement "cheap oil" in the reply', "a recurring cost is not asked about")
    ]


def test_a_care_factor_takes_one_of_its_two_choices() -> None:
    ran = read(
        "I'd rather not season it", reading(said(SEASONING_NUMBER, "not season it", choice=2))
    )

    (answer,) = ran.output.answers
    assert (answer.factor_id, answer.choice_id) == (SEASONING.id, "care-avoid")


def test_a_care_reply_as_a_free_value_goes_to_the_trail_only() -> None:
    ran = read(
        "I'd rather not season it",
        reading(said(SEASONING_NUMBER, "not season it", value="no seasoning")),
    )

    assert ran.output.answers == ()
    assert excluded(ran.output) == [
        (
            'Ignored the requirement "not season it" in the reply',
            "a care factor takes one of its two choices",
        )
    ]


def test_only_the_first_answer_for_a_factor_counts() -> None:
    ran = read(
        "induction, or gas",
        reading(said(HOB_NUMBER, "induction", choice=3), said(HOB_NUMBER, "gas", choice=1)),
    )

    assert [answer.choice_id for answer in ran.output.answers] == ["choice-3"]
    assert excluded(ran.output) == [
        (
            'Ignored the requirement "gas" in the reply',
            "an earlier requirement is about the same factor",
        )
    ]


# --- What a reply cannot change ---


@pytest.mark.parametrize(
    ("reply", "phrase", "changes"),
    [("I meant a wok", "I meant a wok", "category"), ("make it €40", "make it €40", "budget")],
)
def test_a_reply_that_asks_to_change_the_request_changes_nothing_and_says_so(
    reply: str, phrase: str, changes: str
) -> None:
    ran = read(reply, reading(said("new", phrase, changes=changes)))

    assert (ran.output.answers, ran.output.factors) == ((), ())
    assert ran.output.asks_to_change_request is True
    assert excluded(ran.output) == [
        (
            f'Ignored the requirement "{phrase}" in the reply',
            f"it asks to change the {changes}, which a reply cannot",
        )
    ]


# --- Factors of the user's own ---


def own(ran: Read) -> list[tuple[str, str]]:
    return [(factor.id, factor.name) for factor in ran.output.factors]


def test_a_requirement_that_fits_no_factor_continues_the_requests_numbering() -> None:
    ran = read(
        "it must go in the oven",
        reading(said("new", "go in the oven", value="oven safe")),
    )

    assert own(ran) == [("user-2", "go in the oven")]
    assert ran.output.answers == (
        from_reply(ran.output.factors[0], "go in the oven", "go in the oven"),
    )
    assert ran.output.trail[0].summary == (
        'Stated in the reply: "go in the oven" as a requirement of its own'
    )


def test_the_cap_of_three_is_shared_with_the_request() -> None:
    extras = ("oven safe", "a long handle", "riveted")

    ran = read(", ".join(extras), reading(*(said("new", extra) for extra in extras)))

    assert own(ran) == [("user-2", "oven safe"), ("user-3", "a long handle")]
    assert excluded(ran.output) == [
        (
            'Ignored the requirement "riveted" in the reply',
            "at most 3 requirements that fit no decision factor are kept",
        )
    ]


def test_a_requirement_the_request_states_already_is_not_added_again() -> None:
    ran = read("Made in Italy, as I said", reading(said("new", "Made in Italy")))

    assert own(ran) == []
    assert excluded(ran.output) == [
        (
            'Ignored the requirement "Made in Italy" in the reply',
            "an earlier requirement says the same",
        )
    ]


@pytest.mark.parametrize(
    ("reply", "phrase", "reason"),
    [
        ("like the one at www.pans.example.com", "www.pans.example.com", "it holds a link"),
        ("see https://pans.example.com/x", "https://pans.example.com/x", "it holds a link"),
        ("like pans.example.com has", "pans.example.com", "it holds a link"),
        ("40", "40", "it is only a number or an amount"),
        ("40 euro", "40 euro", "its phrase holds a currency marker"),
        ("make it €40", "make it €40", "its phrase holds a currency marker"),
        ("a bigger frying pan", "a bigger frying pan", "it holds the category"),
        ("een koekenpan van ijzer", "een koekenpan van ijzer", "it holds the local category term"),
        ("about 50", "about 50", "it is the budget"),
        ("an eco-friendly one", "eco-friendly", "its phrase holds a generic environmental term"),
    ],
)
def test_a_phrase_that_is_no_requirement_of_the_users_own_goes_to_the_trail_only(
    reply: str, phrase: str, reason: str
) -> None:
    ran = read(reply, reading(said("new", phrase)))

    assert own(ran) == []
    assert excluded(ran.output) == [(f'Ignored the requirement "{phrase}" in the reply', reason)]


@pytest.mark.parametrize(
    ("reply", "kept"),
    [("frying pans with rivets", False), ("Japanese steel", True), ("a glass panel", True)],
)
def test_the_category_and_the_local_term_are_refused_as_whole_words(reply: str, kept: bool) -> None:
    pan = REQUEST.model_copy(update={"category": "pan"})

    ran = read(reply, reading(said("new", reply)), request=pan, local_term="pan")

    assert [factor.name for factor in ran.output.factors] == ([reply] if kept else [])


def test_the_link_is_refused_only_when_it_stands_in_the_reply() -> None:
    linked = REQUEST.model_copy(update={"product_url": LINK, "original_text": LINK})

    in_reply = read(f"{LINK} but bigger", reading(said("new", LINK)), request=linked, stated=())
    not_in_reply = read(
        "it must go in the dishwasher",
        reading(said("new", "dishwasher")),
        request=linked,
        stated=(),
    )

    assert excluded(in_reply.output) == [
        (f'Ignored the requirement "{LINK}" in the reply', "it is the link")
    ]
    assert [factor.name for factor in not_in_reply.output.factors] == ["dishwasher"]


def test_the_answers_to_the_users_own_factors_come_first() -> None:
    ran = read(
        "induction, and oven safe",
        reading(said(HOB_NUMBER, "induction", choice=3), said("new", "oven safe")),
    )

    assert [answer.factor_id for answer in ran.output.answers] == ["user-2", HOB.id]


# --- Phrases and the trail ---


def test_a_phrase_not_in_the_reply_goes_to_the_trail_without_being_repeated() -> None:
    ran = read("induction", reading(said(HOB_NUMBER, "an induction hob", choice=3)))

    assert ran.output.answers == ()
    assert excluded(ran.output) == [
        ("Ignored a requirement whose phrase is not in the reply", "the phrase is not in the reply")
    ]


def test_each_entry_names_the_medium_model() -> None:
    ran = read("on induction", reading(said(HOB_NUMBER, "on induction", choice=3)))

    assert [(entry.model_tier, entry.model) for entry in ran.output.trail] == [
        ("medium", MODEL_IDS["medium"])
    ]


def test_the_reading_is_shown_the_reply_the_category_and_every_factor_marked() -> None:
    ran = read("on induction", reading())

    (call,) = ran.requests
    shown = call.messages[-1]["content"]
    assert (call.model, call.low_effort) == (MODEL_IDS["medium"], True)
    assert "Reply: on induction" in shown
    assert "Product category: frying pan" in shown
    assert "a frying pan with a lid" not in shown
    for line in (
        "[1] Hob compatibility (compatibility): asked\nQuestion: Which hob do you cook on?\n"
        "[1] Gas\n[2] Electric\n[3] Induction",
        "[2] Pan size (requirement): not asked\nQuestion: Which size of pan do you need?\n"
        "[1] Small",
        "[3] Seasoning (care): not asked",
        "[1] That's fine\n[2] I'd rather avoid it",
        "[4] Coating (requirement): not asked\nNo choices: write a value.",
        "[5] Seasoning oil (recurring_cost): a recurring cost, never answered",
        "[6] Lid (requirement): answered by the request",
        "[7] made in Italy (requirement): answered by the request",
        "[8] Usage frequency (usage): asked",
        "- several_times_a_day: Several times a day",
    ):
        assert line in shown


# --- When the reading fails ---


@pytest.mark.parametrize(
    "replies",
    [
        (ChatError("service down"), ChatError("service down")),
        (ChatError("service down"), "not json", "still not json"),
        ("not json", "still not json"),
    ],
    ids=["the service fails twice", "the service fails, then invalid twice", "invalid twice"],
)
def test_a_reading_that_fails_twice_raises_its_own_error(
    replies: tuple[str | Exception, ...],
) -> None:
    with pytest.raises(ReplyUnreadError):
        read("on induction", *replies)


def test_a_reading_the_service_fails_once_is_tried_again() -> None:
    ran = read(
        "on induction",
        ChatError("service down"),
        reading(said(HOB_NUMBER, "on induction", choice=3)),
    )

    assert [answer.factor_id for answer in ran.output.answers] == [HOB.id]
