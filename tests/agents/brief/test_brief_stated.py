"""What the request already states, read by the stated-answers call: a requirement or a usage
that becomes an answer and is not asked, and a requirement that fits no factor and becomes a
factor of the user's own (reading_answers.md, "Stated answers")."""

from decimal import Decimal
from pathlib import Path

import pytest
from brief_replies import (
    FIVE_FACTORS,
    FOUND,
    FOUR_QUESTIONS,
    HOB,
    LINK,
    NOTHING_STATED,
    Ran,
    asked,
    asked_about,
    brief,
    excluded,
    phrasing,
    reading,
    requirement,
    run,
    stated,
    warnings,
)

from fakes import failing_search_service, finding
from shopper.agents.bundle import BriefOutput
from shopper.config import MODEL_IDS
from shopper.llm import ChatError
from shopper.state import (
    Answer,
    AnswerStatus,
    FactorKind,
    Request,
    Scope,
    SourceKind,
    TrailKind,
    WarningCode,
)
from shopper.tools.results import FailureKind

# --- What the request already states ---

INDUCTION_DAILY = Request(
    original_text="a frying pan for induction, I cook every day",
    category="frying pan",
    scope=Scope.TUNED,
)
# The stated-answers call numbers the five researched factors 1 to 5 and usage 6.
USAGE_NUMBER = 6
HOB_STATED = Answer(
    factor_id="researched-1",
    status=AnswerStatus.STATED,
    choice_id="choice-1",
    stated_value="Induction",
    stated_phrase="for induction",
)
EVERY_DAY_STATED = Answer(
    factor_id="usage-1",
    status=AnswerStatus.STATED,
    stated_value="Every day",
    stated_phrase="I cook every day",
    uses_per_year=365,
)


def stating(cache: Path, *replies: str | Exception, request: Request = INDUCTION_DAILY) -> Ran:
    """A run on the five factors and four questions, with these replies to the stated call."""
    return run(
        cache,
        reading(*FIVE_FACTORS),
        phrasing(*FOUR_QUESTIONS),
        request=request,
        service=finding(FOUND),
        stated_replies=replies,
    )


def test_a_requirement_and_a_usage_the_request_states_are_answers_and_not_asked(
    tmp_path: Path,
) -> None:
    ran = stating(
        tmp_path,
        stated(
            requirement(1, "for induction", choice=1),
            requirement(USAGE_NUMBER, "I cook every day", frequency="every_day"),
        ),
    )

    assert ran.output.stated_answers == (HOB_STATED, EVERY_DAY_STATED)
    assert asked_about(ran.output) == ["researched-2", "researched-3", "researched-4"]


def test_the_stated_call_reads_the_request_and_the_factors_with_their_choices(
    tmp_path: Path,
) -> None:
    ran = stating(tmp_path, NOTHING_STATED)

    (call,) = ran.stated_requests
    shown = call.messages[-1]["content"]
    assert (call.model, call.low_effort) == (MODEL_IDS["medium"], True)
    assert "a frying pan for induction, I cook every day" in shown
    assert shown.index("[1] Hob compatibility") < shown.index("[2] Pan size")
    assert shown.index("[5] Coating wear") < shown.index("[6] Usage frequency")
    assert shown.index("[1] Induction") < shown.index("[3] Electric or ceramic")
    for frequency in ("several_times_a_day", "about_once_a_year"):
        assert frequency in shown
    assert "budget" in call.messages[0]["content"]


def test_a_freed_place_goes_to_the_next_phrased_question(tmp_path: Path) -> None:
    six = [{**HOB, "name": f"Factor {letter}"} for letter in "ABCDEF"]
    questions = [
        asked(number, f"Which {letter} do you have?", "It decides what fits.", "Gas", "Electric")
        for number, letter in enumerate("abcdef", start=1)
    ]
    request = Request(
        original_text="a frying pan for gas", category="frying pan", scope=Scope.TUNED
    )

    ran = run(
        tmp_path,
        reading(*six),
        phrasing(*questions),
        request=request,
        service=finding(FOUND),
        stated_replies=(stated(requirement(2, "for gas", choice=1)),),
    )

    assert asked_about(ran.output) == [
        "researched-1",
        "researched-3",
        "researched-4",
        "researched-5",
        "usage-1",
    ]
    assert "Left 1 phrased question unasked" in [entry.summary for entry in ran.output.trail]
    # Every phrased question is kept, the settled and the unasked one among them.
    assert [question.factor_id for question in ran.output.phrased_questions] == [
        f"researched-{number}" for number in range(1, 7)
    ]


def test_a_requirement_whose_phrase_is_not_in_the_request_goes_to_the_trail_only(
    tmp_path: Path,
) -> None:
    ran = stating(tmp_path, stated(requirement(1, "for an induction hob", choice=1)))

    assert ran.output.stated_answers == ()
    assert "researched-1" in asked_about(ran.output)
    assert excluded(ran.output, "Ignored") == [
        (
            'Ignored the requirement "for an induction hob" in the request',
            "the phrase is not in the request",
        )
    ]


def test_a_phrase_is_kept_as_the_request_has_it_whatever_its_case_spacing_and_edges(
    tmp_path: Path,
) -> None:
    ran = stating(tmp_path, stated(requirement(1, "For  Induction.", choice=1)))

    (answer,) = ran.output.stated_answers
    assert answer.stated_phrase == "for induction"


def test_a_requirement_that_fits_no_choice_is_stated_with_its_own_value(tmp_path: Path) -> None:
    request = Request(original_text="a 24 cm frying pan", category="frying pan", scope=Scope.TUNED)

    ran = stating(tmp_path, stated(requirement(2, "24 cm", value="24 cm")), request=request)

    assert ran.output.stated_answers == (
        Answer(
            factor_id="researched-2",
            status=AnswerStatus.STATED,
            stated_value="24 cm",
            stated_phrase="24 cm",
        ),
    )
    assert "researched-2" not in asked_about(ran.output)


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("28 cm", "its value holds a number that is not in its phrase"),
        ("an eco-friendly size", "its value holds a generic environmental term"),
        ("  ", "it has no value"),
        (None, "it has no value"),
    ],
)
def test_a_value_that_cannot_be_shown_goes_to_the_trail_only(
    tmp_path: Path, value: str | None, reason: str
) -> None:
    request = Request(original_text="a small frying pan", category="frying pan", scope=Scope.TUNED)

    ran = stating(tmp_path, stated(requirement(2, "small", value=value)), request=request)

    assert ran.output.stated_answers == ()
    assert "researched-2" in asked_about(ran.output)
    assert excluded(ran.output, "Ignored") == [
        ('Ignored the requirement "small" in the request', reason)
    ]


# --- Requirements that fit no factor: the user's own factors ---

SPARE_BATTERY = "with a spare battery"
DRILL = Request(
    original_text=f"a cordless drill {SPARE_BATTERY}", category="drill", scope=Scope.TUNED
)


def own_factors(output: BriefOutput) -> list[tuple[str, str, FactorKind, str]]:
    """The user's own factors: id, name, kind and why."""
    return [
        (factor.id, factor.name, factor.kind, factor.why)
        for factor in output.factors
        if factor.id.startswith("user-")
    ]


def test_a_requirement_that_fits_no_factor_becomes_a_factor_of_the_users_own(
    tmp_path: Path,
) -> None:
    ran = run(
        tmp_path,
        request=DRILL,
        service=failing_search_service(FailureKind.UNAVAILABLE),
        stated_replies=(stated(requirement("new", SPARE_BATTERY, value="spare battery")),),
    )

    assert own_factors(ran.output) == [
        ("user-1", SPARE_BATTERY, FactorKind.REQUIREMENT, "You asked for this.")
    ]
    (factor, usage) = ran.output.factors
    assert (factor.source.kind, usage.kind) == (SourceKind.USER, FactorKind.USAGE)
    assert ran.output.stated_answers == (
        Answer(
            factor_id="user-1",
            status=AnswerStatus.STATED,
            stated_value=SPARE_BATTERY,
            stated_phrase=SPARE_BATTERY,
        ),
    )
    assert asked_about(ran.output) == ["usage-1"]


@pytest.mark.parametrize(
    ("text", "phrase", "reason"),
    [
        ("an eco-friendly pan", "eco-friendly", "its phrase holds a generic environmental term"),
        ("a frying pan, budget €50", "budget €50", "its phrase holds a currency marker"),
        ("a frying pan, at most 50", "at most 50", "it is the budget"),
        (f"{LINK} with a lid", LINK, "it is the link"),
        (f"{LINK} with a lid", "example.org", "it is the link"),
    ],
)
def test_a_requirement_that_is_no_requirement_of_the_users_own_goes_to_the_trail_only(
    tmp_path: Path, text: str, phrase: str, reason: str
) -> None:
    request = Request(
        original_text=text,
        product_url=LINK if LINK in text else None,
        category="frying pan",
        budget=Decimal(50) if "50" in text else None,
        scope=Scope.TUNED,
    )

    ran = stating(tmp_path, stated(requirement("new", phrase, value=phrase)), request=request)

    assert own_factors(ran.output) == []
    assert ran.output.stated_answers == ()
    assert excluded(ran.output, "Ignored") == [
        (f'Ignored the requirement "{phrase}" in the request', reason)
    ]


def test_three_requirements_of_the_users_own_are_kept_and_a_fourth_goes_to_the_trail(
    tmp_path: Path,
) -> None:
    extras = ("with a lid", "dishwasher safe", "with a long handle", "made in Italy")
    request = Request(
        original_text=f"a frying pan {', '.join(extras)}", category="frying pan", scope=Scope.TUNED
    )

    ran = stating(
        tmp_path,
        stated(*(requirement("new", extra, value=extra) for extra in extras)),
        request=request,
    )

    assert [name for _, name, _, _ in own_factors(ran.output)] == list(extras[:3])
    assert [answer.factor_id for answer in ran.output.stated_answers] == [
        "user-1",
        "user-2",
        "user-3",
    ]
    assert excluded(ran.output, "Ignored") == [
        (
            'Ignored the requirement "made in Italy" in the request',
            "at most 3 requirements that fit no decision factor are kept",
        )
    ]
    assert len(ran.output.factors) == 9


def test_a_requirement_of_the_users_own_said_twice_is_kept_once(tmp_path: Path) -> None:
    request = Request(
        original_text="a frying pan with a lid", category="frying pan", scope=Scope.TUNED
    )

    ran = stating(
        tmp_path,
        stated(requirement("new", "with a lid"), requirement(9, "With a lid")),
        request=request,
    )

    assert [name for _, name, _, _ in own_factors(ran.output)] == ["with a lid"]
    assert excluded(ran.output, "Ignored") == [
        (
            'Ignored the requirement "with a lid" in the request',
            "an earlier requirement says the same",
        )
    ]


def test_a_stated_usage_may_be_any_of_the_seven_frequencies(tmp_path: Path) -> None:
    request = Request(
        original_text="a frying pan, I cook three times a day",
        category="frying pan",
        scope=Scope.TUNED,
    )

    ran = stating(
        tmp_path,
        stated(requirement(USAGE_NUMBER, "three times a day", frequency="several_times_a_day")),
        request=request,
    )

    (usage,) = ran.output.stated_answers
    assert (usage.stated_value, usage.uses_per_year) == ("Several times a day", 1000)
    assert "usage-1" not in asked_about(ran.output)


@pytest.mark.parametrize("frequency", [None, "now_and_then"])
def test_with_no_clear_frequency_the_usage_question_is_asked(
    tmp_path: Path, frequency: str | None
) -> None:
    request = Request(
        original_text="a frying pan I use now and then", category="frying pan", scope=Scope.TUNED
    )

    ran = stating(
        tmp_path,
        stated(requirement(USAGE_NUMBER, "now and then", frequency=frequency)),
        request=request,
    )

    assert ran.output.stated_answers == ()
    assert asked_about(ran.output)[-1] == "usage-1"
    assert excluded(ran.output, "Ignored") == [
        (
            'Ignored the usage "now and then" in the request',
            "it names none of the usage frequencies",
        )
    ]


def test_only_the_first_requirement_for_a_factor_counts(tmp_path: Path) -> None:
    ran = stating(
        tmp_path,
        stated(requirement(1, "for induction", choice=1), requirement(1, "frying pan", choice=2)),
    )

    assert ran.output.stated_answers == (HOB_STATED,)


# The stated-answers call numbers the seasoning factor 3; its question is a care question.
SEASONING_NUMBER = 3
NO_SEASONING = Request(
    original_text="a frying pan I never have to season",
    category="frying pan",
    scope=Scope.TUNED,
)


def test_a_care_factor_stated_in_the_request_takes_one_of_its_two_choices(tmp_path: Path) -> None:
    ran = stating(
        tmp_path,
        stated(requirement(SEASONING_NUMBER, "never have to season", choice=2)),
        request=NO_SEASONING,
    )

    (answer,) = ran.output.stated_answers
    assert (answer.factor_id, answer.choice_id) == ("researched-3", "care-avoid")


def test_a_care_factor_stated_in_the_request_as_a_value_goes_to_the_trail_only(
    tmp_path: Path,
) -> None:
    ran = stating(
        tmp_path,
        stated(requirement(SEASONING_NUMBER, "never have to season", value="no seasoning")),
        request=NO_SEASONING,
    )

    assert ran.output.stated_answers == ()
    assert "researched-3" in asked_about(ran.output)
    assert excluded(ran.output, "Ignored") == [
        (
            'Ignored the requirement "never have to season" in the request',
            "a care factor takes one of its two choices",
        )
    ]


def test_a_choice_that_is_not_on_the_question_is_read_as_its_own_value(tmp_path: Path) -> None:
    ran = stating(tmp_path, stated(requirement(1, "for induction", choice=7, value="induction")))

    (answer,) = ran.output.stated_answers
    assert (answer.choice_id, answer.stated_value) == (None, "induction")


def test_each_stated_answer_has_a_trail_entry_by_the_medium_model(tmp_path: Path) -> None:
    ran = stating(tmp_path, stated(requirement(1, "for induction", choice=1)))

    assert (
        TrailKind.DECIDED,
        'Stated in the request: "for induction" as Hob compatibility: Induction',
        "medium",
    ) in [(entry.kind, entry.summary, entry.model_tier) for entry in ran.output.trail]


@pytest.mark.parametrize(
    "replies",
    [
        (ChatError("service down"), ChatError("service down")),
        (ChatError("service down"), "not json", "still not json"),
        ("not json", "still not json"),
    ],
    ids=["the service fails twice", "the service fails, then invalid twice", "invalid twice"],
)
def test_with_the_stated_call_failing_every_question_is_asked_with_a_warning(
    tmp_path: Path, replies: tuple[str | Exception, ...]
) -> None:
    ran = stating(tmp_path, *replies)

    assert ran.output.stated_answers == ()
    assert len(ran.output.questions) == 5
    assert warnings(ran.output) == [
        (
            WarningCode.STATED_ANSWERS_UNAVAILABLE,
            "We couldn't pick out the requirements in your request, so only your answers to the "
            "questions are applied.",
        )
    ]


def test_a_brief_from_the_cache_still_reads_what_the_request_states(tmp_path: Path) -> None:
    brief(tmp_path, *FOUR_QUESTIONS)

    again = run(
        tmp_path,
        request=INDUCTION_DAILY,
        stated_replies=(stated(requirement(1, "for induction", choice=1)),),
    )

    assert again.requests == []
    assert again.output.stated_answers == (HOB_STATED,)


def test_a_request_with_no_category_can_state_its_usage(tmp_path: Path) -> None:
    request = Request(
        original_text=f"{LINK} I cook every day", product_url=LINK, scope=Scope.GENERAL
    )

    ran = run(
        tmp_path,
        request=request,
        stated_replies=(stated(requirement(1, "I cook every day", frequency="every_day")),),
    )

    assert ran.output.stated_answers == (EVERY_DAY_STATED,)
    assert ran.output.questions == ()
    assert ran.output.phrased_questions == ()


def test_a_stated_call_the_service_fails_once_is_tried_again(tmp_path: Path) -> None:
    ran = stating(
        tmp_path, ChatError("service down"), stated(requirement(1, "for induction", choice=1))
    )

    assert ran.output.stated_answers == (HOB_STATED,)
    assert warnings(ran.output) == []
