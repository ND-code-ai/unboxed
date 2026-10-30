"""The pure functions the `interview` node calls: completing the answers, and uses per year."""

import pytest

from shopper.graph.interview import complete_answers, uses_per_year
from shopper.state import (
    Answer,
    AnswerStatus,
    Choice,
    DecisionFactor,
    FactorKind,
    Question,
    Source,
    SourceKind,
    StatedIn,
)

USAGE_QUESTION = Question(
    id="q-usage",
    factor_id="usage",
    text="How often will you use it?",
    reason="It sets the cost per use.",
    choices=(
        Choice(id="daily", text="Every day", uses_per_year=365),
        Choice(id="weekly", text="About once a week", uses_per_year=50),
    ),
)
HOB_QUESTION = Question(
    id="q-hob",
    factor_id="hob",
    text="Which hob do you cook on?",
    reason="Not every pan works on every hob.",
    choices=(Choice(id="gas", text="Gas"), Choice(id="induction", text="Induction")),
)
QUESTIONS = (USAGE_QUESTION, HOB_QUESTION)
WEEKLY = Answer(factor_id="usage", status=AnswerStatus.CHOSEN, choice_id="weekly")
INDUCTION = Answer(factor_id="hob", status=AnswerStatus.CHOSEN, choice_id="induction")
HOB_NOT_SURE = Answer(factor_id="hob", status=AnswerStatus.NOT_SURE)
SIZE_STATED = Answer(
    factor_id="size", status=AnswerStatus.STATED, stated_value="28 cm", stated_phrase="28 cm pan"
)


def test_every_question_gets_the_answer_the_caller_gave() -> None:
    assert complete_answers(QUESTIONS, (), (INDUCTION, WEEKLY)) == (WEEKLY, INDUCTION)


def test_a_not_sure_answer_is_kept_as_not_sure() -> None:
    assert complete_answers(QUESTIONS, (), (WEEKLY, HOB_NOT_SURE)) == (WEEKLY, HOB_NOT_SURE)


def test_a_question_with_no_answer_is_skipped() -> None:
    assert complete_answers(QUESTIONS, (), (WEEKLY,)) == (
        WEEKLY,
        Answer(factor_id="hob", status=AnswerStatus.SKIPPED),
    )


def test_skipping_all_is_no_answers_and_skips_every_question() -> None:
    assert complete_answers(QUESTIONS, (), ()) == (
        Answer(factor_id="usage", status=AnswerStatus.SKIPPED),
        Answer(factor_id="hob", status=AnswerStatus.SKIPPED),
    )


def test_the_stated_answers_are_kept_before_the_questions_answers() -> None:
    assert complete_answers(QUESTIONS, (SIZE_STATED,), (WEEKLY, INDUCTION)) == (
        SIZE_STATED,
        WEEKLY,
        INDUCTION,
    )


def test_no_questions_and_no_answers_is_the_stated_answers_alone() -> None:
    assert complete_answers((), (SIZE_STATED,), ()) == (SIZE_STATED,)


def test_nothing_asked_stated_or_given_is_no_answers() -> None:
    assert complete_answers((), (), ()) == ()


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ((Answer(factor_id="size", status=AnswerStatus.NOT_SURE),), "has no question"),
        (
            (Answer(factor_id="hob", status=AnswerStatus.CHOSEN, choice_id="weekly"),),
            "is not on question",
        ),
        ((INDUCTION, HOB_NOT_SURE), "same factor"),
        ((Answer(factor_id="hob", status=AnswerStatus.SKIPPED),), "chosen or not sure"),
        (
            (
                Answer(
                    factor_id="hob",
                    status=AnswerStatus.STATED,
                    stated_value="induction",
                    stated_phrase="for induction",
                ),
            ),
            "chosen or not sure",
        ),
        (
            (
                Answer(
                    factor_id="usage",
                    status=AnswerStatus.CHOSEN,
                    choice_id="weekly",
                    uses_per_year=9,
                ),
            ),
            "uses per year",
        ),
    ],
    ids=[
        "a factor with no question",
        "a choice that is not on its question",
        "two answers for one factor",
        "status skipped",
        "status stated",
        "its own uses per year",
    ],
)
def test_answers_the_caller_may_not_give_raise(given: tuple[Answer, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        complete_answers(QUESTIONS, (SIZE_STATED,), given)


# --- With the answers read in the reply ---

# Phrased in the brief and not asked: its answers are checked against these choices.
LID_QUESTION = Question(
    id="q-lid",
    factor_id="lid",
    text="Do you want a lid?",
    reason="A lid keeps the heat in.",
    choices=(Choice(id="with-lid", text="With a lid"), Choice(id="no-lid", text="No lid")),
)
PHRASED = (HOB_QUESTION, LID_QUESTION)


def from_reply(factor_id: str, value: str, *, choice_id: str | None = None) -> Answer:
    return Answer(
        factor_id=factor_id,
        status=AnswerStatus.STATED,
        choice_id=choice_id,
        stated_value=value,
        stated_phrase=f"phrase for {value}",
        stated_in=StatedIn.REPLY,
    )


REPLY_GAS = from_reply("hob", "Gas", choice_id="gas")
REPLY_HOB_NOT_SURE = Answer(
    factor_id="hob",
    status=AnswerStatus.NOT_SURE,
    stated_phrase="no idea which hob",
    stated_in=StatedIn.REPLY,
)
REPLY_LID = from_reply("lid", "With a lid", choice_id="with-lid")
REPLY_OWN = from_reply("user-2", "with a long handle")
SKIPPED_USAGE = Answer(factor_id="usage", status=AnswerStatus.SKIPPED)


def completed(given: tuple[Answer, ...], *reply: Answer) -> tuple[Answer, ...]:
    return complete_answers(QUESTIONS, (SIZE_STATED,), given, from_reply=reply, phrased=PHRASED)


@pytest.mark.parametrize(
    ("given", "reply", "counts"),
    [
        ((INDUCTION,), (REPLY_GAS,), INDUCTION),
        ((HOB_NOT_SURE,), (REPLY_GAS,), REPLY_GAS),
        ((HOB_NOT_SURE,), (REPLY_HOB_NOT_SURE,), REPLY_HOB_NOT_SURE),
        ((), (REPLY_GAS,), REPLY_GAS),
        ((HOB_NOT_SURE,), (), HOB_NOT_SURE),
        ((), (), Answer(factor_id="hob", status=AnswerStatus.SKIPPED)),
    ],
    ids=[
        "a chosen choice over the reply",
        "the reply over a not-sure picked",
        "the reply's not-sure over a not-sure picked",
        "the reply alone",
        "a not-sure picked alone",
        "nothing: skipped",
    ],
)
def test_the_strongest_answer_to_a_question_counts(
    given: tuple[Answer, ...], reply: tuple[Answer, ...], counts: Answer
) -> None:
    assert completed(given, *reply) == (SIZE_STATED, SKIPPED_USAGE, counts)


def test_the_request_counts_over_the_reply_for_a_factor_it_states() -> None:
    reply_size = from_reply("size", "24 cm")

    assert completed((), reply_size) == (
        SIZE_STATED,
        SKIPPED_USAGE,
        Answer(factor_id="hob", status=AnswerStatus.SKIPPED),
    )


def test_the_replys_answers_to_factors_not_asked_follow_the_stated_ones_in_the_order_read() -> None:
    assert completed((WEEKLY,), REPLY_OWN, REPLY_LID, REPLY_GAS) == (
        SIZE_STATED,
        REPLY_OWN,
        REPLY_LID,
        WEEKLY,
        REPLY_GAS,
    )


@pytest.mark.parametrize(
    ("given", "reply", "message"),
    [
        ((REPLY_HOB_NOT_SURE,), (), "never given by the caller"),
        ((), (INDUCTION,), "not read in the reply"),
        ((), (SIZE_STATED,), "not read in the reply"),
        (
            (),
            (REPLY_HOB_NOT_SURE.model_copy(update={"factor_id": "lid"}),),
            "not sure only to a question",
        ),
        ((), (from_reply("lid", "No lid", choice_id="gas"),), "is not on question"),
        ((), (from_reply("hob", "Gas", choice_id="with-lid"),), "is not on question"),
        ((), (from_reply("size", "24 cm", choice_id="gas"),), "has no question"),
        ((), (REPLY_GAS, REPLY_HOB_NOT_SURE), "same factor"),
    ],
    ids=[
        "a caller's answer from the reply",
        "a chosen answer as the reply's",
        "a request's answer as the reply's",
        "not sure about a factor not asked",
        "a choice of another phrased question",
        "a choice of another asked question",
        "a choice for a factor with no question",
        "two of the reply's answers for one factor",
    ],
)
def test_answers_read_in_the_reply_that_code_may_not_place_raise(
    given: tuple[Answer, ...], reply: tuple[Answer, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        completed(given, *reply)


# --- Uses per year ---

WEB = Source(kind=SourceKind.URL, reference="https://example.com/pans")
USAGE = DecisionFactor(id="usage", name="Usage", kind=FactorKind.USAGE, why="w")
HOB = DecisionFactor(id="hob", name="Hob", kind=FactorKind.COMPATIBILITY, why="w", source=WEB)
FACTORS = (USAGE, HOB)


def test_uses_per_year_is_copied_from_the_chosen_choice() -> None:
    assert uses_per_year(FACTORS, QUESTIONS, (WEEKLY, INDUCTION)) == 50


def test_a_stated_usage_answer_gives_the_uses_per_year_code_put_on_it() -> None:
    stated = Answer(
        factor_id="usage",
        status=AnswerStatus.STATED,
        stated_value="every day",
        stated_phrase="I cook every day",
        uses_per_year=365,
    )

    assert uses_per_year(FACTORS, (HOB_QUESTION,), (stated, INDUCTION)) == 365


@pytest.mark.parametrize(
    "answers",
    [
        (INDUCTION,),
        (Answer(factor_id="usage", status=AnswerStatus.NOT_SURE), INDUCTION),
        (Answer(factor_id="usage", status=AnswerStatus.SKIPPED), INDUCTION),
    ],
    ids=["no answer", "not sure", "skipped"],
)
def test_uses_per_year_is_missing_without_a_usage_answer(answers: tuple[Answer, ...]) -> None:
    assert uses_per_year(FACTORS, QUESTIONS, answers) is None


def test_uses_per_year_is_missing_without_a_usage_factor() -> None:
    assert uses_per_year((HOB,), (HOB_QUESTION,), (INDUCTION,)) is None
