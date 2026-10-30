"""The typical yearly cost of the first recurring-cost factor, read by code from what the read
quotes, and a recurring-cost factor that is not asked about (category_brief.md, "Decision factors":
"Recurring costs are factors")."""

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from brief_replies import Ran, asked, asked_about, factor, phrasing, reading, run, trail, warnings

from fakes import finding
from shopper.agents.bundle import BriefOutput
from shopper.state import FactorKind, Request, Scope, TrailKind, WarningCode
from shopper.tools.fixtures import fixture_search_service

FIXTURES = Path(__file__).parents[2] / "fixtures"


# --- The typical yearly cost of a recurring-cost factor ---

VACUUM = Request(original_text="a vacuum cleaner", category="vacuum cleaner", scope=Scope.GENERAL)
VACUUM_GUIDE_QUERY = "vacuum cleaner buying guide what to look for"
VACUUM_CARE_QUERY = "vacuum cleaner care maintenance and replacement parts"
VACUUM_GUIDE_URL = "https://www.consumentenbond.nl/stofzuiger/kiezen"
FILTER_URL = "https://www.vacuumparts.example.com/hepa-filters"
VACUUM_GUIDE = {
    "url": VACUUM_GUIDE_URL,
    "title": "Choosing a vacuum cleaner",
    "content": (
        "A bagged vacuum cleaner needs new bags. Bags cost €12 for a pack of 5, and the bag is "
        "replaced every month. A cordless vacuum cleaner needs a place to charge."
    ),
}
FILTERS = {
    "url": FILTER_URL,
    "title": "HEPA filters",
    "content": (
        "The HEPA filter traps fine dust. A replacement HEPA filter costs $30 and should be "
        "replaced every 6 months. Replacement filters cost €20 at most shops. Spare filters are "
        "sold for €18 per pack."
    ),
}
VACUUM_FOUND = {VACUUM_GUIDE_QUERY: (VACUUM_GUIDE,), VACUUM_CARE_QUERY: (FILTERS,)}
CHARGING = factor(
    "Charging spot",
    "requirement",
    "A cordless vacuum cleaner needs a socket where it is kept.",
    1,
    "A cordless vacuum cleaner needs a place to charge.",
)
DUST_BAGS = factor(
    "Dust bags",
    "recurring_cost",
    "A bagged vacuum cleaner keeps needing new bags.",
    1,
    "A bagged vacuum cleaner needs new bags.",
    amount="Bags cost €12 for a pack of 5",
    interval="the bag is replaced every month",
    pack="a pack of 5",
)
HEPA_FILTER = factor(
    "Filter replacement",
    "recurring_cost",
    "The filter has to be replaced to keep trapping fine dust.",
    2,
    "The HEPA filter traps fine dust.",
    amount="A replacement HEPA filter costs $30",
    interval="replaced every 6 months",
)


def vacuum(cache: Path, *factors: Mapping[str, object], **kwargs: object) -> Ran:
    """A run on the vacuum cleaner's searches with this read and an empty phrasing reply."""
    return run(
        cache,
        reading(*factors),
        phrasing(),
        request=VACUUM,
        service=finding(VACUUM_FOUND),
        **kwargs,  # type: ignore[arg-type]
    )


def yearly_costs(output: BriefOutput) -> list[tuple[str, Decimal | None, str | None, str | None]]:
    """Each recurring-cost factor's name, typical yearly cost, its source and the currency it
    was converted from."""
    return [
        (
            factor.name,
            factor.typical_yearly_cost,
            None
            if factor.typical_yearly_cost_source is None
            else factor.typical_yearly_cost_source.reference,
            factor.typical_yearly_cost_converted_from,
        )
        for factor in output.factors
        if factor.kind is FactorKind.RECURRING_COST
    ]


def test_the_first_recurring_cost_factor_gets_a_typical_yearly_cost_read_by_code(
    tmp_path: Path,
) -> None:
    ran = vacuum(tmp_path, CHARGING, DUST_BAGS, HEPA_FILTER)

    # €12 for 5 bags, one a month: 12 bags a year at €2.40.
    assert yearly_costs(ran.output) == [
        ("Dust bags", Decimal("28.8"), VACUUM_GUIDE_URL, None),
        ("Filter replacement", None, None, None),
    ]


def test_a_typical_yearly_cost_in_dollars_is_converted_at_the_fixed_rate(tmp_path: Path) -> None:
    ran = vacuum(tmp_path, HEPA_FILTER)

    # $30 at 1.1253 per euro is €26.66, twice a year.
    assert yearly_costs(ran.output) == [
        ("Filter replacement", Decimal("53.32"), FILTER_URL, "USD"),
    ]
    (found,) = trail(ran.output, "Typical yearly cost")
    assert found[0] is TrailKind.FOUND
    assert "30 USD converted at 1.1253 per euro" in (found[2] or "")


@pytest.mark.parametrize(
    ("amount", "interval", "reason"),
    [
        ("Replacement filters cost €20", None, "no interval is quoted from the search result"),
        (
            "Replacement filters cost €20",
            "at most shops",
            'the interval "at most shops" cannot be read as a time',
        ),
        (
            "A replacement HEPA filter costs €30",
            "replaced every 6 months",
            "its amount is not quoted from the search result",
        ),
        (
            "Spare filters are sold for €18 per pack",
            "replaced every 6 months",
            "the price is for a pack with no quoted count",
        ),
    ],
)
def test_an_amount_that_fails_a_check_leaves_the_factor_with_no_amount_and_says_why(
    tmp_path: Path, amount: str, interval: str | None, reason: str
) -> None:
    filters = factor(
        "Filter replacement",
        "recurring_cost",
        "The filter has to be replaced to keep trapping fine dust.",
        2,
        "The HEPA filter traps fine dust.",
        amount=amount,
        interval=interval,
    )
    ran = vacuum(tmp_path, filters)

    assert yearly_costs(ran.output) == [("Filter replacement", None, None, None)]
    assert trail(ran.output, "No typical yearly cost") == [
        (TrailKind.EXCLUDED, 'No typical yearly cost for "Filter replacement"', reason)
    ]


# --- A recurring cost is not asked about ---

CHARGING_QUESTION = asked(
    1, "Where will you keep it?", "It needs a socket nearby.", "Near a socket", "In a cupboard"
)


def test_a_recurring_cost_factor_with_an_amount_gets_no_question_and_no_phrasing(
    tmp_path: Path,
) -> None:
    ran = run(
        tmp_path,
        reading(CHARGING, DUST_BAGS),
        phrasing(CHARGING_QUESTION),
        request=VACUUM,
        service=finding(VACUUM_FOUND),
    )

    assert asked_about(ran.output) == ["researched-1", "usage-1"]
    _, phrase = ran.requests
    assert "Dust bags" not in phrase.messages[-1]["content"]


def test_a_recurring_cost_factor_takes_none_of_the_four_places(tmp_path: Path) -> None:
    four = [{**CHARGING, "name": f"Factor {letter}"} for letter in "ABCD"]
    questions = [{**CHARGING_QUESTION, "factor": number} for number in range(1, 5)]
    ran = run(
        tmp_path,
        reading(four[0], DUST_BAGS, *four[1:]),
        phrasing(*questions),
        request=VACUUM,
        service=finding(VACUUM_FOUND),
    )

    assert asked_about(ran.output) == [
        "researched-1",
        "researched-3",
        "researched-4",
        "researched-5",
        "usage-1",
    ]


# --- On the recorded searches of a category with a consumable ---

TOOTHBRUSH = Request(
    original_text="an electric toothbrush", category="electric toothbrush", scope=Scope.GENERAL
)
TOOTHBRUSH_FOLLOW_UP = (
    "electric toothbrush brush head replacement cost and battery replacement price"
)
# The two template searches give 16 results; the follow-up's second is result 18.
BRUSH_HEADS = factor(
    "Brush head replacement",
    "recurring_cost",
    "Replacement heads are bought again to keep cleaning well.",
    18,
    "requires a $15 replacement head every 3 months",
    stated_by="seller",
    amount="requires a $15 replacement head",
    interval="every 3 months",
)
COST_GAP = {"what": "Brush head price and interval", "reason": "No result gives both."}


def test_a_dollar_cost_in_a_recorded_search_result_is_read_and_converted(
    tmp_path: Path,
) -> None:
    ran = run(
        tmp_path,
        reading(gaps=[COST_GAP], follow_up_query=TOOTHBRUSH_FOLLOW_UP),
        reading(BRUSH_HEADS),
        phrasing(),
        request=TOOTHBRUSH,
        service=fixture_search_service(FIXTURES),
    )

    # $15 at 1.1253 per euro is €13.33, four times a year.
    assert yearly_costs(ran.output) == [
        (
            "Brush head replacement",
            Decimal("53.32"),
            "https://usmile.us/blogs/oral-care/blogs-guides-best-cheap-electric-toothbrush",
            "USD",
        )
    ]


def test_with_the_phrasing_call_failing_the_recurring_cost_keeps_its_amount(
    tmp_path: Path,
) -> None:
    ran = run(
        tmp_path,
        reading(DUST_BAGS),
        "not json",
        "still not json",
        request=VACUUM,
        service=finding(VACUUM_FOUND),
    )

    assert yearly_costs(ran.output) == [("Dust bags", Decimal("28.8"), VACUUM_GUIDE_URL, None)]
    assert [code for code, _ in warnings(ran.output)] == [WarningCode.QUESTIONS_UNAVAILABLE]
