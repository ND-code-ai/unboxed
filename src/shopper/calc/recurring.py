"""A recurring cost: how often a consumable is replaced, read from its quote, and what it costs a
year. Rules: docs/architecture/option_research.md ("Recurring cost").

An interval in uses ("every 50 uses") or one the parser cannot read gives nothing, so the cost
stays not found; so does a pack with no readable count.
"""

import re
from decimal import Decimal

from shopper.calc.amounts import NUMBER, SPELLED_NUMBER, spelled_amount

DAYS_PER_YEAR = Decimal(365)
WEEKS_PER_YEAR = Decimal(52)
MONTHS_PER_YEAR = Decimal(12)
_PER_YEAR_OF_UNIT = {
    "day": DAYS_PER_YEAR,
    "week": WEEKS_PER_YEAR,
    "month": MONTHS_PER_YEAR,
    "year": Decimal(1),
}
_UNITS = {
    "day": "day",
    "days": "day",
    "dag": "day",
    "dagen": "day",
    "week": "week",
    "weeks": "week",
    "weken": "week",
    "month": "month",
    "months": "month",
    "maand": "month",
    "maanden": "month",
    "year": "year",
    "years": "year",
    "jaar": "year",
    "jaren": "year",
}
_NUMBER = SPELLED_NUMBER
_UNIT = "|".join(sorted(_UNITS, key=len, reverse=True))
_EVERY = r"(?:every|elke|iedere|ieder|elk|om de)"
_EVERY_N = re.compile(
    rf"\b{_EVERY}\s+(?:(?P<low>{_NUMBER})\s*(?:to|-|–|tot)\s*)?(?P<number>{_NUMBER})?\s*"
    rf"(?P<unit>{_UNIT})\b",
    re.IGNORECASE,
)
_TIMES = {"once": 1, "twice": 2, "een": 1, "één": 1, "twee": 2, "drie": 3, "vier": 4}
_PER = r"(?:a|per|each|every|in de|in het)"
_TIMES_A = re.compile(
    rf"\b(?P<times>{_NUMBER}|{'|'.join(_TIMES)})\s*(?:times|keer|maal)?\s*"
    rf"{_PER}\s+(?P<unit>{_UNIT})\b",
    re.IGNORECASE,
)
# A money amount in the quote ("€12.50 a month", "30 euro a year") is not a count of times; it
# is taken out before the interval is read.
_CURRENCY_WORD = r"(?:eur|euro|euros|usd|dollar|dollars|gbp|pound|pounds)"
_AMOUNT = re.compile(
    rf"(?:US\$|[€$£]|\b{_CURRENCY_WORD})\s?(?:{NUMBER})"
    rf"|\b(?:{NUMBER})\s?(?:[€$£]|{_CURRENCY_WORD}\b)",
    re.IGNORECASE,
)
# Once per unit, as in "per year" or "a new bag each month".
_ONCE_PER = re.compile(rf"\b{_PER}\s+(?P<unit>{_UNIT})\b", re.IGNORECASE)
_ADVERBS = {
    "yearly": "year",
    "annually": "year",
    "annual": "year",
    "jaarlijks": "year",
    "jaarlijkse": "year",
    "monthly": "month",
    "maandelijks": "month",
    "maandelijkse": "month",
    "weekly": "week",
    "wekelijks": "week",
    "wekelijkse": "week",
    "daily": "day",
    "dagelijks": "day",
    "dagelijkse": "day",
}
_ADVERB = re.compile(rf"\b(?P<adverb>{'|'.join(_ADVERBS)})\b", re.IGNORECASE)
_PACK = re.compile(r"\b(?:pack|packs|set of|pak|verpakking|stuks)\b", re.IGNORECASE)
_WHOLE_NUMBER = re.compile(r"\b[0-9]+\b")


def replacements_per_year(quote: str) -> Decimal | None:
    """How many times a year the quote says the consumable is replaced; a range of intervals
    takes its long end. Missing when the quote states no interval in time. A money amount in
    the quote is never read as a count."""
    quote = _AMOUNT.sub(" ", quote)
    found = _EVERY_N.search(quote)
    if found is not None:
        number = Decimal(1) if found.group("number") is None else spelled_amount(found["number"])
        if number is None or number <= 0:
            return None
        return _PER_YEAR_OF_UNIT[_UNITS[found["unit"].casefold()]] / number
    found = _TIMES_A.search(quote)
    if found is not None:
        word = found["times"].casefold()
        times = Decimal(_TIMES[word]) if word in _TIMES else spelled_amount(word)
        if times is None or times <= 0:
            return None
        return times * _PER_YEAR_OF_UNIT[_UNITS[found["unit"].casefold()]]
    found = _ADVERB.search(quote)
    if found is not None:
        return _PER_YEAR_OF_UNIT[_ADVERBS[found["adverb"].casefold()]]
    found = _ONCE_PER.search(quote)
    if found is not None:
        return _PER_YEAR_OF_UNIT[_UNITS[found["unit"].casefold()]]
    return None


def recurring_cost_per_year(amount: Decimal, replacements: Decimal, pack_count: int = 1) -> Decimal:
    """The amount divided by the pieces in its pack, times the replacements a year."""
    return amount / pack_count * replacements


def is_a_pack(amount_quote: str) -> bool:
    """Whether the quoted amount is for a pack, so its count is needed."""
    return _PACK.search(amount_quote) is not None


def pack_count(quote: str) -> int | None:
    """The pieces a pack holds: the one whole number in the quote, at least 1; missing
    otherwise."""
    numbers = _WHOLE_NUMBER.findall(quote)
    if len(numbers) != 1 or int(numbers[0]) < 1:
        return None
    return int(numbers[0])
