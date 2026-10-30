"""The pure functions `assemble_report` calls: the caveats and the check-before-you-buy list."""

import pytest

from samples import seen_price
from shopper.graph.report import caveats_for, check_before_you_buy
from shopper.state import (
    Answer,
    AnswerStatus,
    Caveat,
    CaveatCode,
    CheckItem,
    CheckReason,
    DecisionFactor,
    FactorKind,
    FactorValue,
    Fit,
    ProductOption,
    Scope,
    Source,
    SourceKind,
)


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (Scope.TUNED, ()),
        (Scope.GENERAL, (Caveat(code=CaveatCode.NOT_TUNED),)),
        (Scope.ENERGY_HEAVY, (Caveat(code=CaveatCode.ENERGY_HEAVY),)),
        (Scope.CLOTHING, (Caveat(code=CaveatCode.CLOTHING),)),
        (Scope.NOT_A_PRODUCT, ()),
        (Scope.SEVERAL_PRODUCTS, ()),
        (Scope.UNCLEAR, ()),
    ],
)
def test_each_scope_has_its_caveat(scope: Scope, expected: tuple[Caveat, ...]) -> None:
    assert caveats_for(scope) == expected


WEB = Source(kind=SourceKind.URL, reference="https://example.com/pans")
ESTIMATE = Source(kind=SourceKind.MODEL_ESTIMATE, reference="test")
USAGE = DecisionFactor(id="usage", name="Usage", kind=FactorKind.USAGE, why="w")
HOB = DecisionFactor(id="hob", name="Hob", kind=FactorKind.COMPATIBILITY, why="w", source=WEB)


def pan(option_id: str, hob_fit: Fit) -> ProductOption:
    value = None if hob_fit is Fit.UNVERIFIED else "induction"
    hob = FactorValue(factor_id="hob", value=value, fit=hob_fit, source=ESTIMATE)
    return ProductOption(id=option_id, name=option_id, factor_values=(hob,))


def test_a_factor_answered_not_sure_is_one_unanswered_item() -> None:
    answers = (Answer(factor_id="hob", status=AnswerStatus.NOT_SURE),)
    options = (pan("a", Fit.UNVERIFIED), pan("b", Fit.UNVERIFIED))

    items = check_before_you_buy((USAGE, HOB), answers, options)

    assert items == (CheckItem(factor_id="hob", reason=CheckReason.UNANSWERED),)


@pytest.mark.parametrize(
    "answers",
    [(), (Answer(factor_id="hob", status=AnswerStatus.SKIPPED),)],
    ids=["no answer", "skipped"],
)
def test_a_factor_without_an_answer_or_skipped_is_unanswered(answers: tuple[Answer, ...]) -> None:
    items = check_before_you_buy((HOB,), answers, (pan("a", Fit.UNVERIFIED),))

    assert items == (CheckItem(factor_id="hob", reason=CheckReason.UNANSWERED),)


def test_a_chosen_answer_leaves_one_unverified_item_per_unverified_option() -> None:
    answers = (Answer(factor_id="hob", status=AnswerStatus.CHOSEN, choice_id="induction"),)
    options = (pan("a", Fit.UNVERIFIED), pan("b", Fit.MEETS), pan("c", Fit.UNVERIFIED))

    items = check_before_you_buy((USAGE, HOB), answers, options)

    assert items == (
        CheckItem(factor_id="hob", option_id="a", reason=CheckReason.UNVERIFIED),
        CheckItem(factor_id="hob", option_id="c", reason=CheckReason.UNVERIFIED),
    )


def test_a_stated_answer_that_every_option_meets_leaves_no_item() -> None:
    stated = Answer(
        factor_id="hob",
        status=AnswerStatus.STATED,
        stated_value="induction",
        stated_phrase="for induction",
    )

    items = check_before_you_buy((HOB,), (stated,), (pan("a", Fit.MEETS), pan("b", Fit.MEETS)))

    assert items == ()


def test_each_option_with_a_price_has_its_price_to_confirm_after_the_factors() -> None:
    priced = ProductOption(id="b", name="b", **seen_price("40"))

    items = check_before_you_buy((HOB,), (), (pan("a", Fit.MEETS), priced))

    assert items == (
        CheckItem(factor_id="hob", reason=CheckReason.UNANSWERED),
        CheckItem(option_id="b", reason=CheckReason.PRICE),
    )


def test_an_option_with_no_price_has_no_price_to_confirm() -> None:
    unpriced = ProductOption(id="b", name="b")
    priced = ProductOption(id="c", name="c", **seen_price("30"))

    items = check_before_you_buy((), (), (unpriced, priced))

    assert items == (CheckItem(option_id="c", reason=CheckReason.PRICE),)


@pytest.mark.parametrize(
    "answers",
    [
        (),
        (Answer(factor_id="usage", status=AnswerStatus.NOT_SURE),),
        (Answer(factor_id="usage", status=AnswerStatus.SKIPPED),),
    ],
    ids=["no answer", "not sure", "skipped"],
)
def test_usage_frequency_is_never_on_the_list(answers: tuple[Answer, ...]) -> None:
    assert check_before_you_buy((USAGE,), answers, (pan("a", Fit.UNVERIFIED),)) == ()
