"""What a consumable costs a year, read by code from the quoted amount, interval and pack count:
the one reading the brief's typical yearly cost and a product option's recurring cost share.

Rules: docs/architecture/option_research.md ("Recurring cost") and
docs/adr/0002-fixed-rate-conversion-recurring-costs.md.
"""

from decimal import Decimal
from typing import NamedTuple

from shopper.agents.shared.research import stands_in
from shopper.calc.conversion import to_euros
from shopper.calc.money import quoted_money
from shopper.calc.recurring import (
    is_a_pack,
    pack_count,
    recurring_cost_per_year,
    replacements_per_year,
)
from shopper.config import FIXED_RATES
from shopper.state import ConvertedCurrency
from shopper.tools.results import SearchResult


class YearlyCost(NamedTuple):
    """The yearly cost in euro and the currency it was converted from, with the notes that say
    how, for the trail."""

    per_year: Decimal
    converted_from: ConvertedCurrency | None
    notes: tuple[str, ...]


def yearly_cost(
    result: SearchResult,
    amount_quote: str,
    interval_quote: str | None,
    pack_count_quote: str | None,
) -> YearlyCost | str:
    """The yearly cost the quotes from this result state, or why there is none.

    Each quote has to stand in the result. The amount is in euro, or in USD or GBP converted at
    the fixed rate; a bare "$" is read as US dollars. With no interval in time, or a pack with no
    count, there is no yearly cost.
    """
    if not amount_quote.strip() or not stands_in(amount_quote, result):
        return "its amount is not quoted from the search result"
    money = quoted_money(amount_quote)
    if money is None:
        return "its amount quote holds no single amount with a currency"
    if money.currency == "other":
        return "its amount is in a currency that is not converted"
    interval = (interval_quote or "").strip()
    if not interval or not stands_in(interval, result):
        return "no interval is quoted from the search result"
    per_year = replacements_per_year(interval)
    if per_year is None:
        return f'the interval "{interval}" cannot be read as a time'
    pack = _pack(amount_quote, pack_count_quote, result)
    if isinstance(pack, str):
        return pack
    if money.currency == "EUR":
        return YearlyCost(recurring_cost_per_year(money.amount, per_year, pack), None, ())
    currency: ConvertedCurrency = "USD" if money.currency == "$" else money.currency
    rate = FIXED_RATES[currency]
    euro_amount = to_euros(money.amount, currency, FIXED_RATES)
    assert euro_amount is not None, "every converted currency has a fixed rate"
    converted = (
        f"{money.amount:f} {currency} converted at {rate.per_euro:f} per euro, "
        f"the {rate.source} of {rate.on.isoformat()}"
    )
    bare = ('a bare "$" is read as US dollars',) if money.currency == "$" else ()
    per_year_cost = recurring_cost_per_year(euro_amount, per_year, pack)
    return YearlyCost(per_year_cost, currency, (converted, *bare))


def _pack(amount_quote: str, quote: str | None, result: SearchResult) -> int | str:
    """The pieces the amount is for, or why the count cannot be read."""
    quote = (quote or "").strip()
    if not quote:
        return "the price is for a pack with no quoted count" if is_a_pack(amount_quote) else 1
    if not stands_in(quote, result):
        return "its pack count is not quoted from the search result"
    count = pack_count(quote)
    return "its pack count quote holds no readable count" if count is None else count
