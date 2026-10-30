"""The figures of docs/architecture/calculations.md, on plain values.

Callers pass known, positive prices and lifespans; `comparison.py` decides what is missing.
Nothing here rounds.
"""

from decimal import Decimal
from math import ceil

NO_RECURRING_COST = Decimal(0)


def cost_per_year(
    price: Decimal,
    lifespan_years: Decimal,
    recurring_cost_per_year: Decimal = NO_RECURRING_COST,
) -> Decimal:
    return price / lifespan_years + recurring_cost_per_year


def cost_per_use(cost_per_year: Decimal, uses_per_year: int) -> Decimal:
    return cost_per_year / uses_per_year


def purchases_over_horizon(horizon_years: int, lifespan_years: Decimal) -> int:
    return max(1, ceil(Decimal(horizon_years) / lifespan_years))


def horizon_cost(
    price: Decimal,
    purchases: int,
    horizon_years: int,
    recurring_cost_per_year: Decimal = NO_RECURRING_COST,
) -> Decimal:
    return purchases * price + recurring_cost_per_year * horizon_years


def horizon_co2e(co2e_low: Decimal, co2e_high: Decimal, purchases: int) -> tuple[Decimal, Decimal]:
    """The low and high end over the horizon, never collapsed to a midpoint."""
    return purchases * co2e_low, purchases * co2e_high
