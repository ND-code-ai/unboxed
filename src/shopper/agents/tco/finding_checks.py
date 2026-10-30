"""The checks on a finding's summary and rating, as pure functions.

The summary is the app's own words for one report, checked against the quote behind it and the
text the read saw (docs/adr/0005-findings-summarised-quote-logged.md). Each fault function
returns why a finding or its rating is left out, or nothing when it passes. Rules:
docs/architecture/option_evidence.md ("Findings").
"""

import re
from collections.abc import Iterable, Sequence
from decimal import Decimal

from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.phrases import plain
from shopper.agents.shared.research import numbers_in
from shopper.calc.amounts import parse_amount
from shopper.config import COPIED_RUN_WORDS, MAX_SUMMARY_WORDS

# Words that speak of more than one unit or one test; each stands in a summary only when it
# stands in its quote.
GENERALISING_WORDS = ("many", "most", "often", "always", "owners", "commonly")
_WORD = re.compile(r"[^\W_]+(?:-[^\W_]+)*")
# A summary speaks of one unit or one test ("One owner's pan ..."), so this word is no number.
_ONE = re.compile(r"\bone\b", re.IGNORECASE)
# Words that make a score one of an aspect, not an overall rating: a durability score is never
# shown as a rating (product.md, "Durability evidence").
ASPECT_WORDS = (
    "durability",
    "longevity",
    "lifespan",
    "build quality",
    "duurzaamheid",
    "levensduur",
    "haltbarkeit",
)
# A value on a scale: "4.5/5", "4.5 out of 5", "8/10", "4,5 van 5".
_RATING = re.compile(
    r"(?<![0-9.,])([0-9]+(?:[.,][0-9]+)?)\s*(?:/|out of|van|uit|von|of)\s*([0-9]+)(?![0-9.,])",
    re.IGNORECASE,
)


def copied_fault(summary: str, seen: Sequence[str], name_words: Iterable[str]) -> str | None:
    """Why a summary copies its source: it shares a run of six words with a text the read saw,
    compared as plain words. A run made only of the option's name and brand words does not
    count, since a summary has to name the product as the source does."""
    own = frozenset(plain(word) for word in name_words)
    summary_runs = {run for run in _runs(_words(summary)) if any(word not in own for word in run)}
    copied = any(summary_runs & set(_runs(_words(text))) for text in seen)
    return (
        "its summary copies six or more words in a row from the search results" if copied else None
    )


def _words(text: str) -> tuple[str, ...]:
    return tuple(_WORD.findall(plain(text)))


def _runs(words: Sequence[str]) -> Iterable[tuple[str, ...]]:
    return (
        tuple(words[start : start + COPIED_RUN_WORDS])
        for start in range(len(words) - COPIED_RUN_WORDS + 1)
    )


def summary_fault(summary: str, quote: str) -> str | None:
    """Why a summary says more than its quote, or what no string a model writes may hold."""
    words = _words(summary)
    if not words:
        return "it has no summary"
    if len(words) > MAX_SUMMARY_WORDS:
        return f"its summary is longer than {MAX_SUMMARY_WORDS} words"
    fault = fault_in(summary, digits_allowed=True)
    if fault is not None:
        return f"its summary holds {fault}"
    if not numbers_in(_ONE.sub(" ", summary)) <= numbers_in(quote):
        return "its summary holds a number that is not in its quote"
    quoted = set(_words(quote))
    general = [word for word in GENERALISING_WORDS if word in words and word not in quoted]
    if general:
        named = ", ".join(f'"{word}"' for word in general)
        return f"its summary generalises ({named}) where its quote does not"
    return None


def rating_in(quote: str) -> str | None:
    """The first value on a scale the quote states, as it writes it; missing when it states
    none, or a value above its scale."""
    for found in _RATING.finditer(quote):
        value, scale = parse_amount(found.group(1)), parse_amount(found.group(2))
        if value is not None and scale is not None and Decimal(0) < value <= scale:
            return found.group(0)
    return None


def scored_aspect(quote: str) -> str | None:
    """The aspect a rating quote scores, such as "durability", when it scores one; missing when
    it names none."""
    words = plain(quote)
    return next((aspect for aspect in ASPECT_WORDS if re.search(rf"\b{aspect}\b", words)), None)
