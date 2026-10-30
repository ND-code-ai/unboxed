import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import pytest

from fakes import (
    NOT_JUDGED_BY_PAGE,
    UNUSED_SOURCES,
    Clock,
    counted,
    extraction,
    failing_page_service,
    failing_search_service,
    fake_chat,
    fake_chat_with_reads,
    finding,
    judged,
    typing,
)
from shopper.agents.brief.agent import research_brief
from shopper.agents.brief.usage_frequency import USAGE_FACTOR
from shopper.agents.default import DEFAULT_AGENTS
from shopper.agents.lca.agent import estimate_co2e
from shopper.agents.stubs import HOB_FACTOR, HOB_QUESTION, STUB_AGENTS, USAGE_QUESTION
from shopper.config import SearchPurpose
from shopper.llm import ChatTimeoutError
from shopper.state import Answer, AnswerStatus
from shopper.terminal.cli import ask, main, parse_arguments, run
from shopper.tools.fixtures import fixture_page_service, fixture_search_service
from shopper.tools.results import (
    FailureKind,
    PageRequest,
    SearchRequest,
    SearchService,
    StoredResponse,
)
from shopper.tools.sources import Sources, fixture_sources

# The questions come from the real brief agent; the options are the stub pans.
REAL_BRIEF = replace(STUB_AGENTS, brief=research_brief)

SOURCES = UNUSED_SOURCES
FRYING_PAN = "I need a new frying pan, budget 50 euro"
FRYING_PAN_REPLY = extraction("frying pan", "tuned", "50 euro", 50)
# The reply of the call that reads what the request states, when it states nothing.
NOTHING_STATED = json.dumps({"requirements": []})
UNREADABLE_BUDGET = (
    'We couldn\'t read "5o euro" as an amount, so no budget is applied. '
    'To set one, start again with an amount in euro, such as "budget €50".'
)
# The lines printed as the supervisor and the brief agent start.
READING = "Reading your request..."
RESEARCHING = "Researching what to ask about..."


def output_of(
    capsys: pytest.CaptureFixture[str], text: str, *replies: str | Exception
) -> list[str]:
    chat, _ = fake_chat(replies)
    assert asyncio.run(run(text, chat, SOURCES, agents=STUB_AGENTS)) == 0
    return capsys.readouterr().out.splitlines()


def never_asked(prompt: str) -> str:
    raise AssertionError("nothing is asked with --skip-all")


def skipped_all(capsys: pytest.CaptureFixture[str], text: str, reply: str) -> list[str]:
    """The output of a run with --skip-all."""
    chat, _ = fake_chat([reply])
    assert (
        asyncio.run(run(text, chat, SOURCES, never_asked, skip_all=True, agents=STUB_AGENTS)) == 0
    )
    return capsys.readouterr().out.splitlines()


def typed_run(
    capsys: pytest.CaptureFixture[str], reply: str, *typed: str, text: str = FRYING_PAN
) -> list[str]:
    """The output of a run with these lines typed at the prompts."""
    chat, _ = fake_chat([reply])
    assert asyncio.run(run(text, chat, SOURCES, typing(*typed), agents=STUB_AGENTS)) == 0
    return capsys.readouterr().out.splitlines()


# --- What was understood, above the questions ---


def test_it_opens_with_what_was_understood(capsys: pytest.CaptureFixture[str]) -> None:
    lines = skipped_all(capsys, FRYING_PAN, FRYING_PAN_REPLY)

    assert lines[:2] == [READING, "Looking for: frying pan · Budget: €50"]
    assert "Scope: tuned" not in lines


def test_a_line_is_printed_as_each_agent_starts(capsys: pytest.CaptureFixture[str]) -> None:
    lines = skipped_all(capsys, FRYING_PAN, FRYING_PAN_REPLY)

    assert lines[2] == RESEARCHING
    options = lines.index("Finding options and their prices...")
    # The LCA and second-hand agents start at once, then the report follows.
    assert sorted(lines[options + 1 : options + 3]) == [
        "Checking for used options...",
        "Estimating the CO2e of making each option...",
    ]
    assert lines[options + 3] == ""


def test_a_budget_that_was_not_applied_opens_with_no_budget_and_its_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = skipped_all(
        capsys,
        "I need a new frying pan, budget 5o euro",
        extraction("frying pan", "tuned", "5o euro", None),
    )

    assert lines[:4] == [
        READING,
        "Looking for: frying pan · Budget: none given",
        RESEARCHING,
        UNREADABLE_BUDGET,
    ]


# --- A pasted link, on the recorded pages ---

FIXTURES = Path(__file__).parent.parent / "fixtures"
# The day a run on the recorded pages reads them, as the report writes it beside each price.
READ_AT = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
SEEN_ON = "22 October 2026"


def recorded_sources(cache: Path) -> Sources:
    """The fixture twins on a clock the test sets, so a price says the day it was seen."""
    return replace(fixture_sources(FIXTURES, cache), clock=Clock(READ_AT))


PAN_LINK = "https://example.org/shop/de-buyer-mineral-b-28"
BLOCKED_LINK = "https://example.org/shop/blocked"
PAN_NAME = "De Buyer Mineral B koekenpan 28 cm"
PAGE_DETAILS = json.dumps(
    {
        "materials": [{"name": "carbon steel", "form": None}],
        "weight_amount": 2.1,
        "weight_unit": "kg",
    }
)
LINK_UNREADABLE = (
    "We couldn't read the product at your link, so it is not among the options below. "
    "These are options for frying pan."
)


def link_run(
    capsys: pytest.CaptureFixture[str], cache: Path, text: str, *replies: str
) -> tuple[list[str], list[PageRequest]]:
    """The output of a --skip-all run on the recorded pages, and the page requests that reached
    the service: each one a network call."""
    chat, _ = fake_chat(replies)
    fetch_page, fetched = counted(fixture_page_service(FIXTURES))
    sources = replace(recorded_sources(cache), fetch_page=fetch_page)
    assert (
        asyncio.run(run(text, chat, sources, never_asked, skip_all=True, agents=STUB_AGENTS)) == 0
    )
    return capsys.readouterr().out.splitlines(), fetched


def test_a_pasted_link_is_a_product_option_on_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines, _ = link_run(capsys, tmp_path, PAN_LINK, extraction("frying pan", "tuned"), PAGE_DETAILS)

    assert lines[1] == "Looking for: frying pan · Budget: none given"
    block = lines.index(PAN_NAME)
    assert (
        lines[block + 1]
        == "Price: €54.95, shipping not stated, price seen at example.org on 22 October 2026"
    )
    assert lines[block + 2] == f"Link: {PAN_LINK}"


def test_a_second_run_of_the_same_link_makes_no_network_call(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    replies = (extraction("frying pan", "tuned"), PAGE_DETAILS)
    _, first = link_run(capsys, tmp_path, PAN_LINK, *replies)
    lines, second = link_run(capsys, tmp_path, PAN_LINK, *replies)

    assert len(first) == 1
    assert second == []
    assert PAN_NAME in lines
    assert any("Read the product at the link from the cache" in line for line in lines)


def test_an_unreadable_link_with_a_category_continues_with_the_warning(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines, _ = link_run(
        capsys, tmp_path, f"{BLOCKED_LINK} a frying pan", extraction("frying pan", "tuned")
    )

    assert lines[:4] == [
        READING,
        "Looking for: frying pan · Budget: none given",
        RESEARCHING,
        LINK_UNREADABLE,
    ]
    assert "Non-stick pan" in lines


def test_an_unreadable_link_with_no_category_asks_for_the_product_name(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines, _ = link_run(capsys, tmp_path, BLOCKED_LINK, extraction(None, "general"))

    assert lines == [
        READING,
        "We couldn't read the product at your link. "
        "Name the product to start, for example 'a frying pan, budget €50'.",
    ]


def test_a_link_whose_product_names_no_category_opens_by_saying_so(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines, _ = link_run(
        capsys,
        tmp_path,
        PAN_LINK,
        extraction(None, "general"),
        extraction(None, "general"),
        PAGE_DETAILS,
    )

    assert lines[1:3] == ["Looking for: the product at your link · Budget: none given", RESEARCHING]


# --- The questions ---

# The third choice of the usage question is the frequency "about once a week".
USAGE_CHOSEN = Answer(
    factor_id=USAGE_QUESTION.factor_id, status=AnswerStatus.CHOSEN, choice_id="about_once_a_week"
)
HOB_CHOSEN = Answer(
    factor_id=HOB_QUESTION.factor_id, status=AnswerStatus.CHOSEN, choice_id="choice-3"
)
HOB_NOT_SURE = Answer(factor_id=HOB_QUESTION.factor_id, status=AnswerStatus.NOT_SURE)


def asked(*typed: str) -> tuple[Answer, ...]:
    """The answers to the two stub questions with these lines typed at the prompts."""
    return ask((USAGE_QUESTION, HOB_QUESTION), (USAGE_FACTOR, HOB_FACTOR), typing(*typed))


def test_each_question_is_shown_with_its_reason_and_numbered_choices(
    capsys: pytest.CaptureFixture[str],
) -> None:
    asked("3", "3")

    lines = capsys.readouterr().out.splitlines()
    first = lines.index("How often will you use it?")
    assert lines[first : first + 6] == [
        "How often will you use it?",
        "It sets the cost per use.",
        "1. Every day",
        "2. A few times a week",
        "3. About once a week",
        "4. About once a month",
    ]
    assert "Which hob do you cook on?" in lines


def test_the_keys_are_shown_once_above_the_first_question(
    capsys: pytest.CaptureFixture[str],
) -> None:
    asked("3", "3")

    lines = capsys.readouterr().out.splitlines()
    assert lines[:3] == [
        "",
        "Type the number of a choice, n for not sure, or press Enter to skip. "
        "Type skip all to skip the rest.",
        "",
    ]
    assert lines.count(lines[1]) == 1


def test_with_no_questions_nothing_is_shown(capsys: pytest.CaptureFixture[str]) -> None:
    assert ask((), (), typing()) == ()
    assert capsys.readouterr().out == ""


def test_a_typed_number_is_that_choice() -> None:
    assert asked("3", "3") == (USAGE_CHOSEN, HOB_CHOSEN)


@pytest.mark.parametrize("typed", ["n", " N "])
def test_n_is_not_sure(typed: str) -> None:
    assert asked("3", typed) == (USAGE_CHOSEN, HOB_NOT_SURE)


def test_enter_skips_one_question() -> None:
    assert asked("", "3") == (HOB_CHOSEN,)


@pytest.mark.parametrize("typed", ["skip all", " Skip All "])
def test_skip_all_at_the_second_question_keeps_the_first_answer(typed: str) -> None:
    assert asked("3", typed) == (USAGE_CHOSEN,)


def test_skip_all_at_the_first_question_shows_no_second_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert asked("skip all", "3") == ()
    assert "Which hob do you cook on?" not in capsys.readouterr().out.splitlines()


def test_anything_that_is_not_a_listed_number_is_asked_again(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The usage question has four choices and the hob question three.
    answers = asked("7", "often", "0", "3", "4", "3")

    lines = capsys.readouterr().out.splitlines()
    assert answers == (USAGE_CHOSEN, HOB_CHOSEN)
    assert lines.count("Type a number from 1 to 4, n for not sure, or press Enter to skip.") == 3
    assert lines.count("Type a number from 1 to 3, n for not sure, or press Enter to skip.") == 1
    assert lines.count("How often will you use it?") == 1


def test_input_that_runs_out_skips_the_remaining_questions() -> None:
    assert asked("3") == (USAGE_CHOSEN,)


# --- The report, end to end on the stub agents ---

# The figures of the frying pan worked example in docs/architecture/calculations.md.
WORKED_EXAMPLE = (
    "Cost per year: €10",
    "Purchases over 10 years: 5",
    "Cost over 10 years: €100",
    "Cost per year: €1.33",
    "Purchases over 10 years: 1",
    "Cost over 10 years: €40",
    "Over 10 years: Carbon steel pan costs €60 less than Non-stick pan. A lifespan behind "
    "this is a rough estimate.",
)
STUB_TRAIL = ("Trail", "tco decided: Stub: two fixed frying pans, not searched for")


def test_the_frying_pan_run_with_typed_answers_prints_every_part_of_the_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = typed_run(capsys, FRYING_PAN_REPLY, "3", "3")

    expected = (
        "Looking for: frying pan · Budget: €50",
        "Lifespan sourced for 0 of 2 options. CO2e to make: not found for 2.",
        *WORKED_EXAMPLE,
        "Cost per use: €0.20",
        "Cost per use: €0.03",
        "Check before you buy",
        "Could not be confirmed",
        "- Hob compatibility: Not every pan works on every hob. (Non-stick pan, Carbon steel pan)",
        *STUB_TRAIL,
    )
    assert [line for line in expected if line not in lines] == []
    assert any(line.startswith("supervisor ") for line in lines)
    assert "Over your budget" not in lines


def test_the_frying_pan_run_with_skip_all_asks_nothing_and_prints_the_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = skipped_all(capsys, FRYING_PAN, FRYING_PAN_REPLY)

    expected = (
        "Looking for: frying pan · Budget: €50",
        "Lifespan sourced for 0 of 2 options. CO2e to make: not found for 2.",
        *WORKED_EXAMPLE,
        "Cost per use: not available (uses per year not given)",
        "Check before you buy",
        "Not yet known",
        "- Hob compatibility: Not every pan works on every hob.",
        *STUB_TRAIL,
    )
    assert [line for line in expected if line not in lines] == []
    assert "How often will you use it?" not in lines


def test_a_fridge_request_prints_the_energy_caveat(capsys: pytest.CaptureFixture[str]) -> None:
    lines = skipped_all(capsys, "a fridge", extraction("fridge", "energy_heavy"))

    assert (
        "Energy and water use are not included in these figures. For this kind of product they "
        "are a large part of the cost, so the order of these options can change once they are "
        "counted."
    ) in lines


def test_a_budget_warning_is_shown_before_the_questions_and_again_on_the_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = typed_run(
        capsys,
        extraction("frying pan", "tuned", "5o euro", None),
        "3",
        "3",
        text="I need a new frying pan, budget 5o euro",
    )

    first_question = lines.index("How often will you use it?")
    assert lines[:first_question].count(UNREADABLE_BUDGET) == 1
    assert lines[first_question:].count(UNREADABLE_BUDGET) == 1


# --- Category research, with the real brief agent ---

GUIDE_QUERY = "frying pan buying guide what to look for"
CARE_QUERY = "frying pan care maintenance and replacement parts"
FOUND = {
    GUIDE_QUERY: (
        {
            "url": "https://www.consumentenbond.nl/koekenpan/kopen",
            "title": "Koekenpan kopen",
            "content": "Only pans with a magnetic base work on an induction hob.",
        },
    ),
    CARE_QUERY: (
        {
            "url": "https://maker.example.com/manual",
            "title": "Manual",
            "content": "Our non-stick pans must be washed by hand to protect the coating.",
        },
    ),
}
READ = json.dumps(
    {
        "factors": [
            {
                "name": "Hob compatibility",
                "kind": "compatibility",
                "why": "Not every pan works on an induction hob.",
                "result": 1,
                "quote": "Only pans with a magnetic base work on an induction hob.",
                "stated_by": "tester",
                "amount_quote": None,
                "interval_quote": None,
                "pack_count_quote": None,
            },
            {
                "name": "Hand washing",
                "kind": "care",
                "why": "Some coatings do not survive a dishwasher.",
                "result": 2,
                "quote": "must be washed by hand to protect the coating",
                "stated_by": "manufacturer",
                "amount_quote": None,
                "interval_quote": None,
                "pack_count_quote": None,
            },
        ],
        "gaps": [],
        "follow_up_query": None,
    }
)
PHRASE = json.dumps(
    {
        "questions": [
            {
                "factor": 1,
                "text": "Which hob do you cook on?",
                "reason": "Not every pan works on every hob.",
                "choices": ["Induction", "Gas", "Electric or ceramic"],
            },
            {
                "factor": 2,
                "text": "Some frying pans are washed by hand only.",
                "reason": None,
                "choices": [],
            },
        ],
        "usage_frequencies": [],
    }
)
FINDING = finding(FOUND)
UNDERSTOOD = [READING, "Looking for: frying pan · Budget: €50", RESEARCHING]
USAGE_BLOCK = [
    "",
    "How often will you use it?",
    "It sets the cost per use.",
    "1. Every day",
    "2. A few times a week",
    "3. About once a week",
    "4. About once a month",
]


def research_run(
    capsys: pytest.CaptureFixture[str],
    cache: Path,
    *replies: str,
    service: SearchService = FINDING,
    typed: tuple[str, ...] = (),
    text: str = FRYING_PAN,
    stated: tuple[str | Exception, ...] = (NOTHING_STATED,),
) -> list[str]:
    """The output of a frying pan run with the real brief and the stub options.

    The replies to the call that reads what the request states come last.
    """
    chat, _ = fake_chat([FRYING_PAN_REPLY, *replies, *stated])
    sources = Sources(search=service, fetch_page=failing_page_service(), cache_folder=cache)
    assert asyncio.run(run(text, chat, sources, typing(*typed), agents=REAL_BRIEF)) == 0
    return capsys.readouterr().out.splitlines()


def test_researched_questions_are_shown_with_their_source_lines_and_usage_without_one(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines = research_run(capsys, tmp_path, READ, PHRASE, typed=("1", "1", "3"))

    hob = lines.index("Which hob do you cook on?")
    assert lines[hob : hob + 6] == [
        "Which hob do you cook on?",
        "Not every pan works on every hob.",
        "1. Induction",
        "2. Gas",
        "3. Electric or ceramic",
        "Source: consumentenbond.nl",
    ]
    care = lines.index("Some frying pans are washed by hand only. Is that fine with you?")
    assert lines[care + 1 : care + 5] == [
        "Some coatings do not survive a dishwasher.",
        "1. That's fine",
        "2. I'd rather avoid it",
        "Source: maker.example.com (the manufacturer states)",
    ]
    usage = lines.index("How often will you use it?")
    assert lines[usage - 1 : usage + 7] == [*USAGE_BLOCK, ""]


SPRAY_PAGE = {
    "url": "https://www.consumentenbond.nl/koekenpan/onderhoud",
    "title": "Onderhoud",
    "content": "A cooking spray costs $6 and is bought again every 3 months.",
}
COST_READ = json.dumps(
    {
        "factors": [
            {
                "name": "Cooking spray",
                "kind": "recurring_cost",
                "why": "A coated pan is kept with a spray that is bought again.",
                "result": 1,
                "quote": "A cooking spray costs $6",
                "stated_by": "tester",
                "amount_quote": "A cooking spray costs $6",
                "interval_quote": "every 3 months",
                "pack_count_quote": None,
            }
        ],
        "gaps": [],
        "follow_up_query": None,
    }
)
NO_QUESTIONS = json.dumps({"questions": [], "usage_frequencies": []})


def test_a_typical_yearly_cost_is_shown_above_the_questions_and_on_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    service = finding({GUIDE_QUERY: (SPRAY_PAGE,), CARE_QUERY: ()})

    lines = research_run(capsys, tmp_path, COST_READ, NO_QUESTIONS, service=service, typed=("1",))

    # $6 at 1.1253 per euro is €5.33, four times a year.
    cost = (
        "Cooking spray: typically €21.32 a year (consumentenbond.nl), converted from USD at a "
        "fixed rate."
    )
    keys = lines.index(KEYS)
    assert lines[3:keys] == [cost, ""]
    assert cost in lines[keys:]
    assert "Is that fine with you?" not in " ".join(lines)


def test_with_the_search_failing_the_cli_shows_the_usage_question_and_research_unavailable(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    failing = failing_search_service(FailureKind.UNAVAILABLE)

    lines = research_run(capsys, tmp_path, service=failing, typed=("1",))

    assert lines[:4] == [
        *UNDERSTOOD,
        """We couldn't research "frying pan", so the questions and the check list are """
        "shorter than usual.",
    ]
    assert lines[6:13] == USAGE_BLOCK
    assert lines[13] == ""


def test_with_the_phrasing_call_failing_the_cli_shows_the_usage_question_and_questions_unavailable(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines = research_run(capsys, tmp_path, READ, "not json", "still not json", typed=("1",))

    assert lines[:4] == [
        *UNDERSTOOD,
        """We couldn't prepare the questions for "frying pan". """
        "What they would have asked about is on the check-before-you-buy list.",
    ]
    assert lines[6:13] == USAGE_BLOCK
    assert lines[13] == ""
    assert "- Hob compatibility: Not every pan works on an induction hob." in lines


# --- What the request already states ---

INDUCTION_DAILY = "a frying pan for induction, I cook every day"
# The factors are numbered as the call shows them: hob 1, hand washing 2, usage 3.
STATED = json.dumps(
    {
        "requirements": [
            {
                "factor": 1,
                "choice": 1,
                "value": None,
                "frequency": None,
                "phrase": "for induction",
            },
            {
                "factor": 3,
                "choice": None,
                "value": None,
                "frequency": "every_day",
                "phrase": "I cook every day",
            },
        ]
    }
)
STATED_LINES = [
    'From your request: Hob compatibility: Induction ("for induction")',
    'From your request: Every day, 365 uses a year ("I cook every day")',
]
KEYS = (
    "Type the number of a choice, n for not sure, or press Enter to skip. "
    "Type skip all to skip the rest."
)


def test_what_the_request_states_is_shown_above_the_questions_and_not_asked(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines = research_run(
        capsys, tmp_path, READ, PHRASE, typed=("1",), text=INDUCTION_DAILY, stated=(STATED,)
    )

    keys = lines.index(KEYS)
    assert lines[3:keys] == [*STATED_LINES, ""]
    assert "Which hob do you cook on?" not in lines
    assert "How often will you use it?" not in lines
    report = lines[keys:]
    for line in STATED_LINES:
        assert line in report[report.index("Some coatings do not survive a dishwasher.") :]


def test_with_the_stated_call_failing_the_cli_asks_every_question_and_shows_the_warning(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines = research_run(
        capsys,
        tmp_path,
        READ,
        PHRASE,
        typed=("1", "1", "1"),
        text=INDUCTION_DAILY,
        stated=("not json", "still not json"),
    )

    assert lines[3] == (
        "We couldn't pick out the requirements in your request, so only your answers to the "
        "questions are applied."
    )
    assert "Which hob do you cook on?" in lines
    assert "How often will you use it?" in lines
    assert not any(line.startswith("From your request:") for line in lines)


# --- Three categories on the recorded searches ---


def read_reply(*factors: tuple[str, str, str, int, str, str]) -> str:
    """The read's reply: each factor is (name, kind, why, result, quote, stated_by)."""
    keys = ("name", "kind", "why", "result", "quote", "stated_by")
    no_amount = {"amount_quote": None, "interval_quote": None, "pack_count_quote": None}
    return json.dumps(
        {
            "factors": [dict(zip(keys, factor, strict=True)) | no_amount for factor in factors],
            "gaps": [],
            "follow_up_query": None,
        }
    )


def phrasing_reply(*questions: tuple[str, str | None, tuple[str, ...]]) -> str:
    """The phrasing reply: each question is (text, reason, choices), for factors 1, 2, ..."""
    return json.dumps(
        {
            "questions": [
                {"factor": number, "text": text, "reason": reason, "choices": list(choices)}
                for number, (text, reason, choices) in enumerate(questions, start=1)
            ],
            "usage_frequencies": [],
        }
    )


# Each category: what the user types, the supervisor's reply, the read's reply quoting the
# recorded search results, the phrasing reply, and the source line under each question.
CATEGORIES = {
    "frying pan": (
        "I need a new frying pan, budget 50 euro",
        FRYING_PAN_REPLY,
        read_reply(
            (
                "Pan size",
                "requirement",
                "A pan that is too small crowds the food.",
                3,
                "A small frying pan of around 8 inches is usually sufficient for cooking eggs",
                "manufacturer",
            ),
            (
                "Pan material",
                "requirement",
                "Each material suits a different way of cooking.",
                2,
                "Nonstick frying pans work well for scrambled eggs, pancakes, and delicate foods "
                "such as fish.",
                "tester",
            ),
            (
                "Seasoning",
                "care",
                "A cast iron pan is non-stick only once it is seasoned.",
                4,
                "Once your cast iron pan is seasoned properly, your pan is naturally non-stick.",
                "tester",
            ),
        ),
        phrasing_reply(
            (
                "Which size of pan do you need?",
                "A pan that is too small crowds the food.",
                ("Around 8 inches", "Larger"),
            ),
            (
                "What do you cook most?",
                "Each material suits a different way of cooking.",
                ("Searing meat", "Eggs, pancakes or fish", "A mix of both"),
            ),
            ("Some frying pans need seasoning before they are non-stick.", None, ()),
        ),
        [
            "Source: all-clad.com (the manufacturer states)",
            "Source: consumerreports.org",
            "Source: extension.umaine.edu",
        ],
    ),
    "kettle": (
        "I need a new kettle",
        extraction("kettle", "tuned"),
        read_reply(
            (
                "Capacity",
                "requirement",
                "A kettle that is too small is filled again and again.",
                1,
                "If you like to boil multiple cups of tea at once, be sure and look for a larger "
                "kettle.",
                "manufacturer",
            ),
            (
                "Temperature settings",
                "requirement",
                "Some drinks need water below boiling.",
                2,
                "For kettles with multiple temperatures, we looked for clearly marked and easily "
                "adjustable settings.",
                "tester",
            ),
            (
                "Rinsing after use",
                "care",
                "Water left standing leaves stains and buildup.",
                5,
                "always be sure to both empty and rinse it thoroughly after use",
                "seller",
            ),
        ),
        phrasing_reply(
            (
                "How much water do you usually boil at once?",
                "A kettle that is too small is filled again and again.",
                ("A single cup", "A full pot"),
            ),
            (
                "Do you make drinks that need water below boiling?",
                "Some drinks need water below boiling.",
                ("Yes", "No"),
            ),
            ("Some kettles need emptying and rinsing after every use.", None, ()),
        ),
        [
            "Source: kitchenaid.com (the manufacturer states)",
            "Source: nytimes.com",
            "Source: abt.com (the seller states)",
        ],
    ),
    "drill": (
        "I need a cordless drill",
        extraction("drill", "tuned"),
        read_reply(
            (
                "Drilling material",
                "requirement",
                "Masonry and concrete need a more powerful drill.",
                1,
                "If you're drilling into harder surfaces like masonry or concrete, you'll want "
                "something high-powered such as an SDS drill.",
                "seller",
            ),
            (
                "Weight in the hand",
                "requirement",
                "A drill that is heavy with its battery tires the arm.",
                2,
                "hold one with the battery clipped in place to see how it handles",
                "tester",
            ),
            (
                "Cleaning and storage",
                "care",
                "Drills last longer when they are cleaned and stored dry.",
                4,
                "Proper drill care focuses on safety, regular cleaning, correct lubrication, and "
                "dry storage.",
                "manufacturer",
            ),
        ),
        phrasing_reply(
            (
                "What will you drill into most?",
                "Masonry and concrete need a more powerful drill.",
                ("Wood", "Masonry or concrete", "Both"),
            ),
            (
                "How heavy a drill can you hold comfortably?",
                "A drill that is heavy with its battery tires the arm.",
                ("Light", "Heavier is fine"),
            ),
            ("Some drills need regular cleaning and dry storage.", None, ()),
        ),
        [
            "Source: toolstation.com (the seller states)",
            "Source: consumerreports.org",
            "Source: titantec.com (the manufacturer states)",
        ],
    ),
}


def recorded_run(
    capsys: pytest.CaptureFixture[str], cache: Path, text: str, *replies: str
) -> list[str]:
    """A run with the real brief on the recorded searches, every question answered "n"."""
    chat, _ = fake_chat((*replies, NOTHING_STATED))
    sources = recorded_sources(cache)
    assert asyncio.run(run(text, chat, sources, typing("n", "n", "n", "n"), agents=REAL_BRIEF)) == 0
    return capsys.readouterr().out.splitlines()


@pytest.mark.parametrize("category", list(CATEGORIES))
def test_each_category_shows_sourced_questions_with_their_source_lines(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, category: str
) -> None:
    text, parsed, read, phrased, sources = CATEGORIES[category]

    lines = recorded_run(capsys, tmp_path, text, parsed, read, phrased)

    assert lines[1].startswith(f"Looking for: {category} · ")
    assert lines[2] == RESEARCHING
    assert [line for line in lines if line.startswith("Source: ")] == sources
    usage = lines.index("How often will you use it?")
    assert lines[usage + 6] == ""
    assert not any(line.startswith("We couldn't") for line in lines)


@pytest.mark.parametrize(
    ("link", "page_replies", "researched_questions"),
    [(PAN_LINK, (PAGE_DETAILS,), 2), (BLOCKED_LINK, (), 3)],
    ids=["a link that was read", "a link that could not be read"],
)
def test_a_pasted_link_asks_two_researched_questions_and_an_unreadable_one_the_full_interview(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    link: str,
    page_replies: tuple[str, ...],
    researched_questions: int,
) -> None:
    _, _, read, phrased, sources = CATEGORIES["frying pan"]
    parsed = extraction("frying pan", "tuned")

    lines = recorded_run(
        capsys, tmp_path, f"{link} a frying pan", parsed, *page_replies, read, phrased
    )

    # Pan size and pan material are requirements; seasoning is care and is asked only without
    # the product.
    assert [line for line in lines if line.startswith("Source: ")] == sources[:researched_questions]
    assert "How often will you use it?" in lines


def test_a_second_run_of_a_category_is_answered_from_the_brief_cache_and_its_trail_says_so(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    text, parsed, read, phrased, sources = CATEGORIES["kettle"]
    recorded_run(capsys, tmp_path, text, parsed, read, phrased)

    # Only the supervisor's reply and the stated call's: a read or a phrasing call would find no
    # reply to give.
    lines = recorded_run(capsys, tmp_path, text, parsed)

    assert [line for line in lines if line.startswith("Source: ")] == sources
    assert any(
        line.startswith("brief found: Category research for kettle from the cache, researched on ")
        for line in lines
    )


# --- The arguments ---


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["a frying pan"], ("a frying pan", False)),
        (["--skip-all", "a frying pan"], ("a frying pan", True)),
        (["a frying pan", "--skip-all"], ("a frying pan", True)),
        ([], None),
        (["--skip-all"], None),
        (["a frying pan", "a kettle"], None),
    ],
)
def test_the_arguments_are_one_text_and_an_optional_skip_all(
    arguments: list[str], expected: tuple[str, bool] | None
) -> None:
    assert parse_arguments(arguments) == expected


def test_arguments_that_cannot_be_used_print_the_usage_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--skip-all"]) == 2
    assert capsys.readouterr().out.splitlines() == [
        'Usage: uv run python -m shopper.terminal.cli [--skip-all] "<what you are looking for>"'
    ]


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (
            extraction("groceries", "not_a_product"),
            "This app covers durable products such as cookware, appliances and tools. "
            """It can't help with "groceries".""",
        ),
        (
            extraction(None, "several_products"),
            "That looks like more than one product. "
            "Name one to start, for example 'a frying pan, budget €50'.",
        ),
        (
            extraction(None, "unclear"),
            "We couldn't tell what you're looking for. "
            "Try naming one product, for example 'a frying pan, budget €50'.",
        ),
    ],
)
def test_a_request_that_does_not_run_prints_the_supervisors_line_and_its_message(
    capsys: pytest.CaptureFixture[str], reply: str, message: str
) -> None:
    assert output_of(capsys, "something", reply) == [READING, message]


def test_a_failed_model_call_ends_with_its_own_line_and_a_non_zero_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    chat, _ = fake_chat([ChatTimeoutError("no answer within 60 s")])

    status = asyncio.run(run("a frying pan", chat, SOURCES, agents=STUB_AGENTS))

    assert status != 0
    assert capsys.readouterr().out.splitlines() == [
        READING,
        "The app couldn't read your request just now, so nothing was run. Try again in a moment.",
    ]


def test_over_long_input_ends_with_its_own_line_and_a_non_zero_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    chat, requests = fake_chat([])

    status = asyncio.run(run("a frying pan " * 200, chat, SOURCES, agents=STUB_AGENTS))

    assert status != 0
    assert requests == []
    assert capsys.readouterr().out.splitlines() == [
        READING,
        "That is more text than the app can read. Try naming one product in a sentence or two.",
    ]


# --- The options, with the default agents on the recorded listing pages ---

GREENCHEF = "GreenChef Diamond Inductie Koekenpan - Ø24 cm - Zwart - PFAS-vrij"
DE_BUYER = "de Buyer Mineral B Element Koekenpan - Ø 26 cm"
WMF = "WMF - Profi Resist - Koekenpan - Roestvrij Staal"
MIDEA = (
    "Midea - Roestvrijstalen waterkoker - Wit - 1,5 liter - 2200 W - Met temperatuurinstelling "
    "en veiligheidsfuncties"
)
INVENTUM = "Inventum HW817D Waterkoker - 1.7L - RVS/Zwart - 2200W - Met Warmhoudfunctie"
SEVERIN = "Severin WK 9342 Waterkoker - 1L - 2400W - Zwart/RVS"
EASYDRILL = "Bosch - EasyDrill 18V-38 - Accu-schroefboormachine - 18 V - 2.5 Ah Li-ion"
GSR = "Bosch Professional Accu-boormachine GSR 120-LI - 12 V - Inclusief batterij en lader"
POWER_X = "Power X-Change - Klopboor-/schroefmachine - Rood - Accu - 18V"


class OptionsCase(NamedTuple):
    """A tuned category's run on the recorded listing pages: what the user types, with the
    budget the runs of task 1.10 asked for, the supervisor's reply, the judgement by page of
    each candidate read (numbered in the order read), the page reads that differ from selling
    the item, and the price line of each option shown."""

    text: str
    parsed: str
    by_page: str
    page_reads: dict[str, str]
    expected: list[tuple[str, str]]


OPTIONS = {
    "frying pan": OptionsCase(
        FRYING_PAN,
        FRYING_PAN_REPLY,
        # Read: GreenChef, Tefal Renew ON, WMF, de Buyer, Tefal Jamie Oliver keramisch.
        judged(
            (1, "short", "ceramic coating that wears"),
            (2, "short", "ceramic coating that wears"),
            (3, "medium", "stainless body with a coating"),
            (4, "long", "carbon steel, no coating to wear out"),
            (5, "short", "ceramic coating that wears"),
        ),
        {},
        [
            (GREENCHEF, "Price: €23.99, plus €2.99 shipping, price seen at bol. via kieskeurig.nl"),
            (DE_BUYER, "Price: €51.95, free shipping, price seen at bol. Plaza via kieskeurig.nl"),
            (
                WMF,
                "Price: €44.99, free shipping, price seen at Joybuy.nl via beslist.nl",
            ),
        ],
    ),
    "kettle": OptionsCase(
        "a kettle that boils quickly, around 60 euros",
        extraction("kettle", "tuned", "around 60 euros", 60),
        NOT_JUDGED_BY_PAGE,
        {},
        [
            (MIDEA, "Price: €27.99, free shipping, price seen at Amazon.nl via beslist.nl"),
            (INVENTUM, "Price: €28.95, free shipping, price seen at Wehkamp via kieskeurig.nl"),
            (SEVERIN, "Price: €29.95, free shipping, price seen at EP.nl via kieskeurig.nl"),
        ],
    ),
    "drill": OptionsCase(
        "a cordless drill for occasional DIY at home, max 120 euro",
        # The live supervisor says "cordless drill" since task 1.10; the brief searches were
        # recorded for "drill" in task 1.15, so the reply written here keeps that category.
        extraction("drill", "tuned", "max 120 euro", 120),
        # Read, from the listing pages of the search with the local term, which stands in 21 of
        # their names since task 1.10 reads compounds ("Accu Klopboormachine"). The two Makitas
        # whose names say "Solo" and "(Body)" are incomplete, so the complete drills fill the
        # slots.
        judged(
            (2, "medium", "brushed motor, replaceable battery"),
            (3, "medium", "brushed motor, replaceable battery"),
            (5, "short", "sealed battery in a light build"),
        ),
        {},
        [
            (EASYDRILL, "Price: €49.99, free shipping, price seen at Joybuy.nl via beslist.nl"),
            (GSR, "Price: €97.10, free shipping, price seen at Galaxus.nl via beslist.nl"),
            (POWER_X, "Price: €60.28, free shipping, price seen at Galaxus.nl via beslist.nl"),
        ],
    ),
}


def options_run(
    capsys: pytest.CaptureFixture[str],
    cache: Path,
    category: str,
    *,
    typed: tuple[str, ...] = ("n", "n", "n", "n"),
    findings_reads: dict[str, str] | None = None,
    search: SearchService | None = None,
) -> list[str]:
    """A run with the default agents on the recorded searches and pages, or on `search` when
    given. The CO2e is the stub's: these runs are about the options."""
    case = OPTIONS[category]
    _, _, read, phrased, _ = CATEGORIES[category]
    chat, _ = fake_chat_with_reads(
        (case.parsed, read, phrased, NOTHING_STATED),
        by_page=case.by_page,
        page_reads=case.page_reads,
        findings_reads=findings_reads,
    )
    sources = recorded_sources(cache)
    if search is not None:
        sources = replace(sources, search=search)
    agents = replace(DEFAULT_AGENTS, lca=STUB_AGENTS.lca)
    assert asyncio.run(run(case.text, chat, sources, typing(*typed), agents=agents)) == 0
    return capsys.readouterr().out.splitlines()


@pytest.mark.parametrize("category", list(OPTIONS))
def test_each_category_prints_its_options_priced_from_a_product_pages_offer(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, category: str
) -> None:
    expected = OPTIONS[category].expected

    lines = options_run(capsys, tmp_path, category)

    for name, price in expected:
        block = lines.index(name)
        # Every page of the fixtures was read on the day they were recorded.
        assert lines[block + 1] == f"{price} on {SEEN_ON}"
        assert lines[block + 2].startswith("Link: https://www.")
    assert len([line for line in lines if line.startswith("Link: ")]) == len(expected)


def test_a_candidate_left_out_and_a_slot_filled_by_price_are_in_the_printed_trail(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines = options_run(capsys, tmp_path, "kettle")

    assert (
        "tco decided: Filled the slots by price; reason: the durability judgement did not tell "
        "the candidates apart"
    ) in lines
    assert any(
        line.startswith('tco excluded: Left out "Philips Daily Collection HD9350/90')
        for line in lines
    )


def test_the_drills_term_stands_in_the_compound_names_its_listing_pages_list(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    # "accuboormachine" stood in 2 of the names as written ("Accu Klopboormachine" in the
    # rest), so task 1.15 searched again with "drill" and checked no name.
    lines = options_run(capsys, tmp_path, "drill")

    assert not any("Searched the listing pages with the category" in line for line in lines)


def test_no_options_found_prints_the_wording_for_what_happened(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    recorded = fixture_search_service(FIXTURES)

    async def search(request: SearchRequest) -> StoredResponse | FailureKind:
        if request.purpose is SearchPurpose.LISTING_PAGES:
            return FailureKind.UNAVAILABLE
        return await recorded(request)

    lines = options_run(capsys, tmp_path, "kettle", search=search)

    assert (
        "The search for kettle options didn't work just now, so there are no options to compare. "
        "Try again in a moment."
    ) in lines
    assert not any(line.startswith("Link: ") for line in lines)


# --- Findings, on the recorded findings searches ---


def test_an_option_whose_findings_found_nothing_shows_that_nothing_was_found(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    lines = options_run(capsys, tmp_path, "kettle")

    # With no evidence item either, one line says both were looked for and nothing was found.
    block = lines.index(SEVERIN)
    assert lines[block + 4] == "  No durability evidence found"


def test_a_findings_search_that_fails_says_the_reports_were_not_looked_up(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    recorded = fixture_search_service(FIXTURES)

    async def search(request: SearchRequest) -> StoredResponse | FailureKind:
        if request.purpose is SearchPurpose.FINDINGS:
            return FailureKind.UNAVAILABLE
        return await recorded(request)

    lines = options_run(capsys, tmp_path, "kettle", search=search)

    block = lines.index(SEVERIN)
    assert "  Owner and tester reports not looked up" in lines[block:]
    assert not any(line.startswith(("  Test: ", "  Owner report: ")) for line in lines)


# --- CO2e: the real LCA agent on the stub pans ---

# The large model's estimate of the two stub pans, recorded in the live run of task 1.9.8
# (scripts/lca_live_run.py, docs/findings/task_1.9.8.md).
STUB_PANS_ESTIMATE = json.loads(
    (FIXTURES / "nebius" / "lca-stub-pans.json").read_text(encoding="utf-8")
)
REAL_LCA = replace(STUB_AGENTS, lca=estimate_co2e)


def co2e_run(capsys: pytest.CaptureFixture[str], lca_reply: str) -> list[str]:
    """A run with --skip-all on the stub pans, estimated by the real LCA agent."""
    chat, _ = fake_chat([FRYING_PAN_REPLY, lca_reply])
    assert (
        asyncio.run(run(FRYING_PAN, chat, SOURCES, never_asked, skip_all=True, agents=REAL_LCA))
        == 0
    )
    return capsys.readouterr().out.splitlines()


def co2e_lines(lines: list[str], option: str) -> list[str]:
    block = lines[lines.index(option) :]
    return [line for line in block[: block.index("") if "" in block else None] if "CO2e" in line]


def test_each_option_shows_its_co2e_range_with_the_ai_synthetic_estimate_label(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = co2e_run(capsys, STUB_PANS_ESTIMATE["reply"])

    assert (
        "Lifespan sourced for 0 of 2 options. CO2e to make: AI synthetic estimate for 2." in lines
    )
    for option in ("Non-stick pan", "Carbon steel pan"):
        (co2e, *_) = co2e_lines(lines, option)
        assert co2e.startswith("CO2e: ")
        assert co2e.endswith(" kg CO2e to make, over 10 years (AI synthetic estimate)")
    assert sum(line.startswith("  Built from (estimated): ") for line in lines) == 2


def test_an_option_the_model_cannot_estimate_shows_no_result_and_the_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply = json.loads(STUB_PANS_ESTIMATE["reply"])
    reply["options"][1] = {
        "name": "Carbon steel pan",
        "inputs": [],
        "manufacturing_low": None,
        "manufacturing_high": None,
        "declined_because": "I know nothing of what it is made of",
    }

    lines = co2e_run(capsys, json.dumps(reply))

    assert (
        "We couldn't estimate the CO2e of making Carbon steel pan, so no CO2e figure is shown for "
        "it."
    ) in lines
    assert co2e_lines(lines, "Carbon steel pan") == [
        "CO2e: not available (no CO2e estimate for this option)"
    ]
    assert co2e_lines(lines, "Non-stick pan")[0].endswith("(AI synthetic estimate)")
