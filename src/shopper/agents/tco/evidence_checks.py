"""The checks on what the evidence read wrote, as pure functions.

Each fault function returns why something is left out, or nothing when it passes. Rules:
docs/architecture/option_evidence.md ("Evidence") and docs/architecture/data_sources.md
("Research rules").
"""

import re
from collections.abc import Sequence

from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.phrases import find_phrase, plain
from shopper.agents.shared.research import numbers_in, stands_in
from shopper.agents.tco.checks import name_words, names_product, text_of
from shopper.agents.tco.models import (
    EvidenceContext,
    ReadConsumable,
    ReadEvidenceItem,
    ReadLifespan,
    ReadWarranty,
)
from shopper.state import Source, SourceKind
from shopper.tools.results import SearchResult

NO_BRAND = "the product has no brand to check the result against"
_ELLIPSIS = re.compile(r"\.\.\.|…")
_WORD = re.compile(r"[^\W_]+(?:-[^\W_]+)*")
# What ends a passage of a result's text: a line, or the mark between two of Tavily's snippets.
_PASSAGE_BREAKS = ("\n", "[...]")
# Words of a product's name that name a material, a finish or a tier, not a product line
# (the LCA review of task 1.8.3: "Le Creuset Toughened Nonstick PRO" named its line by "pro").
LINE_GENERIC_WORDS = frozenset(
    """
    nonstick non-stick ceramic stainless steel cast iron carbon copper aluminium aluminum
    enameled enamelled anodized hard-anodized glass plastic
    pro professional classic original premium plus deluxe signature essentials series
    electric cordless brushless
    """.split()
)


def quote_fault(
    result: int, quote: str, results: Sequence[SearchResult], *, holds_a_number: bool
) -> str | None:
    """Why a quote does not stand in the result it cites; missing when it does.

    A text value's quote may join parts with an ellipsis, each found in order; a quote that code
    reads a number from has to stand in one piece.
    """
    if not 1 <= result <= len(results):
        return "it cites no search result that was shown"
    if not quote.strip():
        return "it has no quote"
    cited = results[result - 1]
    parts = [part for part in _ELLIPSIS.split(quote) if part.strip()]
    if holds_a_number and len(parts) > 1:
        return "a quote with a number is in two parts"
    if len(parts) == 1:
        return None if stands_in(parts[0], cited) else "its quote is not in the search result"
    return None if _in_order(parts, text_of(cited)) else "its quote is not in the search result"


def in_two_parts(quote: str) -> bool:
    """Whether a quote joins parts with an ellipsis."""
    return len([part for part in _ELLIPSIS.split(quote) if part.strip()]) > 1


def _in_order(parts: Sequence[str], text: str) -> bool:
    rest = text
    for part in parts:
        found = find_phrase(part, rest)
        if found is None:
            return False
        rest = rest[found[1] :]
    return True


def value_fault(value: str, quote: str) -> str | None:
    """Why a text value the read wrote may not be shown; a number is allowed only when it stands
    in its quote."""
    if not value.strip():
        return "it has no value"
    fault = fault_in(value, digits_allowed=True)
    if fault is not None:
        return f"it holds {fault}"
    if not numbers_in(value) <= numbers_in(quote):
        return "it holds a number that is not in its quote"
    return None


def names_line(text: str, brand: str, name: str, category: str) -> bool:
    """Whether the text names the product's line: its brand and one other word of its name that
    is not a category word, without the model-number rule, since a line spans models. A word for
    a material, a finish or a tier ("nonstick", "pro") names no line."""
    plain_text = plain(text)
    if plain(brand) not in plain_text:
        return False
    words = set(_WORD.findall(plain_text))
    own = (word for word in name_words(brand, name, category) if word not in LINE_GENERIC_WORDS)
    return any(word in words for word in own)


def passage(quote: str, result: SearchResult) -> str:
    """The result's title and the part of its text that holds the quote: the line, or the
    snippet between two "[...]", the quote stands in. A page that names many products, such as a
    buying guide, names the product of a quote only near it."""
    found = find_phrase(quote, result.content)
    if found is None:
        return result.title
    start, end = found
    before = max(result.content.rfind(mark, 0, start) for mark in _PASSAGE_BREAKS)
    afters = [at for mark in _PASSAGE_BREAKS if (at := result.content.find(mark, end)) >= 0]
    after = min(afters) if afters else len(result.content)
    return f"{result.title}\n{result.content[max(before, 0) : after]}"


def brand_fault(
    context: EvidenceContext, result: int, quote: str, *, about: str = "product"
) -> str | None:
    """Why the passage of a quote does not name the product, or its line when `about` is
    "line"."""
    if context.brand is None:
        return NO_BRAND
    text = passage(quote, context.results[result - 1])
    name, category = context.option.name, context.category
    names = (
        names_line(text, context.brand, name, category)
        if about == "line"
        else names_product(text, context.brand, name, category)
    )
    return None if names else f"the passage of its quote does not name the {about}"


def cited_source(
    read: ReadLifespan | ReadWarranty | ReadEvidenceItem | ReadConsumable,
    results: Sequence[SearchResult],
    *,
    label: str | None = None,
) -> Source:
    """The result a value is cited to, with who is speaking in it."""
    return Source(
        kind=SourceKind.URL,
        reference=results[read.result - 1].url,
        label=label,
        stated_by=read.stated_by,
    )
