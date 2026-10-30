"""What the `interview` node does with the user's answers, as pure functions.

Rules: docs/architecture/sessions.md ("The pause") and docs/architecture/interview.md.
"""

from collections.abc import Mapping, Sequence

from shopper.agents.brief.stated import ignored
from shopper.agents.brief.trail import entry
from shopper.agents.bundle import ReplyOutput
from shopper.state import (
    Answer,
    AnswerStatus,
    DecisionFactor,
    FactorKind,
    InterviewAnswers,
    Question,
    StatedIn,
    TrailEntry,
    TrailKind,
)

STATUSES_A_CALLER_GIVES = frozenset({AnswerStatus.CHOSEN, AnswerStatus.NOT_SURE})


def with_reply(
    questions: Sequence[Question],
    stated: Sequence[Answer],
    given: Sequence[Answer],
    reply: ReplyOutput,
    phrased: Sequence[Question],
) -> InterviewAnswers:
    """What the interview resumes with once the reply was read.

    The reply's answers that lose to a choice picked or to the request go to the trail. When
    none of them counts and it adds no factor, one entry says whether it answered nothing, or
    only what was answered already. Raises ValueError as `complete_answers` does.
    """
    kept = kept_from_reply(questions, stated, given, reply, phrased)
    lost = tuple(answer for answer in reply.answers if answer not in kept)
    settled = {answer.factor_id for answer in stated}
    changed_nothing = not kept and not reply.factors
    return InterviewAnswers(
        given=tuple(given),
        from_reply=reply.answers,
        factors=reply.factors,
        trail=(
            *reply.trail,
            *(_lost(answer, settled) for answer in lost),
            *((_changed_nothing(answered_already(reply, kept)),) if changed_nothing else ()),
        ),
    )


def kept_from_reply(
    questions: Sequence[Question],
    stated: Sequence[Answer],
    given: Sequence[Answer],
    reply: ReplyOutput,
    phrased: Sequence[Question],
) -> tuple[Answer, ...]:
    """The reply's answers that count beside the choices picked and the request's answers.
    Raises ValueError as `complete_answers` does."""
    completed = complete_answers(
        questions, stated, given, from_reply=reply.answers, phrased=phrased
    )
    return tuple(answer for answer in reply.answers if answer in completed)


def answered_already(reply: ReplyOutput, kept: Sequence[Answer]) -> bool:
    """Whether the reply changed no answer only because a choice picked or the request already
    answers all it answers, rather than because it answered nothing."""
    spoke_to_an_answer = bool(reply.answers) or reply.answered_by_the_request
    return spoke_to_an_answer and not kept and not reply.factors


def _lost(answer: Answer, settled: set[str]) -> TrailEntry:
    by_request = answer.factor_id in settled
    reason = "the request already answers it" if by_request else "a choice picked answers it"
    return ignored(answer.stated_phrase or "", reason, StatedIn.REPLY, is_usage=False)


def _changed_nothing(already: bool) -> TrailEntry:
    reason = (
        "a choice picked or the request answers all it answers"
        if already
        else "nothing in it answers a factor"
    )
    return entry(TrailKind.DECIDED, "The reply changed no answer", reason=reason)


def every_question(
    questions: Sequence[Question], phrased: Sequence[Question]
) -> tuple[Question, ...]:
    """Every question phrased, asked or not, then those asked that were not phrased in category
    research: the usage question."""
    return tuple(_known(questions, phrased).values())


def _known(questions: Sequence[Question], phrased: Sequence[Question]) -> dict[str, Question]:
    """Every question by its factor, in the order of `every_question`; the question asked stands
    for its factor."""
    return {**_by_factor(phrased), **_by_factor(questions)}


def with_own_factors(
    factors: Sequence[DecisionFactor], added: Sequence[DecisionFactor]
) -> tuple[DecisionFactor, ...]:
    """The factors with the user's own from the reply added before the usage factor: the
    researched, the request's own, the reply's own, then usage."""
    usage = tuple(factor for factor in factors if factor.kind is FactorKind.USAGE)
    others = tuple(factor for factor in factors if factor.kind is not FactorKind.USAGE)
    return (*others, *added, *usage)


def complete_answers(
    questions: Sequence[Question],
    stated: Sequence[Answer],
    given: Sequence[Answer],
    *,
    from_reply: Sequence[Answer] = (),
    phrased: Sequence[Question] = (),
) -> tuple[Answer, ...]:
    """The answers that count, at most one per factor: the stated answers, the reply's answers to
    factors not asked in the order read, then one answer per question.

    For a factor the request states, its answer counts. For a question, a chosen answer counts,
    then the reply's, then a "not sure" picked; with none it is skipped. `phrased` holds every
    question the brief phrased, asked or not: a choice the reply was read to name is checked
    against its factor's.

    Raises ValueError for answers the caller may not give, and for answers of the reply that code
    never reads: both are programming errors, because the caller asks the user again first.
    """
    asked = _by_factor(questions)
    for answer in given:
        _check(answer, asked.get(answer.factor_id))
    for answer in from_reply:
        _check_read(answer, asked, _known(questions, phrased))
    given_by_factor = _one_each(given)
    read_by_factor = _one_each(from_reply)
    settled = {answer.factor_id for answer in stated}
    not_asked = (
        answer
        for answer in from_reply
        if answer.factor_id not in asked and answer.factor_id not in settled
    )
    return (
        *stated,
        *not_asked,
        *(
            _strongest(
                question.factor_id,
                given_by_factor.get(question.factor_id),
                read_by_factor.get(question.factor_id),
            )
            for question in questions
        ),
    )


def uses_per_year(
    factors: Sequence[DecisionFactor],
    questions: Sequence[Question],
    answers: Sequence[Answer],
) -> int | None:
    """Uses per year from the answer to the usage factor; missing when it is not answered.

    A chosen answer takes it from its choice; a stated answer carries it, put there by code.
    """
    usage_ids = {factor.id for factor in factors if factor.kind is FactorKind.USAGE}
    answer = next((answer for answer in answers if answer.factor_id in usage_ids), None)
    if answer is None:
        return None
    if answer.status is AnswerStatus.STATED:
        return answer.uses_per_year
    choices = (
        choice
        for question in questions
        if question.factor_id == answer.factor_id
        for choice in question.choices
    )
    return next((c.uses_per_year for c in choices if c.id == answer.choice_id), None)


def _strongest(factor_id: str, chosen: Answer | None, read: Answer | None) -> Answer:
    """The answer that counts for a question: a chosen one, the reply's, a "not sure" picked."""
    if chosen is not None and chosen.status is AnswerStatus.CHOSEN:
        return chosen
    return read or chosen or Answer(factor_id=factor_id, status=AnswerStatus.SKIPPED)


def _one_each(answers: Sequence[Answer]) -> dict[str, Answer]:
    """The answers by factor; raises when two are for the same factor."""
    by_factor = {answer.factor_id: answer for answer in answers}
    if len(by_factor) != len(answers):
        raise ValueError("two answers are for the same factor")
    return by_factor


def _by_factor(questions: Sequence[Question]) -> dict[str, Question]:
    return {question.factor_id: question for question in questions}


def _check(answer: Answer, question: Question | None) -> None:
    """Raise unless the answer is one a caller may give to this question."""
    if question is None:
        raise ValueError(f"factor {answer.factor_id!r} has no question")
    if answer.status not in STATUSES_A_CALLER_GIVES:
        raise ValueError(f"an answer is chosen or not sure, not {answer.status}")
    if answer.stated_in is StatedIn.REPLY:
        raise ValueError("an answer from the reply is never given by the caller")
    if answer.uses_per_year is not None:
        raise ValueError("uses per year comes from the chosen choice, not from the caller")
    _check_choice(answer, question)


def _check_read(
    answer: Answer, asked: Mapping[str, Question], questions: Mapping[str, Question]
) -> None:
    """Raise unless code could have read the answer in the reply: stated, or "not sure" to a
    question asked, with a choice only from its factor's question."""
    if answer.stated_in is not StatedIn.REPLY:
        raise ValueError(f"an answer for factor {answer.factor_id!r} is not read in the reply")
    if answer.status is AnswerStatus.NOT_SURE and answer.factor_id not in asked:
        raise ValueError("the reply answers not sure only to a question asked")
    if answer.choice_id is None:
        return
    question = questions.get(answer.factor_id)
    if question is None:
        raise ValueError(f"factor {answer.factor_id!r} has no question")
    _check_choice(answer, question)


def _check_choice(answer: Answer, question: Question) -> None:
    if answer.choice_id is not None and answer.choice_id not in {c.id for c in question.choices}:
        raise ValueError(f"choice {answer.choice_id!r} is not on question {question.id!r}")
