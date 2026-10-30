"""How a number is written where it is shown: the rule of docs/architecture/calculations.md
("Display rounding"), decided here once for the terminal app and the page alike.

A single value rounds half up; the ends of a range round outward, so the range shown holds the
range computed. A whole value drops its ".00" or ".0".
"""

import math
from datetime import timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from shopper import wording

CENT = Decimal("0.01")
TENTH = Decimal("0.1")
# Masses and CO2e in kg are shown to two significant figures.
KG_SIGNIFICANT_FIGURES = 2
GRAMS_PER_KG = 1000
# Kilometres for scale are not shown at all under this at the high end.
MIN_KM_FOR_SCALE = 10


def euros(amount: Decimal) -> str:
    """An amount in euro to the cent, without the cents of a whole one ("€5", "€12.50"); a
    positive amount that would show as €0 is "under €0.01"."""
    if 0 < amount < CENT / 2:
        return wording.UNDER_A_CENT
    return f"€{_rounded(amount, CENT, ROUND_HALF_UP)}"


def years(value: Decimal, rounding: str = ROUND_HALF_UP) -> str:
    """Years to one decimal, without the decimal of whole years ("3", "1.7"); the end of a
    range passes the rounding that takes it outward."""
    return _rounded(value, TENTH, rounding)


def kilograms(value: Decimal, rounding: str = ROUND_HALF_UP) -> str:
    """A mass or a CO2e figure in kg to two significant figures, rounded the given way, without
    trailing zeros ("5", not "5.0"); the end of a range passes the rounding that takes it
    outward."""
    if not value:
        return "0"
    exponent = value.adjusted() - (KG_SIGNIFICANT_FIGURES - 1)
    rounded = value.quantize(Decimal(1).scaleb(exponent), rounding=rounding)
    whole = rounded.to_integral_value()
    return f"{whole if rounded == whole else rounded.normalize():f}"


def car_kilometres(
    low_kg: Decimal, high_kg: Decimal, grams_per_km: Decimal
) -> tuple[str, str] | None:
    """A range of CO2e in kg as the kilometres a car emits it over, rounded outward, in tens and
    from 1,000 km to two significant figures, with a comma; missing when the high end comes to
    under 10 km, too small to picture."""
    low, high = (kg * GRAMS_PER_KG / grams_per_km for kg in (low_kg, high_kg))
    if high < MIN_KM_FOR_SCALE:
        return None
    return _kilometres(low, ROUND_FLOOR), _kilometres(high, ROUND_CEILING)


def _kilometres(value: Decimal, rounding: str) -> str:
    step = 10 ** max(1, value.adjusted() - 1)
    return f"{int((value / step).to_integral_value(rounding=rounding)) * step:,}"


def whole_minutes(wait: timedelta) -> int:
    """A wait in whole minutes, rounded up so it is never too short; at least one."""
    return max(1, math.ceil(wait / timedelta(minutes=1)))


def _rounded(value: Decimal, step: Decimal, rounding: str) -> str:
    shown = value.quantize(step, rounding=rounding)
    whole = shown.to_integral_value()
    return f"{whole:f}" if shown == whole else f"{shown:f}"
