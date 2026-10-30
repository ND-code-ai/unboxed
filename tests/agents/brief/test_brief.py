"""The brief agent, called directly with a fake model, a fake search service and a store on disk:
category research and the read's checks, the questions and the usage frequencies, the follow-up
search, the brief cache, the local category term and a pasted link (category_brief.md, "How the
brief is researched"; interview.md, "Questions", "The usage question", "Pasted product link")."""

import json
from collections.abc import Mapping, Sequence
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from brief_replies import (
    CARE,
    CARE_QUERY,
    CARE_URL,
    COATING_WEAR,
    FIVE_FACTORS,
    FOUND,
    FOUR_QUESTIONS,
    GUIDE,
    GUIDE_QUERY,
    GUIDE_URL,
    HAND_WASHING,
    HAND_WASHING_STATEMENT,
    HOB,
    HOB_QUESTION,
    LINK,
    MAKER_URL,
    NOON,
    SEASONING,
    SEASONING_STATEMENT,
    SIZE,
    SIZE_QUESTION,
    asked,
    asked_about,
    brief,
    care,
    excluded,
    factor,
    phrasing,
    reading,
    requirement,
    run,
    stated,
    trail,
    warnings,
)

from fakes import Clock, failing_search_service, finding, recording
from samples import seen_price
from shopper.agents.bundle import BriefOutput
from shopper.config import MODEL_IDS, SearchPurpose
from shopper.llm import ChatError
from shopper.state import (
    Agent,
    FactorKind,
    ProductOption,
    Request,
    Scope,
    StatedBy,
    TrailKind,
    WarningCode,
)
from shopper.tools.brief_store import Brief, brief_store
from shopper.tools.results import FailureKind, SearchRequest, SearchService, StoredResponse

NO_CATEGORY = Request(original_text=LINK, product_url=LINK, scope=Scope.GENERAL)


def choices(output: BriefOutput, factor_kind: FactorKind) -> list[tuple[str, int | None]]:
    """The choices of the question about the one factor of this kind, with their uses per year."""
    (factor,) = (factor for factor in output.factors if factor.kind is factor_kind)
    (question,) = (question for question in output.questions if question.factor_id == factor.id)
    return [(choice.text, choice.uses_per_year) for choice in question.choices]


# --- A request with no category ---


def test_a_request_with_no_category_is_asked_only_how_often_it_is_used(tmp_path: Path) -> None:
    # UNUSED_SOURCES fails the test on any search, and the model has no reply to give.
    ran = run(tmp_path, request=NO_CATEGORY)

    assert [factor.kind for factor in ran.output.factors] == [FactorKind.USAGE]
    assert [question.text for question in ran.output.questions] == ["How often will you use it?"]
    assert choices(ran.output, FactorKind.USAGE) == [
        ("Every day", 365),
        ("A few times a week", 150),
        ("About once a week", 50),
        ("About once a month", 12),
    ]
    assert ran.output.warnings == ()
    assert [entry.kind for entry in ran.output.trail] == [TrailKind.DECIDED]
    assert list(tmp_path.iterdir()) == []


# --- Category research: two template searches and one read ---


def researched(output: BriefOutput) -> list[tuple[str, str, FactorKind, str]]:
    """Each researched factor's id, name, kind and the URL it came from."""
    return [
        (factor.id, factor.name, factor.kind, factor.source.reference)
        for factor in output.factors
        if factor.kind is not FactorKind.USAGE
    ]


def test_a_category_is_researched_with_both_template_searches_and_one_read(
    tmp_path: Path,
) -> None:
    ran = run(tmp_path, reading(*FIVE_FACTORS), phrasing(), service=finding(FOUND))

    assert [(search.search_query, search.purpose) for search in ran.searches] == [
        (GUIDE_QUERY, SearchPurpose.CATEGORY),
        (CARE_QUERY, SearchPurpose.CATEGORY_CARE),
    ]
    assert researched(ran.output) == [
        ("researched-1", "Hob compatibility", FactorKind.COMPATIBILITY, GUIDE_URL),
        ("researched-2", "Pan size", FactorKind.REQUIREMENT, GUIDE_URL),
        ("researched-3", "Seasoning", FactorKind.CARE, CARE_URL),
        ("researched-4", "Hand washing", FactorKind.CARE, MAKER_URL),
        ("researched-5", "Coating wear", FactorKind.RECURRING_COST, CARE_URL),
    ]
    assert ran.output.factors[-1].kind is FactorKind.USAGE
    assert ran.output.warnings == ()


# --- What code checks in a read ---

LID = factor(
    "Lid fit",
    "requirement",
    "A lid that does not fit is bought a second time.",
    1,
    "A lid is sold separately for most pans.",
)


def names(output: BriefOutput) -> list[str]:
    return [name for _, name, _, _ in researched(output)]


def test_a_factor_whose_quote_is_not_in_the_cited_result_is_left_out(tmp_path: Path) -> None:
    ran = run(tmp_path, reading(HOB, LID, SEASONING), phrasing(), service=finding(FOUND))

    assert researched(ran.output) == [
        ("researched-1", "Hob compatibility", FactorKind.COMPATIBILITY, GUIDE_URL),
        ("researched-2", "Seasoning", FactorKind.CARE, CARE_URL),
    ]
    assert excluded(ran.output) == [
        ('Left out the factor "Lid fit"', "its quote is not in the search result it cites")
    ]


LIFETIME = "Makers call it a “lifetime” pan. It’s only true of\nsolid metal."
DASHED = "Non-stick coatings wear out – most within a few years."
OVEN = "It works on the stovetop and in the oven, it heats up quickly."


@pytest.mark.parametrize(
    ("content", "quote", "found"),
    [
        (LIFETIME, 'makers call it a "lifetime" pan. It\'s only true  of solid metal.', True),
        # The model writes a non-breaking hyphen and a plain one where the page has a dash.
        (DASHED, "Non‑stick coatings wear out - most within a few years.", True),
        (OVEN, "It works on the stovetop and in the oven.", True),
        (OVEN, '"It works on the stovetop and in the oven"', True),
        (OVEN, "works on the stovetop and in the oven...", True),
        (OVEN, "It works in the oven.", False),
        (OVEN, "  ", False),
    ],
    ids=[
        "case, spacing and quote marks",
        "hyphens and dashes",
        "a full stop at the end",
        "quote marks around it",
        "an ellipsis at the end",
        "words that differ inside",
        "empty",
    ],
)
def test_a_quote_is_found_whatever_its_case_spacing_quote_marks_dashes_and_edges(
    tmp_path: Path, content: str, quote: str, found: bool
) -> None:
    guide = {"url": GUIDE_URL, "title": "How to choose a frying pan", "content": content}
    quoted = factor("Oven use", "compatibility", "Not every pan goes in an oven.", 1, quote)

    ran = run(
        tmp_path,
        reading(quoted),
        phrasing(),
        service=finding({GUIDE_QUERY: (guide,), CARE_QUERY: ()}),
    )

    assert names(ran.output) == (["Oven use"] if found else [])


@pytest.mark.parametrize("result", [0, 4, -1])
def test_a_factor_that_cites_a_result_that_was_not_shown_is_left_out(
    tmp_path: Path, result: int
) -> None:
    astray = {**HOB, "result": result}

    ran = run(tmp_path, reading(astray, SEASONING), phrasing(), service=finding(FOUND))

    assert names(ran.output) == ["Seasoning"]
    assert excluded(ran.output) == [
        ('Left out the factor "Hob compatibility"', "it cites no search result that was shown")
    ]


MUST = 'its explanation holds "should" or "must"'


@pytest.mark.parametrize(
    ("name", "why", "reason"),
    [
        (" ", "Not every pan fits the hob.", "it has no name or no explanation"),
        ("Pan size", "", "it has no name or no explanation"),
        ("Pans of 28 cm", "Not every pan fits the hob.", "its name holds a digit"),
        ("Pan size", "Most households use 1 pan.", "its explanation holds a digit"),
        ("Pan size", "A pan that is ½ too small is replaced.", "its explanation holds a digit"),
        ("Coating price", "It is sold for €.", "its explanation holds a currency marker"),
        (
            "Coating price",
            "A new one costs a few euros.",
            "its explanation holds a currency marker",
        ),
        ("Cost in USD", "A new coating is paid for again.", "its name holds a currency marker"),
        (
            "Eco-friendly coating",
            "Some coatings wear out sooner.",
            "its name holds a generic environmental term",
        ),
        (
            "Coating",
            "A ceramic coating is the sustainable choice.",
            "its explanation holds a generic environmental term",
        ),
        ("Green pans", "Some pans last longer.", "its name holds a generic environmental term"),
        (
            "Coating",
            "It is better for the planet.",
            "its explanation holds a generic environmental term",
        ),
        # Task 1.7's live runs: a read's why said "you must".
        ("Hob", "For induction you must have a magnetic base.", MUST),
    ],
)
def test_a_factor_that_holds_what_a_model_may_not_write_is_left_out_without_repeating_it(
    tmp_path: Path, name: str, why: str, reason: str
) -> None:
    unusable = {**HOB, "name": name, "why": why}

    ran = run(tmp_path, reading(unusable, SEASONING), phrasing(), service=finding(FOUND))

    assert names(ran.output) == ["Seasoning"]
    assert excluded(ran.output) == [("Left out a factor", reason)]


def test_ordinary_words_that_only_look_like_a_currency_or_a_claim_are_kept(tmp_path: Path) -> None:
    # "cup", "pen", "try", "all" and "top" are also currency codes; "evergreen" holds "green".
    ordinary = {
        **HOB,
        "name": "Cup and pen holder",
        "why": "Try all the top settings of an evergreen design.",
    }

    ran = run(tmp_path, reading(ordinary), phrasing(), service=finding(FOUND))

    assert names(ran.output) == ["Cup and pen holder"]


def test_a_factor_named_twice_is_kept_once(tmp_path: Path) -> None:
    again = {**SEASONING, "name": "hob  compatibility"}

    ran = run(tmp_path, reading(HOB, again, SEASONING), phrasing(), service=finding(FOUND))

    assert names(ran.output) == ["Hob compatibility", "Seasoning"]
    assert excluded(ran.output) == [
        ('Left out the factor "hob  compatibility"', "it repeats an earlier factor")
    ]


def test_at_most_eight_researched_factors_are_kept_in_the_order_read(tmp_path: Path) -> None:
    nine = [{**HOB, "name": f"Factor {letter}"} for letter in "ABCDEFGHI"]

    ran = run(tmp_path, reading(*nine), phrasing(), service=finding(FOUND))

    assert names(ran.output) == [f"Factor {letter}" for letter in "ABCDEFGH"]
    assert excluded(ran.output) == [
        ('Left out the factor "Factor I"', "at most 8 researched factors are kept")
    ]
    assert len(ran.output.factors) == 9


def test_each_kept_factor_has_a_trail_entry_with_its_source_and_who_stated_it(
    tmp_path: Path,
) -> None:
    ran = run(tmp_path, reading(HOB, HAND_WASHING), phrasing(), service=finding(FOUND))

    found = [
        (entry.summary, entry.source.reference, entry.source.stated_by, entry.model_tier)
        for entry in ran.output.trail
        if entry.summary.startswith("Factor")
    ]
    assert found == [
        (
            'Factor "Hob compatibility" (compatibility), stated by a tester',
            GUIDE_URL,
            StatedBy.TESTER,
            "medium",
        ),
        (
            'Factor "Hand washing" (care), stated by the manufacturer',
            MAKER_URL,
            StatedBy.MANUFACTURER,
            "medium",
        ),
    ]
    assert [factor.source.stated_by for factor in ran.output.factors[:2]] == [
        StatedBy.TESTER,
        StatedBy.MANUFACTURER,
    ]


# --- The questions ---


def texts(output: BriefOutput) -> list[str]:
    return [question.text for question in output.questions]


def test_each_factor_that_can_be_asked_about_gets_a_question_and_usage_is_asked_last(
    tmp_path: Path,
) -> None:
    ran = brief(tmp_path, *FOUR_QUESTIONS)

    assert [(question.factor_id, question.text) for question in ran.output.questions] == [
        ("researched-1", "Which hob do you cook on?"),
        ("researched-2", "Which size of pan do you need?"),
        (
            "researched-3",
            "Some frying pans need seasoning with oil before first use. Is that fine with you?",
        ),
        ("researched-4", "Some frying pans are washed by hand only. Is that fine with you?"),
        ("usage-1", "How often will you use it?"),
    ]
    assert len({question.id for question in ran.output.questions}) == 5


def test_a_question_has_the_models_reason_and_choices_and_a_care_question_fixed_ones(
    tmp_path: Path,
) -> None:
    ran = brief(tmp_path, *FOUR_QUESTIONS)

    hob, _, seasoning, hand_washing, _ = ran.output.questions
    assert hob.reason == "Not every pan works on every hob."
    assert [choice.text for choice in hob.choices] == ["Induction", "Gas", "Electric or ceramic"]
    assert seasoning.reason == "A carbon steel pan needs seasoning to keep food from sticking."
    for question in (seasoning, hand_washing):
        assert [(choice.id, choice.text) for choice in question.choices] == [
            ("care-fine", "That's fine"),
            ("care-avoid", "I'd rather avoid it"),
        ]


def test_the_phrasing_call_is_given_the_factors_to_ask_about_and_the_usage_frequencies(
    tmp_path: Path,
) -> None:
    ran = brief(tmp_path, *FOUR_QUESTIONS)

    _, phrase = ran.requests
    shown = phrase.messages[-1]["content"]
    assert phrase.model == MODEL_IDS["medium"]
    assert "frying pan" in shown
    assert shown.index("[1] Hob compatibility") < shown.index("[2] Pan size")
    assert shown.index("[3] Seasoning") < shown.index("[4] Hand washing")
    assert "Coating wear" not in shown
    assert "A pan of 28 cm suits most households." in shown
    for frequency in (
        "several_times_a_day",
        "every_day",
        "a_few_times_a_week",
        "about_once_a_week",
        "about_once_a_month",
        "a_few_times_a_year",
        "about_once_a_year",
    ):
        assert frequency in shown


SIZE_TEXT = "Which size of pan do you need?"
SIZE_REASON = "The size decides how much fits in the pan."
NO_SIZE_QUESTION = 'No question about the factor "Pan size"'


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        (
            asked(2, "Do you need a pan of 28 cm?", SIZE_REASON, "Yes", "No"),
            "its question holds a digit",
        ),
        (
            asked(2, SIZE_TEXT, "Most households own 2 pans.", "Small", "Large"),
            "its reason holds a digit",
        ),
        (
            asked(2, "Which size fits a budget of a few euros?", SIZE_REASON, "Small", "Large"),
            "its question holds a currency marker",
        ),
        (
            asked(2, "Do you want a sustainable pan?", SIZE_REASON, "Yes", "No"),
            "its question holds a generic environmental term",
        ),
        (
            asked(2, SIZE_TEXT, "The pan size should match the food.", "Small", "Large"),
            'its reason holds "should" or "must"',
        ),
        (asked(2, " ", SIZE_REASON, "Small", "Large"), "it has no question or no reason"),
        (asked(2, SIZE_TEXT, "", "Small", "Large"), "it has no question or no reason"),
        (
            asked(2, SIZE_TEXT, SIZE_REASON, "Small"),
            "it does not have 2 to 4 different choices",
        ),
        (
            asked(2, SIZE_TEXT, SIZE_REASON, "A", "B", "C", "D", "E"),
            "it does not have 2 to 4 different choices",
        ),
        (
            asked(2, SIZE_TEXT, SIZE_REASON, "Small", "small "),
            "it does not have 2 to 4 different choices",
        ),
        (asked(2, SIZE_TEXT, SIZE_REASON, "Small", " "), "a choice is empty"),
        (
            asked(
                2, SIZE_TEXT, SIZE_REASON, "Small", "A pan that is large enough for a whole family"
            ),
            "a choice is longer than 40 characters",
        ),
        (
            asked(2, SIZE_TEXT, SIZE_REASON, "Small", "A few euros more"),
            "a choice holds a currency marker",
        ),
        (
            asked(2, SIZE_TEXT, SIZE_REASON, "Small", "The green one"),
            "a choice holds a generic environmental term",
        ),
        (
            asked(2, SIZE_TEXT, SIZE_REASON, "24 cm", "28 cm"),
            "a choice holds a number that is not in the search result its factor cites",
        ),
        (
            asked(2, SIZE_TEXT, SIZE_REASON, "Small", "Up to ½ litre"),
            "a choice holds a numeral other than a plain digit",
        ),
        (
            asked(
                2, "How many people do you cook for?", SIZE_REASON, "One or two", "Three or more"
            ),
            "a choice holds a number that is not in the search result its factor cites",
        ),
    ],
)
def test_a_question_that_fails_a_check_counts_as_not_phrased(
    tmp_path: Path, question: Mapping[str, object], reason: str
) -> None:
    ran = brief(tmp_path, HOB_QUESTION, question, SEASONING_STATEMENT, HAND_WASHING_STATEMENT)

    assert asked_about(ran.output) == ["researched-1", "researched-3", "researched-4", "usage-1"]
    assert excluded(ran.output, "No question") == [(NO_SIZE_QUESTION, reason)]
    # The factor stays, so it is on the check-before-you-buy list.
    assert "Pan size" in names(ran.output)


NO_OPENING = 'its statement does not open with "Some" and the category in the plural'


@pytest.mark.parametrize(
    ("category", "plural"),
    [("knife", "knives"), ("battery charger", "battery chargers"), ("headphones", "headphones")],
)
def test_an_irregular_plural_of_the_category_opens_a_care_statement(
    tmp_path: Path, category: str, plural: str
) -> None:
    request = Request(original_text=f"a {category}", category=category, scope=Scope.TUNED)
    found = {
        f"{category} buying guide what to look for": (CARE,),
        f"{category} care maintenance and replacement parts": (),
    }

    ran = run(
        tmp_path,
        reading({**SEASONING, "result": 1}),
        phrasing(care(1, f"Some {plural} need seasoning with oil.")),
        request=request,
        service=finding(found),
    )

    assert asked_about(ran.output) == ["researched-1", "usage-1"]


@pytest.mark.parametrize(
    ("statement", "reason"),
    [
        ("Some frying pans need seasoning with oil.", None),
        ("some Frying Pans, unlike others, need seasoning with oil.", None),
        ("Carbon steel pans need seasoning with oil.", NO_OPENING),
        ("Some carbon steel pans need seasoning with oil.", NO_OPENING),
        ("Some pans need seasoning with oil.", NO_OPENING),
        ("Some frying pans need seasoning 2 times a year.", "its statement holds a digit"),
        ("Some frying pans need green soap.", "its statement holds a generic environmental term"),
        (
            "Some frying pans should be used with non-metal utensils.",
            'its statement holds "should" or "must"',
        ),
        ("  ", "it has no statement"),
    ],
)
def test_a_care_statement_opens_with_some_and_the_category_in_the_plural_and_passes_the_checks(
    tmp_path: Path, statement: str, reason: str | None
) -> None:
    ran = brief(tmp_path, HOB_QUESTION, SIZE_QUESTION, care(3, statement), HAND_WASHING_STATEMENT)

    left_out = [] if reason is None else [('No question about the factor "Seasoning"', reason)]
    assert ("researched-3" in asked_about(ran.output)) is (reason is None)
    assert excluded(ran.output, "No question") == left_out


def test_a_care_statement_ends_with_one_full_stop_before_the_closing_question(
    tmp_path: Path,
) -> None:
    unfinished = care(3, " Some frying pans need seasoning with oil ")

    ran = brief(tmp_path, unfinished)

    assert texts(ran.output)[0] == (
        "Some frying pans need seasoning with oil. Is that fine with you?"
    )


def test_a_factor_the_model_wrote_no_question_for_is_skipped(tmp_path: Path) -> None:
    ran = brief(tmp_path, HOB_QUESTION, SEASONING_STATEMENT, HAND_WASHING_STATEMENT)

    assert asked_about(ran.output) == ["researched-1", "researched-3", "researched-4", "usage-1"]
    assert excluded(ran.output, "No question") == [(NO_SIZE_QUESTION, "the model wrote none")]


def test_only_the_first_question_for_a_factor_counts_and_one_for_no_factor_is_ignored(
    tmp_path: Path,
) -> None:
    second = asked(1, "Is your hob new?", "It decides the base.", "Yes", "No")
    astray = asked(9, "Do you own a lid?", "A lid is extra.", "Yes", "No")

    ran = brief(tmp_path, *FOUR_QUESTIONS, second, astray)

    assert texts(ran.output)[0] == "Which hob do you cook on?"
    assert len(ran.output.questions) == 5


def test_the_questions_follow_the_order_of_the_factors_not_of_the_reply(tmp_path: Path) -> None:
    ran = brief(tmp_path, *reversed(FOUR_QUESTIONS))

    assert asked_about(ran.output) == [
        "researched-1",
        "researched-2",
        "researched-3",
        "researched-4",
        "usage-1",
    ]


def test_at_most_four_researched_questions_are_asked(tmp_path: Path) -> None:
    six = [{**HOB, "name": f"Factor {letter}"} for letter in "ABCDEF"]
    questions = [
        asked(number, f"Which {letter} do you have?", "It decides what fits.", "Gas", "Electric")
        for number, letter in enumerate("abcdef", start=1)
    ]

    ran = run(tmp_path, reading(*six), phrasing(*questions), service=finding(FOUND))

    assert asked_about(ran.output) == [
        "researched-1",
        "researched-2",
        "researched-3",
        "researched-4",
        "usage-1",
    ]
    assert len(ran.output.factors) == 7
    assert (
        "Left 2 phrased questions unasked",
        "at most 4 questions are asked besides how often the product is used",
    ) in [(entry.summary, entry.reason) for entry in ran.output.trail]


# --- The usage frequencies ---


def test_the_models_pick_of_four_frequencies_is_offered_most_often_first(tmp_path: Path) -> None:
    picked = (
        "about_once_a_year",
        "several_times_a_day",
        "about_once_a_month",
        "a_few_times_a_year",
    )

    ran = brief(tmp_path, *FOUR_QUESTIONS, frequencies=picked)

    assert choices(ran.output, FactorKind.USAGE) == [
        ("Several times a day", 1000),
        ("About once a month", 12),
        ("A few times a year", 4),
        ("About once a year", 1),
    ]


@pytest.mark.parametrize(
    "picked",
    [
        (),
        ("every_day", "about_once_a_week", "about_once_a_month"),
        ("every_day", "every_day", "about_once_a_week", "about_once_a_month"),
        ("every_day", "about_once_a_week", "about_once_a_month", "twice_a_decade"),
        (
            "every_day",
            "a_few_times_a_week",
            "about_once_a_week",
            "about_once_a_month",
            "a_few_times_a_year",
        ),
    ],
    ids=["none", "three", "one twice", "an unknown frequency", "five"],
)
def test_a_pick_that_is_not_four_different_known_frequencies_gives_the_default(
    tmp_path: Path, picked: tuple[str, ...]
) -> None:
    ran = brief(tmp_path, *FOUR_QUESTIONS, frequencies=picked)

    assert choices(ran.output, FactorKind.USAGE) == [
        ("Every day", 365),
        ("A few times a week", 150),
        ("About once a week", 50),
        ("About once a month", 12),
    ]


# --- When research or phrasing gives nothing ---

RESEARCH_UNAVAILABLE = (
    WarningCode.RESEARCH_UNAVAILABLE,
    """We couldn't research "frying pan", so the questions and the check list are shorter """
    "than usual.",
)
QUESTIONS_UNAVAILABLE = (
    WarningCode.QUESTIONS_UNAVAILABLE,
    """We couldn't prepare the questions for "frying pan". """
    "What they would have asked about is on the check-before-you-buy list.",
)
DEFAULT_CHOICES = [
    ("Every day", 365),
    ("A few times a week", 150),
    ("About once a week", 50),
    ("About once a month", 12),
]


def test_with_the_search_failing_only_usage_is_asked_and_research_is_unavailable(
    tmp_path: Path,
) -> None:
    # The model has no reply to give: with nothing to read it is not called.
    ran = run(tmp_path, service=failing_search_service(FailureKind.UNAVAILABLE))

    assert asked_about(ran.output) == ["usage-1"]
    assert choices(ran.output, FactorKind.USAGE) == DEFAULT_CHOICES
    assert names(ran.output) == []
    assert warnings(ran.output) == [RESEARCH_UNAVAILABLE]
    assert excluded(ran.output, "Could not search") == [
        (f'Could not search for "{GUIDE_QUERY}"', "unavailable"),
        (f'Could not search for "{CARE_QUERY}"', "unavailable"),
    ]


async def guide_only(request: SearchRequest) -> StoredResponse | FailureKind:
    """A search service whose care search is rate limited."""
    if request.search_query == CARE_QUERY:
        return FailureKind.RATE_LIMITED
    return await finding(FOUND)(request)


def test_one_failing_search_leaves_the_results_of_the_other_to_be_read(tmp_path: Path) -> None:
    ran = run(
        tmp_path, reading(HOB, SIZE), phrasing(HOB_QUESTION, SIZE_QUESTION), service=guide_only
    )

    assert names(ran.output) == ["Hob compatibility", "Pan size"]
    assert warnings(ran.output) == []
    assert excluded(ran.output, "Could not search") == [
        (f'Could not search for "{CARE_QUERY}"', "rate_limited")
    ]


@pytest.mark.parametrize(
    "replies",
    [(ChatError("service down"),), ("not json", "still not json")],
    ids=["the service fails", "the reply is invalid twice"],
)
def test_a_read_that_fails_gives_no_factors_and_no_phrasing_call(
    tmp_path: Path, replies: tuple[str | Exception, ...]
) -> None:
    ran = run(tmp_path, *replies, service=finding(FOUND))

    assert len(ran.requests) == len(replies)
    assert asked_about(ran.output) == ["usage-1"]
    assert warnings(ran.output) == [RESEARCH_UNAVAILABLE]
    assert [summary for summary, _ in excluded(ran.output, "Could not read")] == [
        "Could not read the search results"
    ]


def test_a_read_that_keeps_no_factor_gives_research_unavailable_and_no_phrasing_call(
    tmp_path: Path,
) -> None:
    ran = run(tmp_path, reading(LID), service=finding(FOUND))

    assert len(ran.requests) == 1
    assert asked_about(ran.output) == ["usage-1"]
    assert warnings(ran.output) == [RESEARCH_UNAVAILABLE]


@pytest.mark.parametrize(
    "replies",
    [(ChatError("service down"),), ("not json", "still not json")],
    ids=["the service fails", "the reply is invalid twice"],
)
def test_with_the_phrasing_call_failing_the_factors_stay_and_the_questions_are_unavailable(
    tmp_path: Path, replies: tuple[str | Exception, ...]
) -> None:
    ran = run(tmp_path, reading(*FIVE_FACTORS), *replies, service=finding(FOUND))

    assert asked_about(ran.output) == ["usage-1"]
    assert choices(ran.output, FactorKind.USAGE) == DEFAULT_CHOICES
    assert len(names(ran.output)) == 5
    assert warnings(ran.output) == [QUESTIONS_UNAVAILABLE]
    assert [summary for summary, _ in excluded(ran.output, "Could not phrase")] == [
        "Could not phrase the questions"
    ]


@pytest.mark.parametrize(
    ("read", "questions"),
    [((HOB,), (HOB_QUESTION,)), ((COATING_WEAR,), ())],
    ids=["one factor", "no factor that can be asked about"],
)
def test_few_factors_or_none_to_ask_about_is_not_a_warning(
    tmp_path: Path,
    read: tuple[Mapping[str, object], ...],
    questions: tuple[Mapping[str, object], ...],
) -> None:
    ran = run(tmp_path, reading(*read), phrasing(*questions), service=finding(FOUND))

    assert len(names(ran.output)) == 1
    assert len(ran.output.questions) == len(questions) + 1
    assert warnings(ran.output) == []


# --- The trail of the research ---


def test_each_search_and_the_read_have_a_trail_entry(tmp_path: Path) -> None:
    ran = brief(tmp_path, *FOUR_QUESTIONS)

    entries = [(entry.kind, entry.summary, entry.model_tier) for entry in ran.output.trail]
    assert entries[:3] == [
        (TrailKind.FOUND, f'Searched "{GUIDE_QUERY}": 2 results', None),
        (TrailKind.FOUND, f'Searched "{CARE_QUERY}": 2 results', None),
        (TrailKind.FOUND, "Read 3 search results: 3 cited, 5 factors kept", "medium"),
    ]
    assert {entry.agent for entry in ran.output.trail} == {Agent.BRIEF}


def test_a_search_answered_from_the_cache_says_so_on_the_trail(tmp_path: Path) -> None:
    # The first run stores no brief, because its phrasing call fails; its searches are cached.
    run(tmp_path, reading(HOB), ChatError("service down"), service=finding(FOUND))

    again = run(tmp_path, reading(HOB), phrasing(HOB_QUESTION), service=finding(FOUND))

    assert again.searches == []
    assert [entry.summary for entry in again.output.trail[:2]] == [
        f'Searched "{GUIDE_QUERY}": 2 results, from the cache',
        f'Searched "{CARE_QUERY}": 2 results, from the cache',
    ]


# --- The follow-up search ---

FOLLOW_UP = "frying pan seasoning and care guide"
SEASONING_URL = "https://example.org/seasoning-a-pan"
SEASONING_GUIDE = {
    "url": SEASONING_URL,
    "title": "Seasoning a pan",
    "content": "Season a carbon steel pan again when food starts to stick.",
}
# The follow-up finds one new page, and the guide again.
FOUND_WITH_FOLLOW_UP = {**FOUND, FOLLOW_UP: (SEASONING_GUIDE, GUIDE)}
GAP = {"what": "How a pan is cared for", "reason": "No result says what care a pan needs."}
SEASONING_AGAIN = factor(
    "Seasoning again",
    "care",
    "A carbon steel pan is seasoned more than once.",
    4,
    "Season a carbon steel pan again when food starts to stick.",
)


def test_a_read_that_reports_gaps_is_followed_by_one_search_and_a_second_read(
    tmp_path: Path,
) -> None:
    ran = run(
        tmp_path,
        reading(HOB, SEASONING, gaps=[GAP], follow_up_query=FOLLOW_UP),
        reading(HOB, SEASONING_AGAIN),
        phrasing(HOB_QUESTION),
        service=finding(FOUND_WITH_FOLLOW_UP),
    )

    assert [(search.search_query, search.purpose) for search in ran.searches[2:]] == [
        (FOLLOW_UP, SearchPurpose.CATEGORY)
    ]
    # The second read keeps as many factors as the first, so it replaces it.
    assert names(ran.output) == ["Hob compatibility", "Seasoning again"]
    assert trail(ran.output, "Follow-up") == [
        (TrailKind.DECIDED, f'Follow-up search: "{FOLLOW_UP}"', "the read reported gaps")
    ]
    assert trail(ran.output, "Factor") == [
        (TrailKind.FOUND, 'Factor "Hob compatibility" (compatibility), stated by a tester', None),
        (TrailKind.FOUND, 'Factor "Seasoning again" (care), stated by a tester', None),
    ]


def test_a_second_read_with_fewer_factors_leaves_the_first_read_standing(tmp_path: Path) -> None:
    # In task 1.10 the drill's follow-up read kept no factor and replaced a first read of 8.
    ran = run(
        tmp_path,
        reading(HOB, SIZE, SEASONING, gaps=[GAP], follow_up_query=FOLLOW_UP),
        reading(HOB),
        phrasing(HOB_QUESTION),
        service=finding(FOUND_WITH_FOLLOW_UP),
    )

    assert names(ran.output) == ["Hob compatibility", "Pan size", "Seasoning"]
    assert trail(ran.output, "The first read") == [
        (
            TrailKind.DECIDED,
            "The first read stands",
            "the second read kept 1 factor, the first 3",
        )
    ]


def test_the_second_read_covers_every_search_result_so_far_once(tmp_path: Path) -> None:
    ran = run(
        tmp_path,
        reading(HOB, gaps=[GAP], follow_up_query=FOLLOW_UP),
        reading(HOB, SEASONING_AGAIN),
        phrasing(HOB_QUESTION),
        service=finding(FOUND_WITH_FOLLOW_UP),
    )

    first, second, _ = ran.requests
    shown = second.messages[-1]["content"]
    assert SEASONING_URL not in first.messages[-1]["content"]
    assert shown.index("[3]") < shown.index(CARE_URL) < shown.index("[4]")
    assert shown.index("[4]") < shown.index(SEASONING_URL)
    assert shown.count(GUIDE_URL) == 1
    assert "[5]" not in shown


def test_fewer_than_three_factors_is_followed_up_without_gaps(tmp_path: Path) -> None:
    ran = run(
        tmp_path,
        reading(HOB, SIZE, follow_up_query=FOLLOW_UP),
        reading(HOB, SIZE, SEASONING_AGAIN),
        phrasing(HOB_QUESTION),
        service=finding(FOUND_WITH_FOLLOW_UP),
    )

    assert names(ran.output) == ["Hob compatibility", "Pan size", "Seasoning again"]
    assert trail(ran.output, "Follow-up") == [
        (
            TrailKind.DECIDED,
            f'Follow-up search: "{FOLLOW_UP}"',
            "fewer than 3 factors were sourced",
        )
    ]


def test_three_factors_and_no_gaps_are_not_followed_up(tmp_path: Path) -> None:
    ran = run(
        tmp_path,
        reading(HOB, SIZE, SEASONING, follow_up_query=FOLLOW_UP),
        phrasing(HOB_QUESTION),
        service=finding(FOUND_WITH_FOLLOW_UP),
    )

    assert len(ran.searches) == 2
    assert trail(ran.output, "Follow-up") == []


def test_gaps_without_a_follow_up_query_are_written_to_the_trail_unless_unwritable(
    tmp_path: Path,
) -> None:
    priced = {"what": "What a lid costs in euros", "reason": "No result gives a price."}
    counted_gap = {"what": "Lid sizes", "reason": "No result names the 3 usual sizes."}

    ran = run(
        tmp_path,
        reading(HOB, SIZE, SEASONING, gaps=[priced, counted_gap, GAP]),
        phrasing(HOB_QUESTION),
        service=finding(FOUND),
    )

    assert len(ran.searches) == 2
    assert trail(ran.output, "Not covered") == [
        (
            TrailKind.DECIDED,
            "Not covered by the search results: How a pan is cared for",
            "No result says what care a pan needs.",
        )
    ]


def test_after_a_second_read_only_its_gaps_are_written_to_the_trail(tmp_path: Path) -> None:
    left = {"what": "Which lids fit", "reason": "No result names lid sizes."}

    ran = run(
        tmp_path,
        reading(HOB, gaps=[GAP], follow_up_query=FOLLOW_UP),
        reading(HOB, SEASONING_AGAIN, gaps=[left]),
        phrasing(HOB_QUESTION),
        service=finding(FOUND_WITH_FOLLOW_UP),
    )

    assert [summary for _, summary, _ in trail(ran.output, "Not covered")] == [
        "Not covered by the search results: Which lids fit"
    ]


@pytest.mark.parametrize(
    ("search_query", "reason"),
    [
        ("seasoning and care guide", 'it does not name "frying pan"'),
        ("frying pan " + "care and seasoning " * 6, "it is longer than 120 characters"),
        ("frying pan under 50 euro", "it holds a currency marker"),
        ("frying pan under €50", "it holds a currency marker"),
        ("eco-friendly frying pan care", "it holds a generic environmental term"),
    ],
)
def test_a_follow_up_query_that_breaks_a_rule_is_discarded(
    tmp_path: Path, search_query: str, reason: str
) -> None:
    ran = run(
        tmp_path,
        reading(HOB, gaps=[GAP], follow_up_query=search_query),
        phrasing(HOB_QUESTION),
        service=finding(FOUND),
    )

    assert len(ran.searches) == 2
    assert trail(ran.output, "Discarded") == [
        (TrailKind.EXCLUDED, "Discarded the follow-up search query", reason)
    ]


def test_a_follow_up_query_may_hold_a_size(tmp_path: Path) -> None:
    # In task 1.10, 3 of 4 shortlists discarded their follow-up for a digit.
    sized = "frying pan 28 cm size guide"

    ran = run(
        tmp_path,
        reading(HOB, gaps=[GAP], follow_up_query=sized),
        reading(HOB, SEASONING_AGAIN),
        phrasing(HOB_QUESTION),
        service=finding({**FOUND, sized: (SEASONING_GUIDE,)}),
    )

    assert [search.search_query for search in ran.searches[2:]] == [sized]
    assert trail(ran.output, "Discarded") == []


async def no_follow_up(request: SearchRequest) -> StoredResponse | FailureKind:
    """A search service whose follow-up search is rate limited."""
    if request.search_query == FOLLOW_UP:
        return FailureKind.RATE_LIMITED
    return await finding(FOUND)(request)


@pytest.mark.parametrize(
    ("service", "reason"),
    [(recording(FOUND), "not_recorded"), (no_follow_up, "rate_limited")],
    ids=["recorded sources", "the search fails"],
)
def test_a_follow_up_that_does_not_run_leaves_the_first_read_standing(
    tmp_path: Path, service: SearchService, reason: str
) -> None:
    ran = run(
        tmp_path,
        reading(HOB, gaps=[GAP], follow_up_query=FOLLOW_UP),
        phrasing(HOB_QUESTION),
        service=service,
    )

    assert len(ran.requests) == 2
    assert names(ran.output) == ["Hob compatibility"]
    assert trail(ran.output, "Follow-up search not run") == [
        (TrailKind.EXCLUDED, "Follow-up search not run", reason)
    ]


def test_a_follow_up_that_finds_nothing_new_is_not_read_again(tmp_path: Path) -> None:
    ran = run(
        tmp_path,
        reading(HOB, gaps=[GAP], follow_up_query=FOLLOW_UP),
        phrasing(HOB_QUESTION),
        service=finding({**FOUND, FOLLOW_UP: (GUIDE,)}),
    )

    assert len(ran.requests) == 2
    assert names(ran.output) == ["Hob compatibility"]
    assert trail(ran.output, "The follow-up search") == [
        (TrailKind.DECIDED, "The follow-up search found no new search result", None)
    ]


def test_a_second_read_that_fails_leaves_the_first_read_standing(tmp_path: Path) -> None:
    ran = run(
        tmp_path,
        reading(HOB, gaps=[GAP], follow_up_query=FOLLOW_UP),
        ChatError("service down"),
        phrasing(HOB_QUESTION),
        service=finding(FOUND_WITH_FOLLOW_UP),
    )

    assert names(ran.output) == ["Hob compatibility"]
    assert asked_about(ran.output) == ["researched-1", "usage-1"]
    assert [summary for _, summary, _ in trail(ran.output, "Could not read")] == [
        "Could not read the search results"
    ]


# --- The brief cache ---


def test_a_second_run_of_the_category_is_answered_from_the_brief_cache_and_says_so(
    tmp_path: Path,
) -> None:
    first = brief(tmp_path, *FOUR_QUESTIONS)

    # No reply and no search service: a model call or a search would fail the test.
    again = run(tmp_path, now=NOON + timedelta(days=40))

    assert again.requests == []
    assert again.searches == []
    assert again.output.factors == first.output.factors
    assert again.output.questions == first.output.questions
    assert again.output.warnings == ()
    lead, *replayed = again.output.trail
    assert (lead.kind, lead.summary) == (
        TrailKind.FOUND,
        "Category research for frying pan from the cache, researched on 2026-10-13",
    )
    assert tuple(replayed) == first.output.trail


def test_another_category_is_researched_on_its_own(tmp_path: Path) -> None:
    brief(tmp_path, *FOUR_QUESTIONS)
    kettle = Request(original_text="a kettle", category="kettle", scope=Scope.TUNED)
    found = {
        "kettle buying guide what to look for": (GUIDE,),
        "kettle care maintenance and replacement parts": (CARE,),
    }

    ran = run(
        tmp_path, reading(HOB), phrasing(HOB_QUESTION), request=kettle, service=finding(found)
    )

    assert len(ran.searches) == 2
    assert len(ran.requests) == 2


@pytest.mark.parametrize(
    ("replies", "found"),
    [
        ((reading(*FIVE_FACTORS), ChatError("service down")), FOUND),
        ((ChatError("service down"),), FOUND),
        (
            (
                reading(HOB, gaps=[GAP], follow_up_query=FOLLOW_UP),
                ChatError("service down"),
                phrasing(HOB_QUESTION),
            ),
            FOUND_WITH_FOLLOW_UP,
        ),
    ],
    ids=["the phrasing failed", "the read failed", "the second read failed"],
)
def test_a_brief_with_a_failed_model_call_is_researched_again(
    tmp_path: Path,
    replies: tuple[str | Exception, ...],
    found: Mapping[str, Sequence[Mapping[str, str]]],
) -> None:
    run(tmp_path, *replies, service=finding(found))

    again = brief(tmp_path, *FOUR_QUESTIONS)

    assert len(again.requests) == 2
    assert warnings(again.output) == []


def test_a_brief_with_a_failed_template_search_is_researched_again(tmp_path: Path) -> None:
    run(tmp_path, reading(HOB, SIZE), phrasing(HOB_QUESTION, SIZE_QUESTION), service=guide_only)

    again = brief(tmp_path, *FOUR_QUESTIONS)

    # The guide search is answered from the search cache; only the care search runs again.
    assert [search.search_query for search in again.searches] == [CARE_QUERY]
    assert len(again.requests) == 2


def test_a_brief_with_no_factors_is_stored_and_still_warns(tmp_path: Path) -> None:
    run(tmp_path, reading(LID), service=finding(FOUND))

    again = run(tmp_path)

    assert again.requests == []
    assert warnings(again.output) == [RESEARCH_UNAVAILABLE]


def test_a_brief_with_fewer_than_three_factors_is_researched_again_after_a_day(
    tmp_path: Path,
) -> None:
    replies = (reading(HOB), phrasing(HOB_QUESTION))
    run(tmp_path, *replies, service=finding(FOUND))

    same_day = run(tmp_path, now=NOON + timedelta(hours=23))
    next_day = run(tmp_path, *replies, now=NOON + timedelta(days=1, minutes=1))

    assert same_day.requests == []
    assert len(next_day.requests) == 2
    assert next_day.searches == []


def test_a_brief_stored_by_other_prompts_or_models_is_researched_again(tmp_path: Path) -> None:
    older = Brief(usage_frequencies=("every_day", "about_once_a_week"))
    brief_store(tmp_path, Clock(NOON)).write("frying pan", "an-older-version", older)

    ran = brief(tmp_path, *FOUR_QUESTIONS)

    assert len(ran.requests) == 2
    assert len(names(ran.output)) == 5


# --- The local category term ---


def test_category_research_gives_the_local_term_and_keeps_it_with_the_brief(
    tmp_path: Path,
) -> None:
    first = brief(tmp_path, *FOUR_QUESTIONS)

    again = run(tmp_path, now=NOON + timedelta(days=40))

    (asked,) = first.term_requests
    assert asked.model == MODEL_IDS["medium"]
    assert "frying pan" in asked.messages[-1]["content"]
    assert first.output.local_term == "koekenpan"
    assert ("Local category term: koekenpan", None) in [
        (entry.summary, entry.reason) for entry in first.output.trail
    ]
    assert again.term_requests == ()
    assert again.output.local_term == "koekenpan"


def test_a_failed_call_for_the_local_term_leaves_it_missing_and_the_brief_unstored(
    tmp_path: Path,
) -> None:
    failed = run(
        tmp_path,
        reading(*FIVE_FACTORS),
        phrasing(*FOUR_QUESTIONS),
        service=finding(FOUND),
        local_terms={"frying pan": ChatError("service down")},
    )

    again = brief(tmp_path, *FOUR_QUESTIONS)

    assert failed.output.local_term is None
    assert warnings(failed.output) == []
    assert "Could not find the local category term" in [
        entry.summary for entry in failed.output.trail
    ]
    assert len(again.requests) == 2
    assert again.output.local_term == "koekenpan"


@pytest.mark.parametrize(
    ("term", "reason"),
    [
        ("koekenpan 28 cm", "it holds a digit"),
        ("goede koekenpan voor elke dag", "it is more than 3 words"),
        ("eco-friendly koekenpan", "it holds a generic environmental term"),
    ],
)
def test_a_local_term_that_is_not_a_few_plain_words_is_left_out(
    tmp_path: Path, term: str, reason: str
) -> None:
    ran = run(
        tmp_path,
        reading(*FIVE_FACTORS),
        phrasing(*FOUR_QUESTIONS),
        service=finding(FOUND),
        local_terms={"frying pan": json.dumps({"local_term": term})},
    )

    assert ran.output.local_term is None
    assert ("Left out the local category term", reason) in [
        (entry.summary, entry.reason) for entry in ran.output.trail
    ]


def test_a_local_term_with_no_word_in_it_is_asked_for_again(tmp_path: Path) -> None:
    # Task 1.15's live run: the model now and then wrote "..." as the term.
    ran = run(
        tmp_path,
        reading(*FIVE_FACTORS),
        phrasing(*FOUR_QUESTIONS),
        service=finding(FOUND),
        local_terms={"frying pan": json.dumps({"local_term": "..."})},
    )

    first, second = ran.term_requests
    assert len(second.messages) > len(first.messages)
    assert ran.output.local_term is None
    assert "Could not find the local category term" in [entry.summary for entry in ran.output.trail]


def test_the_read_reasons_little_and_the_phrasing_in_full(tmp_path: Path) -> None:
    ran = brief(tmp_path, *FOUR_QUESTIONS)

    assert [request.low_effort for request in ran.requests] == [True, False]


def test_the_read_and_the_phrasing_have_room_to_reason_before_they_answer(tmp_path: Path) -> None:
    # The live reads of task 1.7 used up to 7,485 tokens, the reasoning included.
    ran = brief(tmp_path, *FOUR_QUESTIONS)

    assert [(request.max_tokens, request.timeout) for request in ran.requests] == [
        (16000, 120.0),
        (16000, 120.0),
    ]


def test_the_read_is_given_the_category_and_each_search_result_once_by_number(
    tmp_path: Path,
) -> None:
    ran = run(tmp_path, reading(*FIVE_FACTORS), phrasing(), service=finding(FOUND))

    read = ran.requests[0]
    shown = read.messages[-1]["content"]
    assert read.model == MODEL_IDS["medium"]
    assert "frying pan" in shown
    assert shown.index("[1]") < shown.index(GUIDE_URL) < shown.index("[2]")
    assert shown.index("[2]") < shown.index(MAKER_URL) < shown.index("[3]")
    assert shown.index("[3]") < shown.index(CARE_URL)
    assert shown.count(GUIDE_URL) == 1
    assert "[4]" not in shown
    assert "Only pans with a magnetic base work on an induction hob." in shown


# --- A pasted link ---

LINKED_PAN = ProductOption(
    id="option-link", name="De Buyer Mineral B koekenpan 28 cm", link=LINK, **seen_price("54.95")
)
PAN_AT_LINK = Request(
    original_text=f"{LINK} budget 60 euro",
    product_url=LINK,
    category="frying pan",
    budget=Decimal(60),
    scope=Scope.TUNED,
)


def test_a_linked_product_is_asked_two_compatibility_or_requirement_questions_and_usage(
    tmp_path: Path,
) -> None:
    ran = run(
        tmp_path,
        reading(*FIVE_FACTORS),
        phrasing(*FOUR_QUESTIONS),
        request=PAN_AT_LINK,
        linked=LINKED_PAN,
        service=finding(FOUND),
    )

    assert asked_about(ran.output) == ["researched-1", "researched-2", "usage-1"]
    # The calls that write the questions never see the product, so none is a claim about it.
    for request in ran.requests:
        assert LINKED_PAN.name not in request.messages[-1]["content"]
    assert (
        "Left 2 phrased questions unasked",
        "the product at the link is already chosen: at most 2 questions about compatibility or "
        "requirements are asked besides how often the product is used",
    ) in [(entry.summary, entry.reason) for entry in ran.output.trail]


def test_with_a_linked_product_a_stated_answer_frees_its_place_for_the_next_one_that_fits(
    tmp_path: Path,
) -> None:
    lid = factor(
        "Lid fit", "requirement", "A lid that does not fit is bought again.", 1, "most households"
    )
    lid_question = asked(5, "Do you need a lid?", "Not every pan comes with one.", "Yes", "No")
    request = PAN_AT_LINK.model_copy(update={"original_text": f"{LINK} for induction"})

    ran = run(
        tmp_path,
        reading(*FIVE_FACTORS, lid),
        phrasing(*FOUR_QUESTIONS, lid_question),
        request=request,
        linked=LINKED_PAN,
        service=finding(FOUND),
        stated_replies=(stated(requirement(1, "for induction", choice=1)),),
    )

    # The hob is stated; the two care questions between size and lid are passed over.
    assert asked_about(ran.output) == ["researched-2", "researched-6", "usage-1"]
