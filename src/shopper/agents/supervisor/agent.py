"""The supervisor's parsing: turn the input into a request.

The model names the category, classifies the scope, points at the budget phrase and judges its
currency; code does the rest. Rules: docs/architecture/supervisor.md. This module knows nothing
of the graph.
"""

import re
from decimal import Decimal
from enum import StrEnum
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from shopper import wording
from shopper.agents.shared.phrases import find_phrase
from shopper.agents.supervisor.prompt import CATEGORY_CORRECTION, SUPERVISOR_PROMPT
from shopper.calc.budget import BudgetReading, is_currency_marker, read_budget
from shopper.calc.display import euros
from shopper.config import Tier
from shopper.llm import ChatModel, Completion, LlmFailure, complete_structured
from shopper.state import (
    SCOPES_THAT_DO_NOT_RUN,
    SCOPES_WITHOUT_CATEGORY,
    Agent,
    DomainModel,
    Request,
    Scope,
    TrailEntry,
    TrailKind,
    Warning,
    WarningCode,
)

MAX_INPUT_CHARACTERS = 2000
MAX_CATEGORY_WORDS = 4
# The rule of the form check, as the trail and the second try's prompt state it.
CATEGORY_FORM = (
    f"a category has at most {MAX_CATEGORY_WORDS} words and at most one digit, inside a word"
)
# Keeps the scope and category of the same input as steady as the model allows.
SUPERVISOR_TEMPERATURE = 0.0

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_URL_TRAILING_PUNCTUATION = ".,;:!?)]}"
_MARKER_BEFORE = re.compile(r"([€£$¥₺]|[^\W\d_]+\.?)\s*$")
_MARKER_AFTER = re.compile(r"\s*([€£$¥₺]|[^\W\d_]+\.?)")
_MINUS_SIGNS = "-–−"


class Repair(NamedTuple):
    """A repair of the model's reply, as its trail entry states it."""

    summary: str
    reason: str


class InputTooLongError(Exception):
    """The input is longer than the app reads; no request exists."""


class ModelCallError(Exception):
    """The supervisor's model call failed; no request exists."""

    def __init__(self, failure: LlmFailure) -> None:
        super().__init__(f"{failure.kind}: {failure.detail}")
        self.failure = failure


class BudgetCurrency(StrEnum):
    """The model's judgement of the currency the budget phrase is in."""

    EUR = "eur"
    OTHER = "other"
    NONE_STATED = "none_stated"


class Extraction(BaseModel):
    """The fields the model fills, and nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str | None
    scope: Scope
    budget_phrase: str | None
    budget_amount: float | None
    budget_currency: BudgetCurrency | None


class ParsedRequest(DomainModel):
    request: Request
    warnings: tuple[Warning, ...] = ()
    trail: tuple[TrailEntry, ...] = ()


def input_too_long(input_text: str) -> bool:
    """Whether the input is longer than the app reads; the API refuses it before a run starts."""
    return len(input_text) > MAX_INPUT_CHARACTERS


async def parse_request(input_text: str, chat: ChatModel, tier: Tier = "small") -> ParsedRequest:
    """Turn the input into a request, with its warnings and its trail entries.

    Raises InputTooLongError for input over the limit and ModelCallError when a model call
    fails, the second try for a category included; in both cases there is no request.
    """
    if input_too_long(input_text):
        raise InputTooLongError(f"the input is over {MAX_INPUT_CHARACTERS} characters")
    if not input_text.strip():
        return _without_model(input_text, Scope.UNCLEAR, "the input is empty")
    urls = find_urls(input_text)
    if len(urls) > 1:
        return _without_model(
            input_text, Scope.SEVERAL_PRODUCTS, "the input holds more than one link"
        )
    result = await _extract(input_text, chat, tier, SUPERVISOR_PROMPT)
    if isinstance(result, LlmFailure):
        raise ModelCallError(result)
    category, repairs = await _category(input_text, chat, tier, result.value)
    return _to_request(input_text, urls[0] if urls else None, result, category, repairs)


async def read_product_name(
    request: Request, name: str, chat: ChatModel, tier: Tier = "small"
) -> ParsedRequest:
    """The request with the category and scope the model reads from the product name.

    For a pasted link whose request had no category: the name read from the page goes to the
    model with the same prompt, and its category and scope replace those of the request. The
    budget, the text and the link stay. Raises ModelCallError when a model call fails.
    """
    result = await _extract(name, chat, tier, SUPERVISOR_PROMPT)
    if isinstance(result, LlmFailure):
        raise ModelCallError(result)
    category, repairs = await _category(name, chat, tier, result.value)
    named = Request.model_validate(
        {**request.model_dump(), "category": category, "scope": result.value.scope}
    )
    summary = (
        f'Named the category from the product "{name}": '
        f"{category or 'no category'}; scope {named.scope}"
    )
    entries = (
        _entry(TrailKind.DECIDED, summary),
        *(_entry(TrailKind.DECIDED, repair.summary, repair.reason) for repair in repairs),
    )
    trail = tuple(
        entry.model_copy(update={"model_tier": result.tier, "model": result.model})
        for entry in entries
    )
    return ParsedRequest(request=named, trail=trail)


def find_urls(text: str) -> tuple[str, ...]:
    """The different http and https URLs in the text, in order, without punctuation after them."""
    urls = (match.rstrip(_URL_TRAILING_PUNCTUATION) for match in _URL.findall(text))
    return tuple(dict.fromkeys(urls))


def _without_model(input_text: str, scope: Scope, reason: str) -> ParsedRequest:
    """The request for input the model never sees."""
    entry = TrailEntry(
        agent=Agent.SUPERVISOR,
        kind=TrailKind.DECIDED,
        summary=f"Scope {scope} without asking the model",
        reason=reason,
    )
    return ParsedRequest(request=Request(original_text=input_text, scope=scope), trail=(entry,))


async def _extract(
    input_text: str, chat: ChatModel, tier: Tier, system: str
) -> Completion[Extraction] | LlmFailure:
    return await complete_structured(
        chat, tier, input_text, Extraction, system=system, temperature=SUPERVISOR_TEMPERATURE
    )


async def _category(
    input_text: str, chat: ChatModel, tier: Tier, extraction: Extraction
) -> tuple[str | None, tuple[Repair, ...]]:
    """The category the request gets, and the repair that says how it differs from the reply.

    A category that fails the form check gets one second try: the model is asked again, told
    which category it gave and the rule that one broke. Only the category of that reply is used.
    Raises ModelCallError when that call fails.
    """
    category = _normalised(extraction.category)
    if category is None:
        return None, ()
    dropped = f'Dropped the category "{category}"'
    if extraction.scope in SCOPES_WITHOUT_CATEGORY:
        return None, (Repair(dropped, f"a {extraction.scope} request carries no category"),)
    if _has_category_form(category):
        return category, ()
    correction = CATEGORY_CORRECTION.format(category=category, rule=CATEGORY_FORM)
    second = await _extract(input_text, chat, tier, SUPERVISOR_PROMPT + correction)
    if isinstance(second, LlmFailure):
        raise ModelCallError(second)
    retried = _normalised(second.value.category)
    if retried is not None and _has_category_form(retried):
        summary = f'Asked again for the category: "{category}" became "{retried}"'
        return retried, (Repair(summary, CATEGORY_FORM),)
    outcome = "no category" if retried is None else f'"{retried}"'
    return None, (Repair(dropped, f"{CATEGORY_FORM}; the second try gave {outcome}"),)


def _to_request(
    input_text: str,
    product_url: str | None,
    completion: Completion[Extraction],
    category: str | None,
    category_repairs: tuple[Repair, ...],
) -> ParsedRequest:
    """Repair the model's reply into a request and read the budget from the phrase it gave."""
    extraction = completion.value
    repairs = list(category_repairs)

    scope = extraction.scope
    if scope not in SCOPES_THAT_DO_NOT_RUN and category is None and product_url is None:
        repairs.append(
            Repair(f"Changed the scope from {scope} to unclear", "there is no category and no link")
        )
        scope = Scope.UNCLEAR

    budget, warnings, budget_entries = (
        (None, (), ())
        if scope in SCOPES_THAT_DO_NOT_RUN or extraction.budget_phrase is None
        else _budget(
            input_text,
            extraction.budget_phrase,
            extraction.budget_amount,
            extraction.budget_currency,
        )
    )
    request = Request(
        original_text=input_text,
        product_url=product_url,
        category=category,
        budget=budget,
        scope=scope,
    )
    entries = (
        _entry(TrailKind.DECIDED, _understood(request)),
        *budget_entries,
        *(_entry(TrailKind.DECIDED, repair.summary, repair.reason) for repair in repairs),
    )
    trail = tuple(
        entry.model_copy(update={"model_tier": completion.tier, "model": completion.model})
        for entry in entries
    )
    return ParsedRequest(request=request, warnings=warnings, trail=trail)


def _entry(kind: TrailKind, summary: str, reason: str | None = None) -> TrailEntry:
    return TrailEntry(agent=Agent.SUPERVISOR, kind=kind, summary=summary, reason=reason)


def _understood(request: Request) -> str:
    budget = "no budget" if request.budget is None else f"budget {euros(request.budget)}"
    return f"Understood as: {request.category or 'no category'}; scope {request.scope}; {budget}"


def _normalised(category: str | None) -> str | None:
    """Trimmed, lower case, single spaces; missing when nothing is left."""
    return " ".join(category.lower().split()) or None if category is not None else None


def _has_category_form(category: str) -> bool:
    """At most four words, and at most one digit, which sits in a word that also has a letter.

    "3d printer" passes; a bare number ("pan 28 cm"), an attached size ("28cm pan") and a model
    number ("wh1000xm4 headphones") do not.
    """
    words = category.split()
    with_digit = [word for word in words if any(character.isdigit() for character in word)]
    digits = sum(character.isdigit() for character in category)
    has_digit_form = digits == 0 or (
        digits == 1 and any(character.isalpha() for character in with_digit[0])
    )
    return len(words) <= MAX_CATEGORY_WORDS and has_digit_form


def _budget(
    input_text: str,
    model_phrase: str,
    model_amount: float | None,
    model_currency: BudgetCurrency | None,
) -> tuple[Decimal | None, tuple[Warning, ...], tuple[TrailEntry, ...]]:
    """The budget, or the warning and trail entries that say why there is none."""
    span = find_phrase(model_phrase, input_text)
    if span is None:
        entry = _entry(
            TrailKind.DECIDED,
            f'Ignored the budget phrase "{model_phrase}"',
            "the budget phrase is not in the input",
        )
        return None, (), (entry,)
    phrase = _widened(input_text, *span)
    judgement = None if model_currency is None else model_currency.value
    reading = _checked(read_budget(phrase, judgement), model_amount)
    if reading.warning_code is not None:
        code = reading.warning_code
        warning = Warning(code=code, message=wording.budget_warning(code, phrase))
        reason = f"{code} (judged by the model)" if reading.judged_by_model else str(code)
        entry = _entry(TrailKind.EXCLUDED, f'Budget "{phrase}" not applied', reason)
        return None, (warning,), (entry,)
    if reading.from_range:
        entry = _entry(
            TrailKind.DECIDED,
            f'Read the budget "{phrase}" as {euros(reading.amount)}',
            "a range is read as its higher amount",
        )
        return reading.amount, (), (entry,)
    return reading.amount, (), ()


def _checked(reading: BudgetReading, model_amount: float | None) -> BudgetReading:
    """Unreadable when code and the model read different amounts: the phrase holds more."""
    if reading.amount is None:
        return reading
    if model_amount is not None and Decimal(str(model_amount)) == reading.amount:
        return reading
    return BudgetReading(warning_code=WarningCode.BUDGET_UNREADABLE)


def _widened(text: str, start: int, end: int) -> str:
    """The part of the text widened to whole tokens and to a currency marker on each side."""
    while start > 0 and _in_token(text, start - 1) and _in_token(text, start):
        start -= 1
    while end < len(text) and _in_token(text, end) and _in_token(text, end - 1):
        end += 1

    before = _MARKER_BEFORE.search(text, 0, start)
    if before and is_currency_marker(before.group(1), after_number=False):
        start = before.start()
    if start > 0 and text[start - 1] in _MINUS_SIGNS and not _in_token(text, start - 2):
        start -= 1

    after = _MARKER_AFTER.match(text, end)
    if after:
        after_number = text[end - 1].isdigit()
        marker = after.group(1)
        # A full stop belongs to the marker only when the marker needs it ("Fr.").
        for candidate in (marker.removesuffix("."), marker):
            if is_currency_marker(candidate, after_number=after_number):
                end = after.start(1) + len(candidate)
                break
    return text[start:end]


def _in_token(text: str, index: int) -> bool:
    """Whether the character is part of a run of digits or letters, separators in a number too."""
    if index < 0 or index >= len(text):
        return False
    if text[index].isalnum():
        return True
    return (
        text[index] in ".,"
        and 0 < index < len(text) - 1
        and text[index - 1].isdigit()
        and text[index + 1].isdigit()
    )
