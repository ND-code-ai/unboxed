"""What every research loop does with search results, as pure functions.

The rules are in docs/architecture/data_sources.md ("Research rules") and hold for category
research, option research and the tier 1 LCA search alike.
"""

import re
from collections.abc import Iterable, Sequence
from decimal import Decimal

from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.phrases import find_phrase, plain
from shopper.calc.amounts import NUMBER, NUMBER_WORDS, parse_amount
from shopper.config import MAX_FOLLOW_UP_CHARACTERS
from shopper.tools.results import SearchResult

# One search result as a model reads it; the number is how the model cites it.
NUMBERED_RESULT = "[{number}] {title}\n{url}\n{content}"
_NUMBER = re.compile(NUMBER)
_WORD = re.compile(r"[^\W\d_]+")


def distinct_results(results: Iterable[SearchResult]) -> tuple[SearchResult, ...]:
    """Each URL once, in the order found: the results are de-duplicated before they are numbered."""
    first_by_url: dict[str, SearchResult] = {}
    for result in results:
        first_by_url.setdefault(result.url, result)
    return tuple(first_by_url.values())


def full_text(result: SearchResult) -> SearchResult:
    """The result as a read sees it: its full page text when the search gave one, so the quote
    check runs on the text the model read."""
    if result.raw_content is None:
        return result
    return result.model_copy(update={"content": result.raw_content})


def follow_up_fault(search_query: str, subject: str) -> str | None:
    """Why a follow-up search query a model wrote is discarded; missing when it may be searched.

    It has to name what is researched (the category, or a product option's name) and stay within
    the length limit, and it is checked like any other string a model writes, except that it may
    hold plain digits: a size or a model number narrows a search (task 1.11). A currency marker
    still fails it, so it never holds a price.
    """
    if plain(subject) not in plain(search_query):
        return f'it does not name "{subject}"'
    if len(search_query) > MAX_FOLLOW_UP_CHARACTERS:
        return f"it is longer than {MAX_FOLLOW_UP_CHARACTERS} characters"
    fault = fault_in(search_query, digits_allowed=True)
    return None if fault is None else f"it holds {fault}"


def is_quoted(quote: str, text: str) -> bool:
    """Whether the quote stands in the text, by the normalisation every copied phrase gets
    (`find_phrase`): a model that ends a quote with a full stop where the text goes on after a
    comma has still quoted it."""
    return find_phrase(quote, text) is not None


def stands_in(phrase: str, result: SearchResult) -> bool:
    """Whether the phrase stands in the result's title or its text."""
    return is_quoted(phrase, result.title) or is_quoted(phrase, result.content)


def numbers_in(text: str) -> frozenset[Decimal | str]:
    """Every number written in the text, by its amount, so "1,5", "1.5" and "three" and "3" are
    the same number.

    A number in digits the amount parser cannot read is kept as it is written.
    """
    in_digits = {_amount(number) for number in _NUMBER.findall(text)}
    in_words = {
        Decimal(NUMBER_WORDS[word])
        for word in _WORD.findall(text.casefold())
        if word in NUMBER_WORDS
    }
    return frozenset(in_digits | in_words)


def _amount(number: str) -> Decimal | str:
    amount = parse_amount(number)
    return number if amount is None else amount


def numbered(results: Sequence[SearchResult]) -> str:
    """The results as a model reads them, numbered from 1, so it can cite one by its number."""
    return "\n\n".join(
        NUMBERED_RESULT.format(
            number=number, title=result.title, url=result.url, content=result.content
        )
        for number, result in enumerate(results, start=1)
    )
