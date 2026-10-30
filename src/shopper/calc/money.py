"""A cost quoted from a search result, read with its currency: euro, US dollar, pound sterling,
a bare "$", or another currency (docs/architecture/option_research.md, "Recurring cost").

Only a recurring cost is read this way; a price is an offer's, read from a product page's
JSON-LD in euro only (`tools/json_ld.py`).
"""

import re
from decimal import Decimal
from typing import Literal, NamedTuple

from shopper.calc.amounts import EURO_SYMBOL, EURO_WORDS, NUMBER, parse_amount
from shopper.calc.budget import OTHER_CURRENCY_CODES, OTHER_CURRENCY_SYMBOLS, OTHER_CURRENCY_WORDS

# "$" alone is read as US dollars by the caller, with a trail entry saying so.
QuotedCurrency = Literal["EUR", "USD", "GBP", "$", "other"]
_TOKEN = re.compile(rf"(?P<number>{NUMBER})|(?P<marker>US\$|[€£$¥₺]|[^\W\d_]+)")
_USD = frozenset({"US$", "usd", "dollar", "dollars"})
_GBP = frozenset({"£", "gbp"})
_NOT_OTHER = frozenset({"USD", "GBP"})


class QuotedMoney(NamedTuple):
    amount: Decimal
    currency: QuotedCurrency


def quoted_money(quote: str) -> QuotedMoney | None:
    """The one amount in the quote that stands next to a currency marker, with that currency;
    missing unless there is exactly one, and it can be read."""
    tokens = [(match.lastgroup, match.group()) for match in _TOKEN.finditer(quote)]
    marked = [
        (number, currency)
        for index, (kind, number) in enumerate(tokens)
        if kind == "number"
        for currency in (_currency_next_to(tokens, index),)
        if currency is not None
    ]
    if len(marked) != 1:
        return None
    number, currency = marked[0]
    amount = parse_amount(number)
    return None if amount is None else QuotedMoney(amount, currency)


def _currency_next_to(tokens: list[tuple[str | None, str]], index: int) -> QuotedCurrency | None:
    before = tokens[max(index - 1, 0) : index]
    after = tokens[index + 1 : index + 2]
    for kind, text in (*before, *after):
        if kind == "marker":
            currency = _currency(text)
            if currency is not None:
                return currency
    return None


def _currency(text: str) -> QuotedCurrency | None:
    lower = text.casefold()
    if text == EURO_SYMBOL or lower in EURO_WORDS:
        return "EUR"
    if text in _USD or lower in _USD:
        return "USD"
    if text == "$":
        return "$"
    if lower in _GBP:
        return "GBP"
    is_other = (
        text in OTHER_CURRENCY_SYMBOLS
        or (text.isupper() and text in OTHER_CURRENCY_CODES - _NOT_OTHER)
        or lower in OTHER_CURRENCY_WORDS - {"pound", "pounds", "dollar", "dollars"}
    )
    return "other" if is_other else None
