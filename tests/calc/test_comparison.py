from decimal import Decimal

import pytest

from samples import model_estimate_parts, seen_price
from shopper.calc.comparison import (
    CO2E_NOT_BELOW_BASELINE,
    CO2E_RANGES_OVERLAP,
    IS_THE_BASELINE,
    SOLD_INCOMPLETE,
    compare,
)
from shopper.state import (
    Assumptions,
    ComparisonRow,
    Figure,
    LcaResult,
    LcaTier,
    ProductOption,
    RecurringCostState,
    Source,
    SourceKind,
)

CENT = Decimal("0.01")
WEB = Source(kind=SourceKind.URL, reference="https://example.com/test")
ESTIMATE = Source(kind=SourceKind.MODEL_ESTIMATE, reference="tier 3")


def option(
    option_id: str,
    price: str | None,
    lifespan: str | None,
    recurring: str | None = None,
    state: RecurringCostState | None = None,
) -> ProductOption:
    return ProductOption(
        id=option_id,
        name=option_id,
        **seen_price(price),
        lifespan_years=None if lifespan is None else Decimal(lifespan),
        lifespan_source=None if lifespan is None else WEB,
        recurring_cost_per_year=None if recurring is None else Decimal(recurring),
        recurring_cost_source=None if recurring is None else WEB,
        recurring_cost_state=state
        or (RecurringCostState.NOT_LOOKED_FOR if recurring is None else RecurringCostState.FOUND),
    )


def footprint(option_id: str, low: str, high: str) -> LcaResult:
    return LcaResult(
        option_id=option_id,
        co2e_low=Decimal(low),
        co2e_high=Decimal(high),
        source=ESTIMATE,
        **model_estimate_parts(),
    )


def sourced_footprint(option_id: str, low: str, high: str, tier: LcaTier) -> LcaResult:
    """A published figure (tier 1) or a benchmark (tier 2)."""
    return LcaResult(
        option_id=option_id,
        co2e_low=Decimal(low),
        co2e_high=Decimal(high),
        tier=tier,
        source=WEB,
        boundary="cradle to gate",
    )


NON_STICK = option("non-stick", "20", "2")
CARBON_STEEL = option("carbon-steel", "40", "30")
BAGGED = option("bagged", "80", "4", recurring="25")
BAGLESS = option("bagless", "200", "10", recurring="10")
TEN_YEARS = Assumptions()
TEN_YEARS_50_USES = Assumptions(uses_per_year=50)


def row(rows: tuple[ComparisonRow, ...], option_id: str) -> ComparisonRow:
    return next(r for r in rows if r.option_id == option_id)


def against_non_stick(footprints: tuple[LcaResult, ...]) -> ComparisonRow:
    """The carbon steel pan's row, with the non-stick pan as the baseline."""
    return row(compare((NON_STICK, CARBON_STEEL), footprints, TEN_YEARS).rows, "carbon-steel")


def test_frying_pan_example() -> None:
    comparison = compare((NON_STICK, CARBON_STEEL), (), TEN_YEARS)

    non_stick = row(comparison.rows, "non-stick")
    carbon_steel = row(comparison.rows, "carbon-steel")
    assert comparison.baseline_option_id == "non-stick"
    assert non_stick.cost_per_year == Decimal("10.00")
    assert non_stick.purchases == 5
    assert non_stick.horizon_cost == Decimal("100")
    assert carbon_steel.cost_per_year is not None
    assert carbon_steel.cost_per_year.quantize(CENT) == Decimal("1.33")
    assert carbon_steel.purchases == 1
    assert carbon_steel.horizon_cost == Decimal("40")
    assert carbon_steel.savings == Decimal("60")
    assert non_stick.savings == Decimal("0")


def test_vacuum_cleaner_example() -> None:
    comparison = compare((BAGGED, BAGLESS), (), TEN_YEARS_50_USES)

    bagged = row(comparison.rows, "bagged")
    bagless = row(comparison.rows, "bagless")
    assert comparison.baseline_option_id == "bagged"
    assert bagged.cost_per_year == Decimal("45.00")
    assert bagged.cost_per_use == Decimal("0.90")
    assert bagged.purchases == 3
    assert bagged.horizon_cost == Decimal("490")
    assert bagless.cost_per_year == Decimal("30.00")
    assert bagless.cost_per_use == Decimal("0.60")
    assert bagless.purchases == 1
    assert bagless.horizon_cost == Decimal("300")
    assert bagless.savings == Decimal("190")
    assert not bagged.recurring_costs_not_found
    assert not bagless.recurring_costs_not_found


def test_unknown_lifespan_leaves_the_figures_missing_with_a_reason() -> None:
    comparison = compare((NON_STICK, option("mystery", "30", None)), (), TEN_YEARS_50_USES)

    mystery = row(comparison.rows, "mystery")
    for figure in (
        Figure.COST_PER_YEAR,
        Figure.COST_PER_USE,
        Figure.PURCHASES,
        Figure.HORIZON_COST,
        Figure.SAVINGS,
    ):
        assert getattr(mystery, figure.value) is None
        assert mystery.missing_reasons[figure]


def test_zero_lifespan_is_missing_not_a_division_by_zero() -> None:
    # The models reject a zero lifespan, so build one without validation to test the guard.
    broken_option = option("broken", "30", "5").model_copy(update={"lifespan_years": Decimal("0")})
    comparison = compare((broken_option,), (), TEN_YEARS)

    broken = comparison.rows[0]
    assert broken.cost_per_year is None
    assert broken.purchases is None
    assert broken.horizon_cost is None
    assert broken.missing_reasons[Figure.COST_PER_YEAR]


def test_unknown_price_leaves_costs_missing_but_keeps_purchases() -> None:
    comparison = compare((option("unpriced", None, "5"),), (), TEN_YEARS)

    unpriced = comparison.rows[0]
    assert comparison.baseline_option_id is None
    assert unpriced.cost_per_year is None
    assert unpriced.horizon_cost is None
    assert unpriced.purchases == 2
    assert unpriced.missing_reasons[Figure.HORIZON_COST]
    assert unpriced.missing_reasons[Figure.SAVINGS]


def test_no_uses_per_year_leaves_cost_per_use_missing() -> None:
    comparison = compare((NON_STICK,), (), TEN_YEARS)

    non_stick = comparison.rows[0]
    assert non_stick.cost_per_use is None
    assert non_stick.missing_reasons[Figure.COST_PER_USE]
    assert Figure.COST_PER_YEAR not in non_stick.missing_reasons


def test_a_recurring_cost_looked_for_and_not_found_counts_as_zero_and_is_flagged() -> None:
    not_found = option("non-stick", "20", "2", state=RecurringCostState.NOT_FOUND)

    non_stick = compare((not_found,), (), TEN_YEARS).rows[0]

    assert non_stick.recurring_costs_not_found
    assert non_stick.horizon_cost == Decimal("100")


def test_a_recurring_cost_not_looked_for_counts_as_zero_with_no_flag() -> None:
    non_stick = compare((NON_STICK,), (), TEN_YEARS).rows[0]

    assert not non_stick.recurring_costs_not_found
    assert non_stick.horizon_cost == Decimal("100")


def test_a_converted_recurring_cost_carries_its_currency_to_the_row() -> None:
    converted = option("bagged", "80", "4", recurring="25").model_copy(
        update={"recurring_cost_converted_from": "USD"}
    )

    assert compare((converted,), (), TEN_YEARS).rows[0].recurring_cost_converted_from == "USD"


def test_within_budget_over_at_and_under() -> None:
    options = (option("under", "30", "5"), option("at", "50", "5"), option("over", "60", "5"))

    comparison = compare(options, (), TEN_YEARS, budget=Decimal("50"))

    assert row(comparison.rows, "under").within_budget is True
    assert row(comparison.rows, "at").within_budget is True
    assert row(comparison.rows, "over").within_budget is False


def test_within_budget_counts_the_stated_shipping() -> None:
    at = option("at", "47", "5").model_copy(update={"shipping": Decimal("3")})
    over = option("over", "48", "5").model_copy(update={"shipping": Decimal("3")})

    comparison = compare((at, over), (), TEN_YEARS, budget=Decimal("50"))

    assert row(comparison.rows, "at").within_budget is True
    assert row(comparison.rows, "over").within_budget is False


@pytest.mark.parametrize("mark", ["out_of_stock", "incomplete"])
def test_an_option_out_of_stock_or_sold_incomplete_is_never_the_baseline(mark: str) -> None:
    marked = option("marked", "10", "2").model_copy(update={mark: True})

    comparison = compare((marked, NON_STICK, CARBON_STEEL), (), TEN_YEARS)

    assert comparison.baseline_option_id == "non-stick"


def test_an_option_sold_incomplete_has_no_savings_and_no_co2e_avoided() -> None:
    bare = option("bare", "30", "10").model_copy(update={"incomplete": True})
    footprints = (footprint("non-stick", "40", "60"), footprint("bare", "4", "6"))

    bare_row = row(compare((NON_STICK, bare), footprints, TEN_YEARS).rows, "bare")

    assert bare_row.horizon_cost == Decimal("30")
    assert (bare_row.savings, bare_row.co2e_avoided_low) == (None, None)
    assert bare_row.missing_reasons[Figure.SAVINGS] == SOLD_INCOMPLETE
    assert bare_row.missing_reasons[Figure.CO2E_AVOIDED] == SOLD_INCOMPLETE


def test_within_budget_is_missing_without_a_budget_or_a_price() -> None:
    no_budget = compare((NON_STICK,), (), TEN_YEARS)
    no_price = compare((option("unpriced", None, "5"),), (), TEN_YEARS, budget=Decimal("50"))

    assert no_budget.rows[0].within_budget is None
    assert no_price.rows[0].within_budget is None


def test_co2e_over_the_horizon_multiplies_by_purchases() -> None:
    footprints = (footprint("non-stick", "4", "6"), footprint("carbon-steel", "8", "11"))

    comparison = compare((NON_STICK, CARBON_STEEL), footprints, TEN_YEARS)

    non_stick = row(comparison.rows, "non-stick")
    carbon_steel = row(comparison.rows, "carbon-steel")
    assert (non_stick.horizon_co2e_low, non_stick.horizon_co2e_high) == (20, 30)
    assert (carbon_steel.horizon_co2e_low, carbon_steel.horizon_co2e_high) == (8, 11)


def test_co2e_avoided_subtracts_the_ranges_as_intervals() -> None:
    footprints = (footprint("non-stick", "4", "6"), footprint("carbon-steel", "8", "11"))

    carbon_steel = against_non_stick(footprints)

    assert (carbon_steel.co2e_avoided_low, carbon_steel.co2e_avoided_high) == (9, 22)


def test_overlapping_co2e_ranges_give_no_co2e_avoided() -> None:
    footprints = (footprint("non-stick", "2", "4"), footprint("carbon-steel", "1", "15"))

    carbon_steel = against_non_stick(footprints)

    assert carbon_steel.co2e_avoided_low is None
    assert carbon_steel.co2e_avoided_high is None
    assert carbon_steel.missing_reasons[Figure.CO2E_AVOIDED] == CO2E_RANGES_OVERLAP


def test_a_co2e_range_wholly_above_the_baseline_gives_no_co2e_avoided() -> None:
    footprints = (footprint("non-stick", "1", "1.5"), footprint("carbon-steel", "8", "11"))

    carbon_steel = against_non_stick(footprints)

    assert carbon_steel.co2e_avoided_low is None
    assert carbon_steel.co2e_avoided_high is None
    assert carbon_steel.missing_reasons[Figure.CO2E_AVOIDED] == CO2E_NOT_BELOW_BASELINE


def test_the_baseline_has_no_co2e_avoided_against_itself() -> None:
    footprints = (footprint("non-stick", "4", "6"), footprint("carbon-steel", "8", "11"))

    comparison = compare((NON_STICK, CARBON_STEEL), footprints, TEN_YEARS)

    non_stick = row(comparison.rows, "non-stick")
    assert non_stick.co2e_avoided_low is None
    assert non_stick.missing_reasons[Figure.CO2E_AVOIDED] == IS_THE_BASELINE


@pytest.mark.parametrize(
    ("baseline_footprint", "option_footprint", "weaker_tier"),
    [
        (sourced_footprint("non-stick", "4", "6", 2), footprint("carbon-steel", "8", "11"), 3),
        (footprint("non-stick", "4", "6"), sourced_footprint("carbon-steel", "8", "11", 1), 3),
        (
            sourced_footprint("non-stick", "4", "6", 1),
            sourced_footprint("carbon-steel", "8", "11", 2),
            2,
        ),
        (
            sourced_footprint("non-stick", "4", "6", 1),
            sourced_footprint("carbon-steel", "8", "11", 1),
            1,
        ),
    ],
)
def test_co2e_avoided_carries_the_weaker_of_the_two_tiers(
    baseline_footprint: LcaResult, option_footprint: LcaResult, weaker_tier: LcaTier
) -> None:
    footprints = (baseline_footprint, option_footprint)

    carbon_steel = against_non_stick(footprints)

    assert carbon_steel.co2e_avoided_tier == weaker_tier


def test_a_missing_co2e_avoided_has_no_tier() -> None:
    footprints = (footprint("non-stick", "2", "4"), footprint("carbon-steel", "1", "15"))

    carbon_steel = against_non_stick(footprints)

    assert carbon_steel.co2e_avoided_tier is None


def test_an_option_without_an_lca_result_has_no_co2e_figures() -> None:
    comparison = compare((NON_STICK, CARBON_STEEL), (footprint("non-stick", "4", "6"),), TEN_YEARS)

    carbon_steel = row(comparison.rows, "carbon-steel")
    assert carbon_steel.horizon_co2e_low is None
    assert carbon_steel.co2e_avoided_high is None
    assert carbon_steel.missing_reasons[Figure.HORIZON_CO2E]
    assert carbon_steel.missing_reasons[Figure.CO2E_AVOIDED]
    assert carbon_steel.horizon_cost == Decimal("40")


def test_the_caller_can_name_another_baseline() -> None:
    comparison = compare(
        (NON_STICK, CARBON_STEEL), (), TEN_YEARS, baseline_option_id="carbon-steel"
    )

    assert comparison.baseline_option_id == "carbon-steel"
    assert row(comparison.rows, "non-stick").savings == Decimal("-60")


def test_a_user_set_lifespan_replaces_the_estimate_in_the_math_only() -> None:
    assumptions = Assumptions(lifespan_overrides={"non-stick": Decimal("5")})

    comparison = compare((NON_STICK, CARBON_STEEL), (), assumptions)

    non_stick = row(comparison.rows, "non-stick")
    assert non_stick.cost_per_year == Decimal("4")
    assert non_stick.purchases == 2
    assert non_stick.horizon_cost == Decimal("40")
    assert row(comparison.rows, "carbon-steel").savings == Decimal("0")
    assert NON_STICK.lifespan_years == Decimal("2")


def test_a_shorter_horizon_changes_purchases_and_horizon_cost() -> None:
    comparison = compare((NON_STICK, CARBON_STEEL), (), Assumptions(horizon_years=4))

    assert row(comparison.rows, "non-stick").purchases == 2
    assert row(comparison.rows, "carbon-steel").savings == Decimal("0")


def test_an_unknown_baseline_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="no-such-option"):
        compare((NON_STICK, CARBON_STEEL), (), TEN_YEARS, baseline_option_id="no-such-option")
