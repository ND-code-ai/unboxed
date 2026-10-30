"""The check on every string a model writes for the user to read.

A model never writes a number or an amount of money, because numbers shown to the user are
computed in code, and never a generic environmental claim (docs/eu_market.md, "Environmental
claims"). What fails is left out by its caller; it is never repaired.
"""

import re

from shopper.calc.budget import EURO_SYMBOL, OTHER_CURRENCY_SYMBOLS, is_currency_marker

# Lower case, with a space where a hyphen may stand.
GENERIC_ENVIRONMENTAL_TERMS = (
    "eco friendly",
    "ecofriendly",
    "eco conscious",
    "environmentally friendly",
    "environment friendly",
    "earth friendly",
    "planet friendly",
    "climate friendly",
    "nature friendly",
    "green",
    "greener",
    "greenest",
    "sustainable",
    "sustainably",
    "sustainability",
    "better for the planet",
    "good for the planet",
    "kind to the planet",
    "better for the environment",
    "good for the environment",
    "kind to the environment",
    "carbon neutral",
    "climate neutral",
    "net zero",
    "carbon negative",
    "climate positive",
    "low impact",
)

PLAIN_DIGITS = "0123456789"
# Hyphen, non-breaking hyphen, figure dash, en dash, em dash, horizontal bar and minus sign.
HYPHENS_AND_DASHES = "".join(map(chr, (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212)))
_CURRENCY_SYMBOLS = EURO_SYMBOL + "".join(sorted(OTHER_CURRENCY_SYMBOLS))
_WORD_OR_SYMBOL = re.compile(r"[^\W\d_]+\.?|[" + re.escape(_CURRENCY_SYMBOLS) + "]")
_HYPHENS = re.compile("[" + re.escape("-" + HYPHENS_AND_DASHES) + "]")
_GENERIC_TERM = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in GENERIC_ENVIRONMENTAL_TERMS) + r")\b"
)


def fault_in(text: str, *, digits_allowed: bool = False) -> str | None:
    """What a model-written string holds that it may not; missing when it holds none of it.

    A digit, a currency marker or a generic environmental term, named as the trail states it.
    A choice may hold plain digits: its numbers are checked against the source it cites instead,
    which a numeral such as "½" cannot be.
    """
    numerals = [character for character in text if character.isnumeric()]
    if numerals and not digits_allowed:
        return "a digit"
    if any(numeral not in PLAIN_DIGITS for numeral in numerals):
        return "a numeral other than a plain digit"
    tokens = _WORD_OR_SYMBOL.findall(text)
    if any(is_currency_marker(token, after_number=False) for token in tokens):
        return "a currency marker"
    if _GENERIC_TERM.search(" ".join(_HYPHENS.sub(" ", text).casefold().split())):
        return "a generic environmental term"
    return None
