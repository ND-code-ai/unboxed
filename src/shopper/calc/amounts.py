"""The one amount parser: a budget, a JSON-LD price, or a cost in a search result.

`parse_amount` reads the number only; which currency an amount is in is decided by its caller.
The rules for a number are the thousands and decimals row of the budget table in
docs/architecture/supervisor.md.
"""

import re
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

# Thousands grouped by a space, a no-break space or a narrow no-break space.
_THOUSANDS_BY_SPACE = r"[0-9]{1,3}(?:[   ][0-9]{3})+(?:[.,][0-9]{1,2})?(?![0-9])"
NUMBER = rf"{_THOUSANDS_BY_SPACE}|[0-9]+(?:[.,][0-9]+)*"
_NUMBER = re.compile(NUMBER)
_SEPARATOR = re.compile(r"[.,]|\s")
_UNITS_AND_TEENS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
# Numbers a model may write in words; each counts as the same number in digits.
NUMBER_WORDS: Mapping[str, int] = MappingProxyType(
    {
        **{word: value for value, word in enumerate(_UNITS_AND_TEENS)},
        **{word: 10 * tens for tens, word in enumerate(_TENS, start=2)},
        "hundred": 100,
        "thousand": 1000,
    }
)

# Small numbers in Dutch, for durations only: "een" is also the article "a", so these are never
# counted as numbers in a quote check.
DUTCH_NUMBER_WORDS: Mapping[str, int] = MappingProxyType(
    {
        "een": 1,
        "één": 1,
        "twee": 2,
        "drie": 3,
        "vier": 4,
        "vijf": 5,
        "zes": 6,
        "zeven": 7,
        "acht": 8,
        "negen": 9,
        "tien": 10,
        "elf": 11,
        "twaalf": 12,
    }
)
_ALL_WORDS = sorted({*NUMBER_WORDS, *DUTCH_NUMBER_WORDS}, key=len, reverse=True)
# A number in digits or in words, English tens and units joined by a hyphen included
# ("twenty-five"), as a duration may write it.
SPELLED_NUMBER = (
    r"[0-9]+(?:[.,][0-9]+)?"
    rf"|(?:{'|'.join(_TENS)})-(?:{'|'.join(_UNITS_AND_TEENS[1:10])})"
    rf"|{'|'.join(_ALL_WORDS)}"
)

EURO_SYMBOL = "€"
EURO_WORDS = frozenset({"eur", "euro", "euros"})


def parse_amount(text: str) -> Decimal | None:
    """The amount a number is, or missing when its separators fit no pattern.

    A separator followed by exactly three digits is thousands; by one or two, and last,
    decimals.
    """
    number = text.strip()
    if _NUMBER.fullmatch(number) is None:
        return None
    groups = _SEPARATOR.split(number)
    separators = ["space" if found.isspace() else found for found in _SEPARATOR.findall(number)]
    if not separators:
        return Decimal(number)
    has_decimals = len(groups[-1]) in (1, 2)
    whole, thousands = (groups[:-1], separators[:-1]) if has_decimals else (groups, separators)
    if len(set(thousands)) > 1 or any(len(group) != 3 for group in whole[1:]):
        return None
    if thousands and len(whole[0]) > 3:
        return None
    if has_decimals and (separators[-1] == "space" or separators[-1] in thousands):
        return None
    return Decimal("".join(whole) + (f".{groups[-1]}" if has_decimals else ""))


def spelled_amount(number: str) -> Decimal | None:
    """The amount of a number `SPELLED_NUMBER` matched, in digits or in words."""
    word = number.casefold()
    if "-" in word and not word[0].isdigit():
        tens, units = word.split("-", 1)
        if tens in NUMBER_WORDS and units in NUMBER_WORDS:
            return Decimal(NUMBER_WORDS[tens] + NUMBER_WORDS[units])
        return None
    if word in NUMBER_WORDS:
        return Decimal(NUMBER_WORDS[word])
    if word in DUTCH_NUMBER_WORDS:
        return Decimal(DUTCH_NUMBER_WORDS[word])
    return parse_amount(number)
