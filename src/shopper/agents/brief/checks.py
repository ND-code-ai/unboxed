"""The checks on what the brief agent's model wrote, as pure functions.

Each returns why something cannot be shown, or nothing when it can. Rules:
docs/architecture/category_brief.md, docs/architecture/interview.md and
docs/architecture/data_sources.md ("Research rules").
"""

import re
from collections.abc import Sequence

from shopper.agents.brief.models import Phrased, ReadFactor, Said
from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.phrases import find_phrase, plain
from shopper.agents.shared.research import is_quoted, numbers_in
from shopper.config import MAX_CHOICE_CHARACTERS
from shopper.state import MAX_CHOICES, MAX_RESEARCHED_FACTORS, MIN_CHOICES, Request, StatedIn
from shopper.tools.results import SearchResult

# How the model's statement about a care factor has to open: "Some" and the category in the
# plural, as in "Some frying pans need ...".
CARE_OPENING = "some"
# A local category term is what a shopper types into a comparison site's search box.
MAX_LOCAL_TERM_WORDS = 3
# Advice the product's tone rules out (docs/product.md, "Tone"), in the words the model writes
# for the user to read; the user's own phrases may hold it.
_ADVICE_WORDS = re.compile(r"\b(?:should|must)(?:n't|nt)?\b", re.IGNORECASE)
ADVICE_FAULT = '"should" or "must"'
# The endings an English or Dutch plural adds: "pans", "dishes", "koekenpannen".
_PLURAL = "(?:s|es|en|nen)?"
# A web address in the user's words: a scheme, "www." or a host name such as "pans.example.com".
_LINK = re.compile(r"https?://|\bwww\.|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b", re.IGNORECASE)


def unwritable(proposed: ReadFactor) -> str | None:
    """Why the factor's own words cannot be shown; missing when they can."""
    if not proposed.name.strip() or not proposed.why.strip():
        return "it has no name or no explanation"
    return _first_fault(("name", proposed.name), ("explanation", proposed.why))


def factor_fault(
    proposed: ReadFactor, results: Sequence[SearchResult], kept: Sequence[str]
) -> str | None:
    """Why a factor of a read is left out; missing when it passes every check."""
    if not 1 <= proposed.result <= len(results):
        return "it cites no search result that was shown"
    if not is_quoted(proposed.quote, results[proposed.result - 1].content):
        return "its quote is not in the search result it cites"
    if plain(proposed.name) in {plain(name) for name in kept}:
        return "it repeats an earlier factor"
    if len(kept) >= MAX_RESEARCHED_FACTORS:
        return f"at most {MAX_RESEARCHED_FACTORS} researched factors are kept"
    return None


def statement_fault(statement: str, category: str) -> str | None:
    """Why a care statement cannot be shown; missing when it can."""
    if not statement.strip():
        return "it has no statement"
    if not _opens_with_the_category(statement, category):
        return 'its statement does not open with "Some" and the category in the plural'
    return _first_fault(("statement", statement))


def _opens_with_the_category(statement: str, category: str) -> bool:
    """Whether the statement opens "Some" and the category in the plural, in any case.

    The category's last word may take any plural ("knife", "knives"), so it is compared on its
    stem: all but its last two letters, and at least three.
    """
    words = statement.casefold().split()
    *leading, last = category.casefold().split()
    named = words[1 : len(leading) + 2]
    if not words or words[0] != CARE_OPENING or len(named) != len(leading) + 1:
        return False
    return named[:-1] == leading and named[-1].startswith(last[: max(3, len(last) - 2)])


def question_fault(phrased: Phrased, source_text: str) -> str | None:
    """Why a question cannot be shown; missing when it can."""
    reason = phrased.reason or ""
    if not phrased.text.strip() or not reason.strip():
        return "it has no question or no reason"
    fault = _first_fault(("question", phrased.text), ("reason", reason))
    if fault is not None:
        return fault
    return _choices_fault([choice.strip() for choice in phrased.choices], source_text)


def _choices_fault(choices: Sequence[str], source_text: str) -> str | None:
    """Why the choices cannot be shown. A number in a choice has to stand in the search result
    the factor cites; a model never supplies one."""
    different = {choice.casefold() for choice in choices}
    if not MIN_CHOICES <= len(choices) <= MAX_CHOICES or len(different) != len(choices):
        return f"it does not have {MIN_CHOICES} to {MAX_CHOICES} different choices"
    sourced_numbers = numbers_in(source_text)
    for choice in choices:
        if not choice:
            return "a choice is empty"
        if len(choice) > MAX_CHOICE_CHARACTERS:
            return f"a choice is longer than {MAX_CHOICE_CHARACTERS} characters"
        fault = fault_in(choice, digits_allowed=True)
        if fault is not None:
            return f"a choice holds {fault}"
        if not numbers_in(choice) <= sourced_numbers:
            return "a choice holds a number that is not in the search result its factor cites"
    return None


def local_term_fault(term: str) -> str | None:
    """Why the local category term cannot be searched for and looked for in product names;
    missing when it can. It is a few plain words."""
    if not term.strip():
        return "it is empty"
    if len(term.split()) > MAX_LOCAL_TERM_WORDS:
        return f"it is more than {MAX_LOCAL_TERM_WORDS} words"
    fault = fault_in(term)
    return None if fault is None else f"it holds {fault}"


def stated_value_fault(value: str | None, phrase: str) -> str | None:
    """Why the value the model wrote for a stated requirement cannot be shown; missing when it
    can. A number in it has to stand in the request's phrase."""
    if value is None or not value.strip():
        return "it has no value"
    fault = fault_in(value, digits_allowed=True)
    if fault is not None:
        return f"its value holds {fault}"
    if not numbers_in(value) <= numbers_in(phrase):
        return "its value holds a number that is not in its phrase"
    return None


def own_phrase_fault(
    span: tuple[int, int], said: Said, request: Request, local_term: str | None = None
) -> str | None:
    """Why the part of what was said at this span cannot be a requirement of the user's own;
    missing when it can.

    The words are the user's, but the same claims are refused as in a model's words, except a
    number. The budget is known already: a phrase holding its amount is taken for it. So is the
    link, when the phrase is part of it. A reply never changes the request, so a phrase of the
    reply is refused as well when it holds a link, the category or the local category term, or is
    only a number.
    """
    phrase = said.text[span[0] : span[1]]
    if request.product_url is not None and _overlaps(span, request.product_url, said):
        return "it is the link"
    fault = fault_in(phrase, digits_allowed=True)
    if fault is not None:
        return f"its phrase holds {fault}"
    if request.budget is not None and request.budget in numbers_in(phrase):
        return "it is the budget"
    if said.stated_in is StatedIn.REPLY:
        return _reply_phrase_fault(phrase, request.category, local_term)
    return None


def _reply_phrase_fault(phrase: str, category: str | None, local_term: str | None) -> str | None:
    if _LINK.search(phrase):
        return "it holds a link"
    # An amount with a currency marker is refused before this.
    if not any(character.isalpha() for character in phrase):
        return "it is only a number or an amount"
    if category is not None and _holds_term(phrase, category):
        return "it holds the category"
    if local_term is not None and _holds_term(phrase, local_term):
        return "it holds the local category term"
    return None


def _holds_term(phrase: str, term: str) -> bool:
    """Whether the phrase holds the term as whole words, its last word in the plural too."""
    return re.search(rf"\b{re.escape(plain(term))}{_PLURAL}\b", plain(phrase)) is not None


def _overlaps(span: tuple[int, int], url: str, said: Said) -> bool:
    """Whether the span shares a character with the link where it stands in what was said, or,
    when it stands nowhere in the request, whether the span's words are part of it."""
    at = find_phrase(url, said.text)
    if at is None:
        is_request = said.stated_in is StatedIn.REQUEST
        return is_request and plain(said.text[span[0] : span[1]]) in plain(url)
    return span[0] < at[1] and at[0] < span[1]


def _first_fault(*parts: tuple[str, str]) -> str | None:
    """Why the first of these named parts cannot be shown; missing when none of them holds
    what a model may not write."""
    for part, text in parts:
        fault = fault_in(text) or (ADVICE_FAULT if _ADVICE_WORDS.search(text) else None)
        if fault is not None:
            return f"its {part} holds {fault}"
    return None
