"""What the request already states: one model call, and the checks on what it returns.

A requirement the request states becomes a `stated` answer, and its factor gets no question. The
checks take the words they read and say which they are, so the reply's reader (`reply.py`) uses
them too. Rules: docs/architecture/reading_answers.md ("Stated answers").
"""

from collections.abc import Mapping, Sequence

from shopper import wording
from shopper.agents.brief.checks import own_phrase_fault, stated_value_fault
from shopper.agents.brief.models import (
    OwnFactor,
    Said,
    Stated,
    StatedReading,
    StatedRequirement,
)
from shopper.agents.brief.prompt import (
    STATED_CHOICE,
    STATED_FACTOR,
    STATED_FREQUENCY,
    STATED_INPUT,
    STATED_NO_CHOICES,
    STATED_PROMPT,
    UNNAMED_CATEGORY,
)
from shopper.agents.brief.trail import by_model, entry, model_call_failed
from shopper.agents.brief.usage_frequency import USES_PER_YEAR
from shopper.agents.shared.phrases import find_phrase, plain
from shopper.config import Tier
from shopper.llm import ChatModel, Completion, LlmFailure, complete_structured
from shopper.state import (
    MAX_USER_FACTORS,
    Answer,
    AnswerStatus,
    Choice,
    DecisionFactor,
    FactorKind,
    Question,
    Request,
    Source,
    SourceKind,
    StatedIn,
    TrailEntry,
    TrailKind,
    Warning,
    WarningCode,
)

# Medium with little reasoning, not small: the small tier took 6 to 23 s reasoning in full and
# missed stated requirements without reasoning (docs/findings/task_1.7.2.md).
STATED_TIER: Tier = "medium"
STATED_LOW_EFFORT = True
# The user's own factors carry their own prefix, so their ids never collide with researched ones.
USER_FACTOR_ID = "user-{number}"
# Why a stated answer settles its factor, on the trail.
_STATED_REASONS = {
    StatedIn.REQUEST: "the request states it, so it is not asked",
    StatedIn.REPLY: "the reply states it",
}


async def read_stated(
    request: Request,
    factors: Sequence[DecisionFactor],
    questions: Sequence[Question],
    chat: ChatModel,
) -> Stated:
    """The answers the request states for these factors, at most one per factor.

    A timeout or a service error is tried once more; invalid output is already retried once by
    `complete_structured`. When the call fails twice, nothing is stated, every question is asked
    and a warning says so.
    """
    choices = choices_by_factor(questions)
    prompt = _stated_input(request, factors, choices)
    reply = await _read_requirements(prompt, chat)
    if isinstance(reply, LlmFailure) and reply.kind != "invalid_output":
        reply = await _read_requirements(prompt, chat)
    if isinstance(reply, LlmFailure):
        failed = model_call_failed("pick out the requirements in the request", reply)
        warning = Warning(
            code=WarningCode.STATED_ANSWERS_UNAVAILABLE,
            message=wording.stated_answers_unavailable(),
        )
        return Stated((), (failed,), (warning,))
    said = Said(request.original_text, StatedIn.REQUEST)
    return _kept(reply, said, request, factors, choices)


async def _read_requirements(
    prompt: str, chat: ChatModel
) -> Completion[StatedReading] | LlmFailure:
    return await complete_structured(
        chat, STATED_TIER, prompt, StatedReading, system=STATED_PROMPT, low_effort=STATED_LOW_EFFORT
    )


def choices_by_factor(questions: Sequence[Question]) -> dict[str, tuple[Choice, ...]]:
    return {question.factor_id: question.choices for question in questions}


def _kept(
    reply: Completion[StatedReading],
    said: Said,
    request: Request,
    factors: Sequence[DecisionFactor],
    choices: Mapping[str, Sequence[Choice]],
) -> Stated:
    """An answer per requirement that passes the checks, the first for a factor counting, a
    trail entry for each requirement, and a factor of the user's own for each that fits none."""
    answers: dict[str, Answer] = {}
    own: list[DecisionFactor] = []
    entries: list[TrailEntry] = []
    for requirement in reply.value.requirements:
        factor = numbered_factor(requirement, factors)
        if factor is None:
            made = own_factor(requirement, said, request, own)
            if isinstance(made, TrailEntry):
                entries.append(made)
            else:
                own.append(made.factor)
                answers[made.factor.id] = made.answer
                entries.append(own_entry(made.factor, said))
            continue
        outcome = stated_answer(requirement, factor, said, choices)
        if isinstance(outcome, TrailEntry):
            entries.append(outcome)
        elif outcome.factor_id in answers:
            entries.append(said_again(outcome, said))
        else:
            answers[outcome.factor_id] = outcome
            entries.append(stated_entry(outcome, factors, said))
    return Stated(
        tuple(answers.values()),
        tuple(by_model(each, reply) for each in entries),
        factors=tuple(own),
    )


def numbered_factor(
    requirement: StatedRequirement, factors: Sequence[DecisionFactor]
) -> DecisionFactor | None:
    """The factor the requirement names by its number; missing for "new" or a number not shown."""
    number = requirement.factor
    if isinstance(number, str) or not 1 <= number <= len(factors):
        return None
    return factors[number - 1]


def own_factor(
    requirement: StatedRequirement,
    said: Said,
    request: Request,
    kept: Sequence[DecisionFactor],
    *,
    local_term: str | None = None,
) -> OwnFactor | TrailEntry:
    """A factor of the user's own for a requirement that fits none, with the answer that settles
    it, or the trail entry that says why the requirement is not applied.

    `kept` holds the user's own factors so far, the request's before the reply's: the places and
    the numbering are shared. A refused requirement does not take one of the places; one past
    them goes to the trail.
    """
    located = located_phrase(requirement, said, is_usage=False)
    if isinstance(located, TrailEntry):
        return located
    span, phrase = located
    fault = own_phrase_fault(span, said, request, local_term) or _own_place_fault(phrase, kept)
    if fault is not None:
        return ignored(phrase, fault, said.stated_in, is_usage=False)
    factor = DecisionFactor(
        id=USER_FACTOR_ID.format(number=len(kept) + 1),
        name=phrase,
        kind=FactorKind.REQUIREMENT,
        why=wording.USER_FACTOR_WHY,
        source=Source(kind=SourceKind.USER, reference=phrase),
    )
    return OwnFactor(factor, _stated(factor, phrase, phrase, said))


def _own_place_fault(phrase: str, kept: Sequence[DecisionFactor]) -> str | None:
    """Why the user's own factor has no place among those kept; missing when it has one."""
    if plain(phrase) in {plain(factor.name) for factor in kept}:
        return "an earlier requirement says the same"
    if len(kept) >= MAX_USER_FACTORS:
        return f"at most {MAX_USER_FACTORS} requirements that fit no decision factor are kept"
    return None


def own_entry(factor: DecisionFactor, said: Said) -> TrailEntry:
    """The trail entry for a factor of the user's own."""
    summary = f'Stated in the {said.stated_in}: "{factor.name}" as a requirement of its own'
    reason = "it fits none of the decision factors"
    return entry(TrailKind.DECIDED, summary, reason=reason)


def stated_answer(
    requirement: StatedRequirement,
    factor: DecisionFactor,
    said: Said,
    choices: Mapping[str, Sequence[Choice]],
) -> Answer | TrailEntry:
    """The stated answer, or the trail entry that says why the requirement is not applied.

    A care factor takes one of its two choices, never a value of the model's own.
    """
    is_usage = factor.kind is FactorKind.USAGE
    located = located_phrase(requirement, said, is_usage=is_usage)
    if isinstance(located, TrailEntry):
        return located
    _, phrase = located
    if is_usage:
        return _usage(requirement.frequency, factor, phrase, said, choices.get(factor.id, ()))
    offered = choices.get(factor.id, ())
    number = requirement.choice
    if number is not None and 1 <= number <= len(offered):
        choice = offered[number - 1]
        return _stated(factor, choice.text, phrase, said, choice_id=choice.id)
    if factor.kind is FactorKind.CARE:
        return ignored(
            phrase, "a care factor takes one of its two choices", said.stated_in, is_usage=False
        )
    fault = stated_value_fault(requirement.value, phrase)
    if fault is not None:
        return ignored(phrase, fault, said.stated_in, is_usage=False)
    return _stated(factor, (requirement.value or "").strip(), phrase, said)


def located_phrase(
    requirement: StatedRequirement, said: Said, *, is_usage: bool
) -> tuple[tuple[int, int], str] | TrailEntry:
    """Where the requirement's phrase stands in what was said and its words there, or the trail
    entry that says it stands nowhere.

    A phrase not in the reply is not repeated: the model wrote it, not the user.
    """
    span = find_phrase(requirement.phrase, said.text)
    if span is not None:
        return span, said.text[span[0] : span[1]]
    reason = f"the phrase is not in the {said.stated_in}"
    if said.stated_in is StatedIn.REPLY:
        summary = f"Ignored a {_noun(is_usage)} whose phrase is not in the reply"
        return entry(TrailKind.EXCLUDED, summary, reason=reason)
    return ignored(requirement.phrase.strip(), reason, said.stated_in, is_usage=is_usage)


def _usage(
    frequency: str | None,
    factor: DecisionFactor,
    phrase: str,
    said: Said,
    offered: Sequence[Choice],
) -> Answer | TrailEntry:
    """A stated usage is one of the seven frequencies; code copies its uses per year. It takes
    the choice of the usage question that offers it, when one does."""
    if frequency not in USES_PER_YEAR:
        return ignored(
            phrase, "it names none of the usage frequencies", said.stated_in, is_usage=True
        )
    words = wording.USAGE_FREQUENCIES[frequency]
    choice_id = frequency if frequency in {choice.id for choice in offered} else None
    return _stated(
        factor, words, phrase, said, choice_id=choice_id, uses_per_year=USES_PER_YEAR[frequency]
    )


def _stated(
    factor: DecisionFactor,
    value: str,
    phrase: str,
    said: Said,
    *,
    choice_id: str | None = None,
    uses_per_year: int | None = None,
) -> Answer:
    return Answer(
        factor_id=factor.id,
        status=AnswerStatus.STATED,
        choice_id=choice_id,
        stated_value=value,
        stated_phrase=phrase,
        uses_per_year=uses_per_year,
        stated_in=said.stated_in,
    )


def ignored(phrase: str, reason: str, stated_in: StatedIn, *, is_usage: bool) -> TrailEntry:
    """The trail entry for a phrase of the request or the reply that is not applied."""
    summary = f'Ignored the {_noun(is_usage)} "{phrase}" in the {stated_in}'
    return entry(TrailKind.EXCLUDED, summary, reason=reason)


def said_again(answer: Answer, said: Said) -> TrailEntry:
    """The trail entry for a requirement about a factor an earlier one answered."""
    reason = "an earlier requirement is about the same factor"
    return ignored(answer.stated_phrase or "", reason, said.stated_in, is_usage=False)


def _noun(is_usage: bool) -> str:
    return "usage" if is_usage else "requirement"


def stated_entry(answer: Answer, factors: Sequence[DecisionFactor], said: Said) -> TrailEntry:
    (factor,) = (factor for factor in factors if factor.id == answer.factor_id)
    summary = (
        f'Stated in the {said.stated_in}: "{answer.stated_phrase}" as {factor.name}: '
        f"{answer.stated_value}"
    )
    return entry(TrailKind.DECIDED, summary, reason=_STATED_REASONS[said.stated_in])


def options_shown(factor: DecisionFactor, choices: Sequence[Choice]) -> str:
    """The factor's choices by number, or for usage every frequency by its id."""
    if factor.kind is FactorKind.USAGE:
        return "\n".join(
            STATED_FREQUENCY.format(frequency=frequency, words=wording.USAGE_FREQUENCIES[frequency])
            for frequency in USES_PER_YEAR
        )
    if not choices:
        return STATED_NO_CHOICES
    return "\n".join(
        STATED_CHOICE.format(number=number, text=choice.text)
        for number, choice in enumerate(choices, start=1)
    )


def _stated_input(
    request: Request,
    factors: Sequence[DecisionFactor],
    choices: Mapping[str, Sequence[Choice]],
) -> str:
    """What the call reads: the request, the category and each factor with its choices."""
    shown = "\n\n".join(
        STATED_FACTOR.format(
            number=number,
            name=factor.name,
            kind=factor.kind,
            options=options_shown(factor, choices.get(factor.id, ())),
        )
        for number, factor in enumerate(factors, start=1)
    )
    category = request.category or UNNAMED_CATEGORY
    return STATED_INPUT.format(text=request.original_text, category=category, factors=shown)
