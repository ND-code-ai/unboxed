"""Fixed-rate conversion of a recurring cost into euro: the one exception to euro only
(docs/adr/0002-fixed-rate-conversion-recurring-costs.md).

The rates are passed in; the table lives in config.py. A price, a budget or a listing is never
converted.
"""

from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

CENT = Decimal("0.01")


class FixedRate(NamedTuple):
    """Units of the currency per euro, on the day of its source's reference rate."""

    per_euro: Decimal
    on: date
    source: str


def to_euros(amount: Decimal, currency: str, rates: Mapping[str, FixedRate]) -> Decimal | None:
    """The amount in euro, rounded to the cent; missing for a currency with no rate."""
    rate = rates.get(currency)
    if rate is None:
        return None
    return (amount / rate.per_euro).quantize(CENT, rounding=ROUND_HALF_UP)
