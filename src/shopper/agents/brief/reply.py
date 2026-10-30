"""The reply's reader: what the user typed in answer to the questions, in their own words.

One model call before the graph resumes, never a node: the checks of the request's reading
(`stated.py`) on the reply's words, with each factor marked by what the session knows of it. A
reply never changes the request. Rules: docs/architecture/reading_answers.md ("The reply").
"""

from collections.abc import Mapping, Sequence
from enum import Enum, auto

from shopper.agents.brief.models import ReplyReading, ReplyRequirement, Said
from shopper.agents.brief.prompt import (
    REPLY_ANSWERED_BY_REQUEST,
    REPLY_ASKED,
    REPLY_FACTOR,
    REPLY_INPUT,
    REPLY_NOT_ASKED,
    REPLY_PROMPT,
    REPLY_QUESTION,
    REPLY_RECURRING_COST,
    UNNAMED_CATEGORY,
)
from shopper.agents.brief.stated import (
    STATED_LOW_EFFORT,
    STATED_TIER,
    choices_by_factor,
    ignored,
    located_phrase,
    numbered_factor,
    options_shown,
    own_entry,
    own_factor,
    said_again,
    stated_answer,
    stated_entry,
)
from shopper.agents.brief.trail import by_model, entry
from shopper.agents.bundle import ReplyOutput, ReplyUnreadError
from shopper.agents.shared.phrases import find_phrase
from shopper.llm import ChatModel, Completion, LlmFailure, complete_structured
from shopper.state import (
    Answer,
    AnswerStatus,
    Choice,
    DecisionFactor,
    FactorKind,
    Question,
    Request,
    SourceKind,
    StatedIn,
    TrailEntry,
    TrailKind,
)


class Mark(Enum):
    """What the session knows of a factor, as the reading is shown it."""

    ASKED = auto()
    NOT_ASKED = auto()
    ANSWERED_BY_REQUEST = auto()
    RECURRING_COST = auto()


_MARK_WORDS = {
    Mark.ASKED: REPLY_ASKED,
    Mark.NOT_ASKED: REPLY_NOT_ASKED,
    Mark.ANSWERED_BY_REQUEST: REPLY_ANSWERED_BY_REQUEST,
    Mark.RECURRING_COST: REPLY_RECURRING_COST,
}
# The marks of the factors a reply never answers: what it says of them goes to the trail.
_NOT_ANSWERED = {
    Mark.ANSWERED_BY_REQUEST: "the request already answers it",
    Mark.RECURRING_COST: "a recurring cost is not asked about",
}


async def read_reply(
    request: Request,
    reply: str,
    factors: Sequence[DecisionFactor],
    questions: Sequence[Question],
    phrased: Sequence[Question],
    stated: Sequence[Answer],
    local_term: str | None,
    chat: ChatModel,
) -> ReplyOutput:
    """What the reply says about these factors, at most one answer per factor, and the factors
    of the user's own it adds, numbered on from the request's.

    The same call as the request's reading: a timeout or a service error is tried once more, and
    invalid output is already retried once by `complete_structured`. Raises ReplyUnreadError
    when the call fails twice.
    """
    marks = _marks(factors, questions, stated)
    known = {question.factor_id: question for question in (*phrased, *questions)}
    prompt = _reply_input(reply, request, factors, marks, known)
    reading = await _read(prompt, chat)
    if isinstance(reading, LlmFailure) and reading.kind != "invalid_output":
        reading = await _read(prompt, chat)
    if isinstance(reading, LlmFailure):
        raise ReplyUnreadError(f"the model call failed ({reading.kind})")
    said = Said(reply, StatedIn.REPLY)
    choices = choices_by_factor(tuple(known.values()))
    return _kept(reading, said, request, factors, marks, choices, local_term)


async def _read(prompt: str, chat: ChatModel) -> Completion[ReplyReading] | LlmFailure:
    return await complete_structured(
        chat, STATED_TIER, prompt, ReplyReading, system=REPLY_PROMPT, low_effort=STATED_LOW_EFFORT
    )


def _marks(
    factors: Sequence[DecisionFactor], questions: Sequence[Question], stated: Sequence[Answer]
) -> dict[str, Mark]:
    asked = {question.factor_id for question in questions}
    settled = {answer.factor_id for answer in stated}
    return {factor.id: _mark(factor, asked, settled) for factor in factors}


def _mark(factor: DecisionFactor, asked: set[str], settled: set[str]) -> Mark:
    if factor.id in settled:
        return Mark.ANSWERED_BY_REQUEST
    if factor.kind is FactorKind.RECURRING_COST:
        return Mark.RECURRING_COST
    return Mark.ASKED if factor.id in asked else Mark.NOT_ASKED


def _kept(
    reading: Completion[ReplyReading],
    said: Said,
    request: Request,
    factors: Sequence[DecisionFactor],
    marks: Mapping[str, Mark],
    choices: Mapping[str, Sequence[Choice]],
    local_term: str | None,
) -> ReplyOutput:
    """An answer per thing the reply says that passes the checks, the first for a factor
    counting, a trail entry for each, and a factor of the user's own for each that fits none."""
    earlier = tuple(factor for factor in factors if _is_own(factor))
    added: list[DecisionFactor] = []
    own_answers: list[Answer] = []
    answers: dict[str, Answer] = {}
    entries: list[TrailEntry] = []
    for requirement in reading.value.requirements:
        factor = numbered_factor(requirement, factors)
        if _is_new(requirement, factor):
            made = own_factor(requirement, said, request, (*earlier, *added), local_term=local_term)
            if isinstance(made, TrailEntry):
                entries.append(made)
            else:
                added.append(made.factor)
                own_answers.append(made.answer)
                entries.append(own_entry(made.factor, said))
            continue
        outcome = _answer(requirement, factor, marks, said, choices)
        if isinstance(outcome, TrailEntry):
            entries.append(outcome)
        elif outcome.factor_id in answers:
            entries.append(said_again(outcome, said))
        else:
            answers[outcome.factor_id] = outcome
            entries.append(_answered_entry(outcome, factors, said))
    requirements = reading.value.requirements
    return ReplyOutput(
        answers=(*own_answers, *answers.values()),
        factors=tuple(added),
        answered_by_the_request=_spoke_to_the_request(requirements, said, factors, marks),
        asks_to_change_request=any(_asks_to_change(each, said) for each in requirements),
        trail=tuple(by_model(each, reading) for each in entries),
    )


def _is_own(factor: DecisionFactor) -> bool:
    return factor.source is not None and factor.source.kind is SourceKind.USER


def _is_new(requirement: ReplyRequirement, factor: DecisionFactor | None) -> bool:
    """Whether the requirement is a factor of the user's own: about no factor, and neither a
    change to the request nor a "not sure"."""
    return factor is None and requirement.changes is None and not requirement.not_sure


def _answer(
    requirement: ReplyRequirement,
    factor: DecisionFactor | None,
    marks: Mapping[str, Mark],
    said: Said,
    choices: Mapping[str, Sequence[Choice]],
) -> Answer | TrailEntry:
    """The reply's answer for the factor, or the trail entry that says why there is none."""
    if requirement.changes is not None:
        reason = f"it asks to change the {requirement.changes}, which a reply cannot"
        return _refused(requirement, said, reason)
    # With no factor, the requirement is a "not sure" about nothing asked.
    mark = None if factor is None else marks[factor.id]
    if mark in _NOT_ANSWERED:
        return _refused(requirement, said, _NOT_ANSWERED[mark])
    if factor is not None and not requirement.not_sure:
        return stated_answer(requirement, factor, said, choices)
    if factor is None or mark is not Mark.ASKED:
        return _refused(requirement, said, "only a question asked is answered not sure")
    located = located_phrase(requirement, said, is_usage=factor.kind is FactorKind.USAGE)
    if isinstance(located, TrailEntry):
        return located
    return Answer(
        factor_id=factor.id,
        status=AnswerStatus.NOT_SURE,
        stated_phrase=located[1],
        stated_in=StatedIn.REPLY,
    )


def _refused(requirement: ReplyRequirement, said: Said, reason: str) -> TrailEntry:
    located = located_phrase(requirement, said, is_usage=False)
    if isinstance(located, TrailEntry):
        return located
    return ignored(located[1], reason, said.stated_in, is_usage=False)


def _answered_entry(answer: Answer, factors: Sequence[DecisionFactor], said: Said) -> TrailEntry:
    if answer.status is not AnswerStatus.NOT_SURE:
        return stated_entry(answer, factors, said)
    (factor,) = (factor for factor in factors if factor.id == answer.factor_id)
    summary = f'Read in the reply: "{answer.stated_phrase}" as {factor.name}: not sure'
    return entry(TrailKind.DECIDED, summary, reason="the reply says it is not known")


def _spoke_to_the_request(
    requirements: Sequence[ReplyRequirement],
    said: Said,
    factors: Sequence[DecisionFactor],
    marks: Mapping[str, Mark],
) -> bool:
    """Whether a phrase that stands in the reply was about a factor the request answers."""
    return any(
        requirement.changes is None
        and factor is not None
        and marks[factor.id] is Mark.ANSWERED_BY_REQUEST
        and find_phrase(requirement.phrase, said.text) is not None
        for requirement in requirements
        for factor in (numbered_factor(requirement, factors),)
    )


def _asks_to_change(requirement: ReplyRequirement, said: Said) -> bool:
    """Whether a phrase that stands in the reply asks to change the request."""
    return (
        requirement.changes is not None and find_phrase(requirement.phrase, said.text) is not None
    )


def _reply_input(
    reply: str,
    request: Request,
    factors: Sequence[DecisionFactor],
    marks: Mapping[str, Mark],
    known: Mapping[str, Question],
) -> str:
    """What the call reads: the reply, the category and each factor marked, with its question
    and choices when a reply may answer it."""
    shown = "\n\n".join(
        REPLY_FACTOR.format(
            number=number,
            name=factor.name,
            kind=factor.kind,
            mark=_MARK_WORDS[marks[factor.id]],
            options=_options(factor, marks[factor.id], known.get(factor.id)),
        )
        for number, factor in enumerate(factors, start=1)
    )
    category = request.category or UNNAMED_CATEGORY
    return REPLY_INPUT.format(reply=reply, category=category, factors=shown)


def _options(factor: DecisionFactor, mark: Mark, question: Question | None) -> str:
    """The lines under a factor: none for one a reply never answers, else its question when it
    has one, and its choices."""
    if mark in _NOT_ANSWERED:
        return ""
    asked = () if question is None else (REPLY_QUESTION.format(text=question.text),)
    choices = () if question is None else question.choices
    return "".join(f"\n{line}" for line in (*asked, options_shown(factor, choices)))
