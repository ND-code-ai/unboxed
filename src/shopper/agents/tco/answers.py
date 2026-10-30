"""What the evidence read says about the answered factors: an option's factor values.

A `meets` or a `fails` stands only on a quote code finds in the cited result, in a passage that
names the product; anything else is `unverified`. Rules: docs/architecture/option_evidence.md
("Evidence", "Answers").
"""

from collections.abc import Sequence
from typing import NamedTuple

from shopper import wording
from shopper.agents.tco.evidence_checks import brand_fault, quote_fault, value_fault
from shopper.agents.tco.models import (
    AnsweredFactor,
    EvidenceContext,
    EvidenceReading,
    FailedAnswer,
    ReadFactorFit,
)
from shopper.agents.tco.prompt import (
    EVIDENCE_ANSWER,
    EVIDENCE_CARE,
    NO_ANSWERS,
    STATED_BY_THE_USER,
)
from shopper.agents.tco.trail import entry
from shopper.state import (
    CARE_AVOID_CHOICE_ID,
    Answer,
    AnswerStatus,
    DecisionFactor,
    FactorKind,
    FactorValue,
    Fit,
    Question,
    Source,
    SourceKind,
    TrailEntry,
    TrailKind,
)

# The kinds whose answer the read judges; a care factor only when its care is to be avoided.
JUDGED_KINDS = frozenset({FactorKind.COMPATIBILITY, FactorKind.REQUIREMENT, FactorKind.CARE})
NOT_JUDGED = "the read did not judge it"


class Fits(NamedTuple):
    """The option's factor values, the `fails` that passed the checks, and the trail."""

    values: tuple[FactorValue, ...]
    failed: tuple[FailedAnswer, ...]
    trail: tuple[TrailEntry, ...]


def answered_factors(
    factors: Sequence[DecisionFactor], questions: Sequence[Question], answers: Sequence[Answer]
) -> tuple[AnsweredFactor, ...]:
    """The factors the read judges, in the order of the factors: a compatibility, requirement or
    user's own factor answered `chosen` or `stated`, and a care factor answered `care-avoid`."""
    by_factor = {answer.factor_id: answer for answer in answers}
    asked = {question.factor_id: question for question in questions}
    judged = (
        _answered(factor, asked.get(factor.id), by_factor[factor.id])
        for factor in factors
        if factor.kind in JUDGED_KINDS and factor.id in by_factor
    )
    return tuple(each for each in judged if each is not None)


def _answered(
    factor: DecisionFactor, question: Question | None, answer: Answer
) -> AnsweredFactor | None:
    if answer.status not in (AnswerStatus.CHOSEN, AnswerStatus.STATED):
        return None
    if factor.kind is FactorKind.CARE:
        if answer.choice_id != CARE_AVOID_CHOICE_ID or question is None:
            return None
        care = question.text.removesuffix(wording.CARE_CLOSING_QUESTION).strip()
        return AnsweredFactor(factor, None, wording.CARE_AVOID, care)
    if factor.source is not None and factor.source.kind is SourceKind.USER:
        return AnsweredFactor(factor, None, answer.stated_phrase or factor.name)
    choices = {} if question is None else {choice.id: choice.text for choice in question.choices}
    text = answer.stated_value if answer.choice_id not in choices else choices[answer.choice_id]
    if text is None:
        return None
    return AnsweredFactor(factor, None if question is None else question.text, text)


def answers_input(answered: Sequence[AnsweredFactor]) -> str:
    """The answered factors, numbered from 1, as the read sees them."""
    lines = (
        EVIDENCE_CARE.format(number=number, factor=each.factor.name, care=each.care)
        if each.care is not None
        else EVIDENCE_ANSWER.format(
            number=number,
            factor=each.factor.name,
            question=each.question or STATED_BY_THE_USER,
            answer=each.answer,
        )
        for number, each in enumerate(answered, start=1)
    )
    return "\n".join(lines) or NO_ANSWERS


def factor_values(
    context: EvidenceContext,
    answered: Sequence[AnsweredFactor],
    reading: EvidenceReading | None,
    *,
    not_read: str | None = None,
) -> Fits:
    """A value per answered factor; with no reading every value is `unverified`, for the reason
    `not_read` gives."""
    if not answered:
        return Fits((), (), ())
    values: list[FactorValue] = []
    failed: list[FailedAnswer] = []
    reasons: list[str] = []
    for number, each in enumerate(answered, start=1):
        read = None if reading is None else _first(reading.fits, number)
        value, fault = _value(context, each.factor, read)
        values.append(value)
        if fault is not None:
            reasons.append(f"{each.factor.name}: {not_read or fault}")
        if value.fit is Fit.FAILS and read is not None and read.quote is not None:
            failed.append(FailedAnswer(each.factor, read.quote.strip(), value.source.reference))
    summary = "; ".join(
        f"{each.factor.name}: {value.fit}{_site(value)}"
        for each, value in zip(answered, values, strict=True)
    )
    found = entry(
        TrailKind.FOUND,
        f'Fit of "{context.option.name}" with your answers: {summary}',
        reason="; ".join(reasons) or None,
    )
    return Fits(tuple(values), tuple(failed), (found,))


def _first(fits: Sequence[ReadFactorFit], number: int) -> ReadFactorFit | None:
    return next((each for each in fits if each.factor == number), None)


def _value(
    context: EvidenceContext, factor: DecisionFactor, read: ReadFactorFit | None
) -> tuple[FactorValue, str | None]:
    """The value the read gives when it stands, or `unverified` with why a check turned it so;
    an `unverified` from the read itself needs no reason."""
    if read is None:
        return _unverified(factor), NOT_JUDGED
    if read.fit == "unverified":
        return _unverified(factor), None
    if read.result is None or read.quote is None or read.value is None:
        return _unverified(factor), "it has no quote or no value"
    fault = (
        quote_fault(read.result, read.quote, context.results, holds_a_number=False)
        or brand_fault(context, read.result, read.quote)
        or value_fault(read.value, read.quote)
    )
    if fault is not None:
        return _unverified(factor), fault
    source = Source(
        kind=SourceKind.URL,
        reference=context.results[read.result - 1].url,
        stated_by=read.stated_by,
    )
    settled = FactorValue(
        factor_id=factor.id, value=read.value.strip(), fit=Fit(read.fit), source=source
    )
    return settled, None


def _unverified(factor: DecisionFactor) -> FactorValue:
    """An `unverified` value has the factor's own source; only the usage factor has none, and
    it is never judged."""
    if factor.source is None:
        raise ValueError(f"factor {factor.id} has no source to stand for an unverified value")
    return FactorValue(factor_id=factor.id, fit=Fit.UNVERIFIED, source=factor.source)


def _site(value: FactorValue) -> str:
    if value.fit is Fit.UNVERIFIED:
        return ""
    return f" ({wording.site_name(value.source.reference)})"
