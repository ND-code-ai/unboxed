"""Builds the comparison: every option's figures over the horizon, set against a baseline.

Unknown stays unknown: a figure that cannot be computed is missing, with its reason, and no
default is substituted (docs/architecture/calculations.md, "Rules").
"""

from collections.abc import Sequence
from decimal import Decimal

from shopper.calc.budget import within_budget
from shopper.calc.figures import (
    NO_RECURRING_COST,
    cost_per_use,
    cost_per_year,
    horizon_co2e,
    horizon_cost,
    purchases_over_horizon,
)
from shopper.state import (
    Assumptions,
    Comparison,
    ComparisonRow,
    Figure,
    LcaResult,
    ProductOption,
    RecurringCostState,
)

USES_PER_YEAR_NOT_GIVEN = "uses per year not given"
NO_CO2E_ESTIMATE = "no CO2e estimate for this option"
NO_BASELINE = "no baseline option to compare against"
BASELINE_FIGURE_MISSING = "this figure is not known for the baseline"
CO2E_RANGES_OVERLAP = "the CO2e ranges of this option and the baseline overlap"
CO2E_NOT_BELOW_BASELINE = "the CO2e range of this option is not below the baseline's"
IS_THE_BASELINE = "this option is the baseline"
SOLD_INCOMPLETE = "this option is sold without a part it needs to work"


def compare(
    options: Sequence[ProductOption],
    lca_results: Sequence[LcaResult],
    assumptions: Assumptions,
    budget: Decimal | None = None,
    baseline_option_id: str | None = None,
) -> Comparison:
    """The baseline is the cheapest option by sticker price unless the caller names another; an
    option out of stock or sold incomplete is never the cheapest. An option sold incomplete is
    not set against the baseline: its price buys less than the item.

    Raises ValueError for a baseline id that is not one of the options: a programming error.
    """
    if baseline_option_id is not None and baseline_option_id not in {o.id for o in options}:
        raise ValueError(f"baseline option {baseline_option_id!r} is not among the options")
    footprints = {result.option_id: result for result in lca_results}
    own_rows = tuple(
        _own_figures(option, footprints.get(option.id), assumptions, budget) for option in options
    )
    baseline_id = baseline_option_id or _cheapest_option_id(options)
    baseline = next((row for row in own_rows if row.option_id == baseline_id), None)
    incomplete = {option.id for option in options if option.incomplete}
    return Comparison(
        baseline_option_id=baseline_id,
        rows=tuple(
            _not_against_baseline(row, SOLD_INCOMPLETE)
            if row.option_id in incomplete
            else _against_baseline(row, baseline)
            for row in own_rows
        ),
    )


def lifespan_in_use(option: ProductOption, assumptions: Assumptions) -> Decimal | None:
    """The user's override when there is one, otherwise the option's own lifespan."""
    return assumptions.lifespan_overrides.get(option.id, option.lifespan_years)


def _gap(value: Decimal | None, name: str) -> str | None:
    """Why a value cannot be used in the math, or None when it can."""
    if value is None:
        return f"{name} not known"
    if value <= 0:
        return f"{name} is zero or less"
    return None


def _cheapest_option_id(options: Sequence[ProductOption]) -> str | None:
    priced = [
        option
        for option in options
        if _gap(option.price, "price") is None and not (option.out_of_stock or option.incomplete)
    ]
    if not priced:
        return None
    return min(priced, key=lambda option: option.price).id


def _own_figures(
    option: ProductOption,
    footprint: LcaResult | None,
    assumptions: Assumptions,
    budget: Decimal | None,
) -> ComparisonRow:
    """The figures that need no baseline."""
    lifespan = lifespan_in_use(option, assumptions)
    lifespan_gap = _gap(lifespan, "lifespan")
    cost_gap = _gap(option.price, "price") or lifespan_gap
    recurring = (
        NO_RECURRING_COST
        if option.recurring_cost_per_year is None
        else option.recurring_cost_per_year
    )
    horizon = assumptions.horizon_years
    uses = assumptions.uses_per_year
    figures: dict[str, Decimal | int] = {}
    reasons: dict[Figure, str] = {}

    if lifespan_gap:
        reasons[Figure.PURCHASES] = lifespan_gap
    else:
        figures["purchases"] = purchases_over_horizon(horizon, lifespan)

    if cost_gap:
        reasons[Figure.COST_PER_YEAR] = cost_gap
        reasons[Figure.HORIZON_COST] = cost_gap
        reasons[Figure.COST_PER_USE] = cost_gap
    else:
        yearly = cost_per_year(option.price, lifespan, recurring)
        figures["cost_per_year"] = yearly
        figures["horizon_cost"] = horizon_cost(
            option.price, figures["purchases"], horizon, recurring
        )
        if uses is None:
            reasons[Figure.COST_PER_USE] = USES_PER_YEAR_NOT_GIVEN
        else:
            figures["cost_per_use"] = cost_per_use(yearly, uses)

    if footprint is None:
        reasons[Figure.HORIZON_CO2E] = NO_CO2E_ESTIMATE
    elif lifespan_gap:
        reasons[Figure.HORIZON_CO2E] = lifespan_gap
    else:
        figures["horizon_co2e_low"], figures["horizon_co2e_high"] = horizon_co2e(
            footprint.co2e_low, footprint.co2e_high, figures["purchases"]
        )
        figures["horizon_co2e_tier"] = footprint.tier

    return ComparisonRow(
        option_id=option.id,
        missing_reasons=reasons,
        recurring_costs_not_found=option.recurring_cost_state is RecurringCostState.NOT_FOUND,
        recurring_cost_converted_from=option.recurring_cost_converted_from,
        within_budget=within_budget(option.price, budget, option.shipping),
        **figures,
    )


def _against_baseline(row: ComparisonRow, baseline: ComparisonRow | None) -> ComparisonRow:
    """Adds savings and CO2e avoided: the baseline's figure minus this option's.

    CO2e avoided carries the weaker of the two tiers: a higher tier number is a weaker estimate.
    """
    figures: dict[str, Decimal | int] = {}
    reasons = dict(row.missing_reasons)

    cost_gap = _baseline_gap(row, baseline, Figure.HORIZON_COST)
    if cost_gap:
        reasons[Figure.SAVINGS] = cost_gap
    else:
        figures["savings"] = baseline.horizon_cost - row.horizon_cost

    co2e_gap = _baseline_gap(row, baseline, Figure.HORIZON_CO2E) or _ranges_gap(row, baseline)
    if co2e_gap:
        reasons[Figure.CO2E_AVOIDED] = co2e_gap
    else:
        figures["co2e_avoided_low"] = baseline.horizon_co2e_low - row.horizon_co2e_high
        figures["co2e_avoided_high"] = baseline.horizon_co2e_high - row.horizon_co2e_low
        figures["co2e_avoided_tier"] = max(baseline.horizon_co2e_tier, row.horizon_co2e_tier)

    return row.model_copy(update={**figures, "missing_reasons": reasons})


def _not_against_baseline(row: ComparisonRow, reason: str) -> ComparisonRow:
    """The row with no savings and no CO2e avoided, each missing for the reason."""
    reasons = {**row.missing_reasons, Figure.SAVINGS: reason, Figure.CO2E_AVOIDED: reason}
    return row.model_copy(update={"missing_reasons": reasons})


def _baseline_gap(row: ComparisonRow, baseline: ComparisonRow | None, figure: Figure) -> str | None:
    """Why this option cannot be set against the baseline on one figure, or None when it can."""
    if figure in row.missing_reasons:
        return row.missing_reasons[figure]
    if baseline is None:
        return NO_BASELINE
    if figure in baseline.missing_reasons:
        return BASELINE_FIGURE_MISSING
    return None


def _ranges_gap(row: ComparisonRow, baseline: ComparisonRow) -> str | None:
    """Why the interval difference gives no CO2e avoided: it exists only when its low end,
    the baseline's low end minus this option's high end, is above 0.

    Call it only once `_baseline_gap` found both horizon CO2e ranges.
    """
    if row.option_id == baseline.option_id:
        return IS_THE_BASELINE
    if baseline.horizon_co2e_high <= row.horizon_co2e_low:
        return CO2E_NOT_BELOW_BASELINE
    if baseline.horizon_co2e_low <= row.horizon_co2e_high:
        return CO2E_RANGES_OVERLAP
    return None
