"""Reading a stated budget, and whether an option fits it.

Sticker price only; nothing is converted or rounded. The rules for reading a budget phrase are in
docs/architecture/supervisor.md ("Reading the phrase").
"""

import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from shopper import wording
from shopper.calc.amounts import EURO_SYMBOL, EURO_WORDS, NUMBER, parse_amount
from shopper.calc.display import euros
from shopper.state import DomainModel, Listing, ProductOption, Warning, WarningCode

# Every three-letter ISO 4217 code of a currency other than the euro, with the codes withdrawn
# since 2020, which people still write.
OTHER_CURRENCY_CODES = frozenset(
    """
    AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP
    BYN BZD CAD CDF CHF CLP CNY COP CRC CUC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB FJD FKP GBP
    GEL GHS GIP GMD GNF GTQ GYD HKD HNL HRK HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS
    KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR
    MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF
    SAR SBD SCR SDG SEK SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD
    TWD TZS UAH UGX USD UYU UZS VED VES VND VUV WST XAF XCD XCG XOF XPF YER ZAR ZMW ZWG ZWL
    """.split()
)
OTHER_CURRENCY_SYMBOLS = frozenset("£$¥₺")
# Symbols written with letters, names in English, Dutch and German, and slang; lower case.
OTHER_CURRENCY_WORDS = frozenset(
    """
    zł zl złoty zloty złote zlote złotych zlotych zlotys
    kr krona kronor krone kroner kroon kronen
    kč koruna koruny korun
    ft forint forints
    leu lei
    pound pounds pond ponden pfund sterling
    dollar dollars
    fr. sfr franc francs frank franken
    yen
    lira lire liras
    quid bucks
    """.split()
)

_TOKEN = re.compile(
    rf"(?P<number>{NUMBER})"
    r"|(?P<word>[^\W\d_]+\.?)"
    r"|(?P<symbol>[€£$¥₺])"
    r"|(?P<minus>[-–−])"
)
_TRAILING_DASH = re.compile(r"(?<=[0-9])[.,]-+")

TokenKind = Literal["number", "word", "symbol", "minus"]
# The model's judgement of the currency of a budget phrase.
CurrencyJudgement = Literal["eur", "other", "none_stated"]


class BudgetReading(DomainModel):
    """What a budget phrase says: an amount in euro, or the code of the reason it has none.

    `judged_by_model` marks another currency that rests on the model's judgement and not on a
    listed marker.
    """

    amount: Decimal | None = None
    warning_code: WarningCode | None = None
    from_range: bool = False
    judged_by_model: bool = False


class _Token(DomainModel):
    kind: TokenKind
    text: str
    start: int
    end: int


def read_budget(phrase: str, judgement: CurrencyJudgement | None = None) -> BudgetReading:
    """Read the amount from a budget phrase; only numerals and currency markers are read.

    The currency is decided by a listed other-currency marker first, then by a euro marker, and
    only then by the model's judgement. When more than one warning applies, unreadable wins over
    another currency, which wins over not positive.
    """
    tokens = _tokens(_TRAILING_DASH.sub("", phrase))
    amounts = _amounts(tokens)
    if amounts is None or not 1 <= len(amounts) <= 2 or _has_other_numeral(phrase):
        return BudgetReading(warning_code=WarningCode.BUDGET_UNREADABLE)
    if _names_other_currency(tokens):
        return BudgetReading(warning_code=WarningCode.BUDGET_OTHER_CURRENCY)
    if judgement == "other" and not _names_euro(tokens):
        return BudgetReading(warning_code=WarningCode.BUDGET_OTHER_CURRENCY, judged_by_model=True)
    amount = max(amounts)
    if amount <= 0:
        return BudgetReading(warning_code=WarningCode.BUDGET_NOT_POSITIVE)
    return BudgetReading(amount=amount, from_range=len(amounts) == 2)


def is_currency_marker(text: str, *, after_number: bool) -> bool:
    """Whether a word or symbol marks a currency, the euro included.

    An ISO code that is not in upper case counts only right after a number ("40 usd"), because
    many codes are also words ("cup", "pen", "try").
    """
    return _is_euro_marker(text) or _is_other_currency_marker(text, after_number=after_number)


def within_budget(
    price: Decimal | None, budget: Decimal | None, shipping: Decimal | None = None
) -> bool | None:
    """Whether the price, with the shipping when one is stated, is within the budget; missing
    when the request has no budget or the option has no price."""
    if price is None or budget is None:
        return None
    return with_shipping(price, shipping) <= budget


def with_shipping(price: Decimal, shipping: Decimal | None) -> Decimal:
    """What buying it costs: the price plus the stated shipping, or the price alone when none is
    stated."""
    return price + (shipping or Decimal(0))


def nothing_within_budget_warning(
    options: Sequence[ProductOption],
    listings: Sequence[Listing],
    budget: Decimal | None,
) -> Warning | None:
    """The warning when a budget is given and no priced option and no listing is within it.

    An option counts with its stated shipping. A listing is judged on its price alone, because
    its shipping cost may be unknown.
    """
    prices = [option.price for option in options if option.price is not None]
    if budget is None or not prices:
        return None
    if any(within_budget(option.price, budget, option.shipping) for option in options):
        return None
    if any(listing.price <= budget for listing in listings):
        return None
    return Warning(
        code=WarningCode.NOTHING_WITHIN_BUDGET,
        message=wording.nothing_within_budget(euros(budget), euros(min(prices))),
    )


def _is_euro_marker(text: str) -> bool:
    return text == EURO_SYMBOL or _bare(text) in EURO_WORDS


def _is_other_currency_marker(text: str, *, after_number: bool) -> bool:
    if text in OTHER_CURRENCY_SYMBOLS or text.lower() in OTHER_CURRENCY_WORDS:
        return True
    bare = _bare(text)
    if bare in OTHER_CURRENCY_WORDS:
        return True
    return bare.upper() in OTHER_CURRENCY_CODES and (after_number or text.isupper())


def _bare(word: str) -> str:
    """A word in lower case without the full stop that may end it."""
    return word.lower().removesuffix(".")


def _tokens(phrase: str) -> tuple[_Token, ...]:
    return tuple(
        _Token(kind=match.lastgroup, text=match.group(), start=match.start(), end=match.end())
        for match in _TOKEN.finditer(phrase)
    )


def _amounts(tokens: Sequence[_Token]) -> list[Decimal] | None:
    """Every number in the phrase with its sign; missing when a part of it cannot be read."""
    amounts: list[Decimal] = []
    for index, token in enumerate(tokens):
        if token.kind == "word" and _is_glued_to_a_number(tokens, index):
            if not is_currency_marker(token.text, after_number=_follows_number(tokens, index)):
                return None
        if token.kind != "number":
            continue
        value = parse_amount(token.text)
        if value is None:
            return None
        amounts.append(-value if _is_negative(tokens, index) else value)
    return amounts


def _is_glued_to_a_number(tokens: Sequence[_Token], index: int) -> bool:
    """Whether a word touches a number with nothing between them, as in "5o" or "50eur"."""
    token = tokens[index]
    before = tokens[index - 1] if index > 0 else None
    after = tokens[index + 1] if index + 1 < len(tokens) else None
    return (before is not None and before.kind == "number" and before.end == token.start) or (
        after is not None and after.kind == "number" and after.start == token.end
    )


def _follows_number(tokens: Sequence[_Token], index: int) -> bool:
    return index > 0 and tokens[index - 1].kind == "number"


def _is_negative(tokens: Sequence[_Token], index: int) -> bool:
    """Whether a minus sign is attached to the number, directly or before its currency symbol.

    A sign that follows another number is the hyphen of a range ("30-50").
    """
    position = index - 1
    if position >= 0 and tokens[position].kind == "symbol":
        if tokens[position].end != tokens[position + 1].start:
            return False
        position -= 1
    if position < 0 or tokens[position].kind != "minus":
        return False
    if tokens[position].end != tokens[position + 1].start:
        return False
    return position == 0 or tokens[position - 1].kind != "number"


def _has_other_numeral(phrase: str) -> bool:
    """Whether the phrase holds a numeral other than the digits 0 to 9."""
    return any(character.isnumeric() and character not in "0123456789" for character in phrase)


def _names_euro(tokens: Sequence[_Token]) -> bool:
    return any(token.kind in ("word", "symbol") and _is_euro_marker(token.text) for token in tokens)


def _names_other_currency(tokens: Sequence[_Token]) -> bool:
    return any(
        token.kind in ("word", "symbol")
        and _is_other_currency_marker(token.text, after_number=_follows_number(tokens, index))
        for index, token in enumerate(tokens)
    )
