"""The lifespan a quote states, read by code: the table in docs/architecture/option_research.md
("Sourced lifespan").

Only years and months count; hours, cycles and "a lifetime" give nothing. A range gives its low
end and keeps both ends, for a lifespan typical of the type. Whether "up to" may stand is the
caller's rule, since it depends on who is speaking.
"""

import re
from decimal import Decimal
from typing import NamedTuple

from shopper.calc.amounts import SPELLED_NUMBER, spelled_amount

MONTHS_PER_YEAR = Decimal(12)
_NUMBER = SPELLED_NUMBER
_YEARS = r"years?|yrs?|jaar|jaren"
_MONTHS = r"months?|maanden|maand"
_UNIT = rf"(?P<unit>{_YEARS}|{_MONTHS})"
_RANGE = re.compile(
    rf"\b(?P<low>{_NUMBER})-?\s*(?:to|and|or|-|–|—|tot|en|of)\s*(?P<high>{_NUMBER})[\s-]*{_UNIT}\b",
    re.IGNORECASE,
)
_SINGLE = re.compile(rf"\b(?P<number>{_NUMBER})\s*\+?\s*-?\s*{_UNIT}\b", re.IGNORECASE)
_UP_TO = re.compile(
    r"\b(?:up to|as long as|tot wel|tot|maximaal)(?:\s+(?:about|around|roughly|ongeveer))?\s*$",
    re.IGNORECASE,
)


class QuotedLifespan(NamedTuple):
    """The years a quote states; `low` and `high` only for a range, `up_to` for an upper bound."""

    years: Decimal
    low: Decimal | None = None
    high: Decimal | None = None
    up_to: bool = False


def quoted_lifespan(quote: str) -> QuotedLifespan | None:
    """The lifespan a quote states in years or months, or missing when it states none."""
    found = _RANGE.search(quote)
    if found is not None:
        low = _years(found.group("low"), found.group("unit"))
        high = _years(found.group("high"), found.group("unit"))
        if low is not None and high is not None and low <= high:
            return QuotedLifespan(years=low, low=low, high=high)
    found = _SINGLE.search(quote)
    if found is None:
        return None
    years = _years(found.group("number"), found.group("unit"))
    if years is None:
        return None
    up_to = _UP_TO.search(quote[: found.start()]) is not None
    return QuotedLifespan(years=years, up_to=up_to)


def _years(number: str, unit: str) -> Decimal | None:
    amount = spelled_amount(number)
    if amount is None or amount <= 0:
        return None
    is_months = re.fullmatch(_MONTHS, unit, re.IGNORECASE) is not None
    return amount / MONTHS_PER_YEAR if is_months else amount
