"""The checks on what the TCO analyzer's model wrote, and the name check with the words a search
names a product by (`search_name`, which reads a name the same way), as pure functions.

Each fault function returns why something is left out, or nothing when it passes. Rules:
docs/architecture/option_research.md ("What a product page sells", "Durability judgement").
"""

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from types import MappingProxyType

from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.phrases import find_phrase, plain
from shopper.agents.shared.research import numbers_in, stands_in
from shopper.agents.tco.models import PageReading, ReadAmount, ReadJudgement, Sells, Sold
from shopper.calc.amounts import NUMBER_WORDS, parse_amount
from shopper.config import COLOUR_WORDS, MISSING_PART_WORDS, SIZE_UNITS
from shopper.tools.results import SearchResult

MONTHS_PER_YEAR = Decimal(12)
# A word of a name of at least this many letters may stand in another language's spelling of
# its ending ("Structure", "Structuur"): the text's word starts with all but its last two letters
# and is at most two letters longer or shorter. A shorter word stands as written ("Combi" is not
# "Compact").
STEMMED_LENGTH = 6
STEM_CUT = 2
LIFETIME = ("lifetime", "life-time", "levenslang", "levenslange", "lebenslang")
YEARS = ("year", "years", "yr", "yrs", "jaar", "jaren")
MONTHS = ("month", "months", "maand", "maanden")
_NUMBER_OR_WORD = r"[0-9]+(?:[.,][0-9]+)?|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
_DURATION = re.compile(rf"\b({_NUMBER_OR_WORD})[\s-]*({'|'.join(YEARS + MONTHS)})\b", re.IGNORECASE)
_WORD = re.compile(r"[^\W_]+(?:-[^\W_]+)*")
# A number with a unit after it, such as "1.7l", "1500w" or "10-inch", is a measure, not a model.
_MEASURE = re.compile(r"[0-9]+(?:[.,][0-9]+)?-?[^\W\d_]{0,6}")
MODEL_NUMBER_LENGTH = 4
# A model number a shop writes in parts ("DHP 490 Z", "WK 9342") is at most this many words, each
# shorter than a model number or a number, one of them a number of at least this many digits, so
# a size ("ON 24 cm") is no model number (left-over item 7 of task 1.12).
MAX_MODEL_NUMBER_PARTS = 3
MODEL_NUMBER_DIGITS = 3
# "&", "+" and "and" count as the same inside a brand ("Black+Decker", "Black & Decker").
_AND = re.compile(r"\s*(?:&|\+|\band\b)\s*")
# A plural adds at most three letters, ending in "s" or "en": "waterkokers", "koekenpannen".
PLURAL_ENDINGS = ("s", "en")
MAX_PLURAL_LETTERS = 3
_PART = re.compile(r"[^\W_]+")
# The parts a shop writes a product name in: between dashes, or in brackets.
_NAME_PARTS = re.compile(r" - |[()]")
# Two compounds that share their last part, written once: "klopboor-/schroefmachine".
_ELIDED = re.compile(r"([^\W_]+)-\s*(?:/|,|\ben\b|\bof\b)\s*([^\W_]+)")
NOT_THE_ITEM: Mapping[Sells, str] = MappingProxyType(
    {
        "set_or_bundle": "the page sells a set or bundle, not the item itself",
        "part_or_accessory": "the page sells a part or accessory, not the item itself",
        "other_kind": "the page sells another kind of product, not the item itself",
        "unclear": "it is unclear what the page sells",
    }
)
NOT_QUOTED = "what the page sells is not quoted from the page"
NO_MISSING_PART = "the page read says it lacks a part, but its quote names no missing part"


def text_of(result: SearchResult) -> str:
    """What a result says, its title included: shops put the product's name in the title."""
    return f"{result.title}\n{result.content}"


def names_product(text: str, brand: str, name: str, category: str) -> bool:
    """Whether the text names the product: it holds the brand, and at least one other word of the
    name that is not a word of the category (a model number or the line's name). When the name
    has a model number, that word is one of its model numbers: a neighbouring model shares the
    rest ("18V", "Combi"). A model number written in parts ("DHP 490 Z") counts as one, so its
    parts alone name nothing, and a size or a colour names nothing either ("7", "28", "cm",
    "zwart").

    A word with a digit has to stand as written; a long word may stand in another spelling of
    its ending.
    """
    plain_text = _anded(plain(text))
    if _anded(plain(brand)) not in plain_text:
        return False
    text_words = _WORD.findall(plain_text)
    words = {*text_words, *_joined(text_words)}
    own = name_words(brand, name, category)
    model_numbers = [word for word in (*own, *_joined(own)) if is_model_number(word)]
    naming = model_numbers or [
        word for word in own if not _is_size(word) and word not in COLOUR_WORDS
    ]
    return any(_word_stands(word, words) for word in naming)


def _is_size(word: str) -> bool:
    """A number, a measure or a unit: "7", "1.7l", "cm"."""
    return _MEASURE.fullmatch(word) is not None or word in SIZE_UNITS


def same_product(one: str, other: str, brand: str | None, category: str) -> bool:
    """Whether two product names name each other, by a brand one of them is known by; with no
    brand there is nothing to tell them apart by."""
    if brand is None:
        return False
    return names_product(one, brand, other, category) and names_product(other, brand, one, category)


def is_model_number(word: str) -> bool:
    """A word with a digit that is not a measure: "DHP482RTWJ" or "28081-70", not "1.7l",
    "1500w", "18v" or "10-inch"."""
    has_digit = any(character.isdigit() for character in word)
    return has_digit and len(word) >= MODEL_NUMBER_LENGTH and _MEASURE.fullmatch(word) is None


def search_name(name: str, brand: str | None) -> str:
    """The words a search names a product by: the first part of its name, cut at its dashes, that
    says more than the brand, with the brand in front when it lacks it, and without its sizes. A
    product page's whole name, with sizes, colours and selling words, finds little (task 1.13).
    A bare number is a size only with a unit after it: "Core 300" and "SBE 650" are models."""
    branded = _anded(plain(brand or ""))
    parts = [part.strip() for part in name.split(" - ") if part.strip()]
    part = next((each for each in parts if _anded(plain(each)) != branded), name)
    if brand is not None and branded not in _anded(plain(part)):
        part = f"{brand} {part}"
    words = part.split()
    return " ".join(
        word
        for word, after in zip(words, [*words[1:], ""], strict=True)
        if not _is_written_size(word, after)
    )


def _is_written_size(word: str, after: str) -> bool:
    """A unit, a number with its unit ("24cm", "1.7L"), a number before a unit ("24 cm"), or a
    sign with no word in it ("Ø")."""
    unit_after = next(iter(_WORD.findall(plain(after))), None) in SIZE_UNITS
    return all(
        each in SIZE_UNITS or _is_measure_with_unit(each) or unit_after
        for each in _WORD.findall(plain(word))
    )


def _is_measure_with_unit(word: str) -> bool:
    return _MEASURE.fullmatch(word) is not None and any(each.isalpha() for each in word)


def name_words(brand: str, name: str, category: str) -> tuple[str, ...]:
    """The words of a name besides its brand and its category."""
    left_out = set(_WORD.findall(_anded(plain(f"{brand} {category}")))) | {"and"}
    return tuple(word for word in _WORD.findall(_anded(plain(name))) if word not in left_out)


def _joined(words: Sequence[str]) -> tuple[str, ...]:
    """The runs of two or three neighbouring parts of a model number written as one word: "DHP
    490 Z" gives "dhp490" and "dhp490z" among them. A part is a short word or a number, and one
    of them a number of at least three digits."""
    runs: list[str] = []
    for start in range(len(words)):
        for end in range(start + 2, min(start + MAX_MODEL_NUMBER_PARTS, len(words)) + 1):
            parts = words[start:end]
            if not all(len(part) < MODEL_NUMBER_LENGTH or part.isdigit() for part in parts):
                break
            if any(part.isdigit() and len(part) >= MODEL_NUMBER_DIGITS for part in parts):
                runs.append("".join(parts))
    return tuple(runs)


def _anded(text: str) -> str:
    return " ".join(_AND.sub(" and ", text).split())


def _word_stands(word: str, words: set[str]) -> bool:
    if any(character.isdigit() for character in word) or len(word) < STEMMED_LENGTH:
        return word in words
    stem = word[:-STEM_CUT]
    return any(
        candidate.startswith(stem) and abs(len(candidate) - len(word)) <= STEM_CUT
        for candidate in words
    )


def judgement_fault(judged: ReadJudgement) -> str | None:
    """Why a candidate's durability judgement counts as unknown; missing when it stands. An
    `unknown` needs no reason."""
    if judged.durability_judgement is None:
        return "no durability judgement was given"
    if judged.durability_judgement == "unknown":
        return None
    reason = (judged.durability_reason or "").strip()
    if not reason:
        return "its durability judgement gives no reason"
    fault = fault_in(reason)
    if fault is not None:
        return f"the reason for its durability judgement holds {fault}"
    return None


def page_sells(
    reading: PageReading,
    page: SearchResult,
    local_term: str | None,
    *,
    set_requested: bool,
) -> Sold:
    """What the page sells by the read: what most of the amounts for the page's own product (its
    title) sell, or of all its amounts when none names it, since a page shows other products too.
    An amount counts only when what it sells is quoted from the page; unclear or a tie is not the
    item.

    The item stands when the page's name holds the local term, or its quote does; `local_term`
    is missing when that check is skipped. An item sold incomplete needs a missing part in its
    quote. A set stands only when a set is asked for, with its piece count quoted.
    """
    quoted = [
        amount
        for result in reading.results
        for amount in result.amounts
        if amount.sells_quote.strip() and stands_in(amount.sells_quote, page)
    ]
    if not quoted:
        return Sold(None, NOT_QUOTED)
    own = [amount for amount in quoted if _same_name(amount.name, page.title)]
    deciding = own or quoted
    ranked = Counter(amount.sells for amount in deciding).most_common(2)
    if len(ranked) == 2 and ranked[0][1] == ranked[1][1]:
        return Sold(None, NOT_THE_ITEM["unclear"])
    sells = ranked[0][0]
    with_it = [amount for amount in deciding if amount.sells == sells]
    if sells == "the_item":
        sold = _the_item(with_it, page, local_term)
        return Sold("incomplete") if sold.sells and _says_bare(page.title) else sold
    if sells == "incomplete":
        return _incomplete(with_it)
    if sells == "set_or_bundle" and set_requested:
        return _set(with_it, page)
    return Sold(None, NOT_THE_ITEM[sells])


def _the_item(amounts: Sequence[ReadAmount], page: SearchResult, local_term: str | None) -> Sold:
    if local_term is None:
        return Sold("the_item")
    texts = (page.title, *(amount.sells_quote for amount in amounts))
    if any(names_kind(local_term, _without_category(text, local_term)) for text in texts):
        return Sold("the_item")
    return Sold(
        None, f'neither its name nor what the page sells holds the local term "{local_term}"'
    )


def _says_bare(name: str) -> bool:
    """Whether a product's own name says it is sold without a part, whatever the page read says
    (the Makita DHP458Z "(Body)", read as the item in task 1.10): a missing-part word of several
    words anywhere, one of a single word only as a part of its own, between dashes or in
    brackets, so a "soft-touch body" is not bare."""
    parts = {plain(part).strip() for part in _NAME_PARTS.split(name)}
    return any(
        find_phrase(words, name) is not None if " " in words else words in parts
        for words in MISSING_PART_WORDS
    )


def _without_category(name: str, term: str) -> str:
    """The name without a part that is only the term in the plural: the shop's category, which
    names no product ("Rommelsbacher - Reisdompelaar Type 343 - Waterkokers - 350 Watt" is a
    travel immersion heater, task 1.14)."""
    wanted = plain(term)
    return " - ".join(
        part
        for part in name.split(" - ")
        if not (
            (found := plain(part).strip()) != wanted
            and found.startswith(wanted)
            and found.endswith(PLURAL_ENDINGS)
            and len(found) - len(wanted) <= MAX_PLURAL_LETTERS
        )
    )


def _incomplete(amounts: Sequence[ReadAmount]) -> Sold:
    """The item sold without a part it needs, when a quote names the part missing."""
    named = any(
        find_phrase(words, amount.sells_quote) is not None
        for amount in amounts
        for words in MISSING_PART_WORDS
    )
    return Sold("incomplete") if named else Sold(None, NO_MISSING_PART)


def _set(amounts: Sequence[ReadAmount], page: SearchResult) -> Sold:
    """A set, with the first piece count quoted from the page."""
    for amount in amounts:
        if piece_count_fault(amount, page) is None:
            return Sold("set_or_bundle", piece_count=amount.piece_count)
    return Sold(None, "a set is asked for and it has no quoted piece count")


def piece_count_fault(amount: ReadAmount, page: SearchResult) -> str | None:
    """Why a set has no usable piece count; missing when it has one."""
    quote = amount.piece_count_quote or ""
    if amount.piece_count is None or amount.piece_count < 1 or not quote.strip():
        return "it has no quoted piece count"
    if not stands_in(quote, page) or Decimal(amount.piece_count) not in numbers_in(quote):
        return "its piece count is not quoted from the page"
    return None


def names_kind(term: str, text: str) -> bool:
    """Whether the text names the kind of product by its local term. A Dutch compound stands
    written as one word, with a hyphen or apart ("Accu-boormachine"), inside a longer one
    ("klopboormachine"), with its last part shared ("klopboor-/schroefmachine" holds
    "klopboormachine"), and after its first word ("Accu Klopboormachine" names an
    "accuboormachine"). A last part shorter than six letters stands only as written, so a
    "braadpan" is no "koekenpan"."""
    if find_phrase(term, text) is not None:
        return True
    wanted = "".join(_PART.findall(plain(term)))
    parts = _PART.findall(plain(text))
    words = {
        *parts,
        *(one + other for one, other in zip(parts, parts[1:], strict=False)),
        *_unshared(plain(text)),
    }
    if any(wanted in word for word in words):
        return True
    return any(
        wanted[:cut] in parts and any(wanted[cut:] in word for word in words)
        for cut in range(1, len(wanted) - STEMMED_LENGTH + 1)
    )


def _unshared(text: str) -> tuple[str, ...]:
    """The first of two compounds written with a shared last part, with each ending the second
    may share: "klopboor-/schroefmachine" gives "klopboormachine" among them."""
    return tuple(
        first + second[cut:]
        for first, second in _ELIDED.findall(text)
        for cut in range(1, len(second))
    )


def _same_name(name: str, other: str) -> bool:
    """Whether two names are the same, case, spaces and punctuation aside."""
    return _WORD.findall(plain(name)) == _WORD.findall(plain(other))


def years_in(quote: str) -> Decimal | None:
    """The first duration a quote states, in years, months converted; missing when it has none."""
    found = _DURATION.search(quote)
    if found is None:
        return None
    number, unit = found.group(1).casefold(), found.group(2).casefold()
    amount = Decimal(NUMBER_WORDS[number]) if number in NUMBER_WORDS else parse_amount(number)
    if amount is None or amount <= 0:
        return None
    return amount / MONTHS_PER_YEAR if unit in MONTHS else amount


def promises_a_lifetime(quote: str) -> bool:
    return any(word in plain(quote) for word in LIFETIME)
