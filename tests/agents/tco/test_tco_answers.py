"""Step 6 of option research, answers: the evidence read judges each answered factor, and code
keeps a `meets` or a `fails` only on a quote from a passage that names the product
(option_evidence.md, "Evidence", "Answers")."""

from collections.abc import Mapping, Sequence
from pathlib import Path

from tco_replies import PAN, PAN_SHOP, Ran, Shop, page_url, pan_shop, reading, run, warnings

from pages import offer, product_page
from shopper import wording
from shopper.llm import ChatError
from shopper.state import (
    Answer,
    AnswerStatus,
    Choice,
    DecisionFactor,
    FactorKind,
    FactorValue,
    Fit,
    ProductOption,
    Question,
    Source,
    SourceKind,
    StatedBy,
    TrailKind,
    WarningCode,
)

TESTS = "https://www.example-tests.org/alpha-cheapo-review"
REVIEW = {
    "url": TESTS,
    "title": "Alpha Cheapo frying pan review",
    "content": (
        "We tested the Alpha Cheapo for a year.\n"
        "The Alpha Cheapo works on induction hobs.\n"
        "Hand wash only to keep the coating.\n"
        "Our cheapest pick has a glass lid."
    ),
}
HOB = DecisionFactor(
    id="researched-1",
    name="Hob compatibility",
    kind=FactorKind.COMPATIBILITY,
    why="Not every pan works on induction.",
    source=Source(kind=SourceKind.URL, reference="https://www.example-guide.org/hobs"),
)
HOB_QUESTION = Question(
    id="question-researched-1",
    factor_id=HOB.id,
    text="Which hob do you cook on?",
    reason="Not every pan works on induction.",
    choices=(Choice(id="choice-1", text="Gas"), Choice(id="choice-2", text="Induction")),
)
INDUCTION = Answer(factor_id=HOB.id, status=AnswerStatus.CHOSEN, choice_id="choice-2")


def fit(
    factor: int,
    judged: str,
    value: str | None = None,
    quote: str | None = None,
    result: int | None = 1,
    by: str = "tester",
) -> dict[str, object]:
    settled = judged != "unverified"
    return {
        "factor": factor,
        "fit": judged,
        "value": value if settled else None,
        "result": result if settled else None,
        "quote": quote if settled else None,
        "stated_by": by if settled else None,
    }


def answered(
    tmp_path: Path,
    *fits: Mapping[str, object],
    factors: Sequence[DecisionFactor] = (HOB,),
    questions: Sequence[Question] = (HOB_QUESTION,),
    answers: Sequence[Answer] = (INDUCTION,),
    found: Sequence[Mapping[str, str]] = (REVIEW,),
) -> Ran:
    """Two pans with these answers; the Alpha Cheapo's read judges them with `fits`."""
    return run(
        tmp_path,
        factors=factors,
        questions=questions,
        answers=answers,
        evidence={"Alpha Cheapo": found},
        evidence_reads={"Alpha Cheapo": reading(fits=list(fits))},
    )


def option(ran: Ran, name: str) -> ProductOption:
    return next(each for each in ran.output.options if each.name == name)


def evidence_input(ran: Ran, name: str) -> str:
    return next(
        request.messages[-1]["content"]
        for request in ran.requests
        if f"Product: {name}\n" in request.messages[-1]["content"]
        and "Look for consumables" in request.messages[-1]["content"]
    )


def test_an_answer_met_by_a_quote_that_names_the_product_gives_its_value_and_source(
    tmp_path: Path,
) -> None:
    ran = answered(
        tmp_path, fit(1, "meets", "works on induction", "The Alpha Cheapo works on induction")
    )

    assert "[1] Hob compatibility" in evidence_input(ran, "Alpha Cheapo")
    assert option(ran, "Alpha Cheapo").factor_values == (
        FactorValue(
            factor_id=HOB.id,
            value="works on induction",
            fit=Fit.MEETS,
            source=Source(kind=SourceKind.URL, reference=TESTS, stated_by=StatedBy.TESTER),
        ),
    )


def excluded(ran: Ran) -> dict[str, str | None]:
    return {
        entry.summary: entry.reason
        for entry in ran.output.trail
        if entry.kind is TrailKind.EXCLUDED
    }


def fit_entry(ran: Ran, name: str) -> tuple[str, str | None]:
    return next(
        (entry.summary, entry.reason)
        for entry in ran.output.trail
        if entry.summary.startswith(f'Fit of "{name}"')
    )


NOT_INDUCTION = {
    **REVIEW,
    "content": REVIEW["content"] + "\nThe Alpha Cheapo is not suitable for induction.",
}
ALPHA_FAILS = fit(1, "fails", "not for induction", "The Alpha Cheapo is not suitable for induction")


def test_an_option_that_fails_an_answer_is_removed_with_the_quote_and_its_site(
    tmp_path: Path,
) -> None:
    ran = answered(tmp_path, ALPHA_FAILS, found=(NOT_INDUCTION,))

    assert [each.name for each in ran.output.options] == ["Beta Steelo"]
    assert excluded(ran)['Left out "Alpha Cheapo"'] == (
        'it does not meet your answer about Hob compatibility: "The Alpha Cheapo is not suitable '
        'for induction" (example-tests.org)'
    )
    assert warnings(ran.output) == [(WarningCode.ONE_OPTION_ONLY, wording.one_option_only())]


def test_when_every_option_fails_an_answer_none_met_the_answers(tmp_path: Path) -> None:
    beta_page = {
        "url": "https://www.example-tests.org/beta",
        "title": "Beta Steelo",
        "content": "The Beta Steelo does not work on induction.",
    }
    beta_fails = fit(1, "fails", "no induction", "The Beta Steelo does not work on induction")
    ran = run(
        tmp_path,
        factors=(HOB,),
        questions=(HOB_QUESTION,),
        answers=(INDUCTION,),
        evidence={"Alpha Cheapo": (NOT_INDUCTION,), "Beta Steelo": (beta_page,)},
        evidence_reads={
            "Alpha Cheapo": reading(fits=[ALPHA_FAILS]),
            "Beta Steelo": reading(fits=[beta_fails]),
        },
    )

    assert ran.output.options == ()
    assert warnings(ran.output) == [
        (
            WarningCode.NO_OPTIONS_FOUND,
            wording.no_options_found("none_met_the_answers", "frying pan", 2),
        )
    ]


def test_a_quote_whose_passage_does_not_name_the_product_leaves_the_answer_unverified(
    tmp_path: Path,
) -> None:
    guide = {
        "url": "https://www.shop.example.nl/buying-guide",
        "title": "Pan buying guide",
        "content": "The Alpha Cheapo is our cheapest pan.\nThe Gamma pan is not for induction.",
    }
    ran = answered(
        tmp_path, fit(1, "fails", "not for induction", "is not for induction"), found=(guide,)
    )

    assert option(ran, "Alpha Cheapo").factor_values == (
        FactorValue(factor_id=HOB.id, fit=Fit.UNVERIFIED, source=HOB.source),
    )
    assert fit_entry(ran, "Alpha Cheapo") == (
        'Fit of "Alpha Cheapo" with your answers: Hob compatibility: unverified',
        "Hob compatibility: the passage of its quote does not name the product",
    )


def test_a_quote_that_is_not_in_the_result_leaves_the_answer_unverified(tmp_path: Path) -> None:
    ran = answered(tmp_path, fit(1, "meets", "induction", "The Alpha Cheapo loves induction"))

    assert option(ran, "Alpha Cheapo").factor_values[0].fit is Fit.UNVERIFIED
    assert fit_entry(ran, "Alpha Cheapo")[1] == (
        "Hob compatibility: its quote is not in the search result"
    )


def test_a_factor_the_read_leaves_out_is_unverified(tmp_path: Path) -> None:
    ran = answered(tmp_path)

    assert option(ran, "Alpha Cheapo").factor_values[0].fit is Fit.UNVERIFIED
    assert option(ran, "Beta Steelo").factor_values[0].fit is Fit.UNVERIFIED


CARE = DecisionFactor(
    id="researched-2",
    name="Hand washing",
    kind=FactorKind.CARE,
    why="The coating lasts longer with hand washing.",
    source=Source(kind=SourceKind.URL, reference="https://www.example-guide.org/care"),
)
CARE_QUESTION = Question(
    id="question-researched-2",
    factor_id=CARE.id,
    text="Non-stick pans last longer when washed by hand. Is that fine with you?",
    reason=CARE.why,
    choices=(
        Choice(id="care-fine", text="That's fine"),
        Choice(id="care-avoid", text="I'd rather avoid it"),
    ),
)


def care_answer(choice: str) -> Answer:
    return Answer(factor_id=CARE.id, status=AnswerStatus.CHOSEN, choice_id=choice)


def test_a_care_factor_declined_and_needed_marks_the_option_and_removes_nothing(
    tmp_path: Path,
) -> None:
    ran = answered(
        tmp_path,
        fit(1, "fails", "hand wash only", "the Alpha Cheapo for a year...Hand wash only"),
        factors=(CARE,),
        questions=(CARE_QUESTION,),
        answers=(care_answer("care-avoid"),),
    )

    assert "Care: Non-stick pans last longer when washed by hand." in evidence_input(
        ran, "Alpha Cheapo"
    )
    (value,) = option(ran, "Alpha Cheapo").factor_values
    assert (value.fit, value.value) == (Fit.FAILS, "hand wash only")
    assert 'Left out "Alpha Cheapo"' not in excluded(ran)


def test_a_care_factor_the_request_declines_is_judged_on_its_phrased_question(
    tmp_path: Path,
) -> None:
    # The request settled it, so its question was not asked; the graph passes it all the same.
    declined = Answer(
        factor_id=CARE.id,
        status=AnswerStatus.STATED,
        choice_id="care-avoid",
        stated_value="I'd rather avoid it",
        stated_phrase="no hand washing",
    )

    ran = answered(
        tmp_path,
        fit(1, "fails", "hand wash only", "the Alpha Cheapo for a year...Hand wash only"),
        factors=(CARE,),
        questions=(CARE_QUESTION,),
        answers=(declined,),
    )

    assert "Care: Non-stick pans last longer when washed by hand." in evidence_input(
        ran, "Alpha Cheapo"
    )
    (value,) = option(ran, "Alpha Cheapo").factor_values
    assert value.fit is Fit.FAILS


def test_a_care_factor_that_is_fine_gets_no_value(tmp_path: Path) -> None:
    ran = answered(
        tmp_path, factors=(CARE,), questions=(CARE_QUESTION,), answers=(care_answer("care-fine"),)
    )

    assert "Answered factors:\nNone." in evidence_input(ran, "Alpha Cheapo")
    assert option(ran, "Alpha Cheapo").factor_values == ()


def test_a_factor_answered_not_sure_gets_no_value(tmp_path: Path) -> None:
    ran = answered(tmp_path, answers=(Answer(factor_id=HOB.id, status=AnswerStatus.NOT_SURE),))

    assert option(ran, "Alpha Cheapo").factor_values == ()


def test_a_factor_of_the_users_own_is_judged_on_the_users_phrase(tmp_path: Path) -> None:
    lid = DecisionFactor(
        id="user-1",
        name="with a glass lid",
        kind=FactorKind.REQUIREMENT,
        why="You asked for this.",
        source=Source(kind=SourceKind.USER, reference="with a glass lid"),
    )
    stated = Answer(
        factor_id=lid.id,
        status=AnswerStatus.STATED,
        stated_value="glass lid",
        stated_phrase="with a glass lid",
    )

    ran = answered(tmp_path, factors=(lid,), questions=(), answers=(stated,))

    assert (
        "[1] with a glass lid\n    Question: none, the shopper asked for this\n"
        "    Answer: with a glass lid"
    ) in evidence_input(ran, "Alpha Cheapo")


def test_a_read_that_fails_twice_leaves_every_answer_unverified(tmp_path: Path) -> None:
    ran = run(
        tmp_path,
        factors=(HOB,),
        questions=(HOB_QUESTION,),
        answers=(INDUCTION,),
        evidence={"Alpha Cheapo": (REVIEW,)},
        evidence_reads={"Alpha Cheapo": ChatError("down")},
    )

    assert option(ran, "Alpha Cheapo").factor_values[0].fit is Fit.UNVERIFIED
    assert fit_entry(ran, "Alpha Cheapo")[1] == (
        "Hob compatibility: durability evidence could not be read"
    )


# --- The linked product, and the option's own page ---

LINKED = ProductOption(
    id="option-link",
    name="Alpha Cheapo",
    brand="Alpha",
    link="https://www.shop.example.nl/alpha-cheapo",
)


def with_linked_page(markdown: str) -> Shop:
    """The two pans, and the linked product's shop page with this text."""
    page = product_page(
        LINKED.link or "", "Alpha Cheapo koekenpan", "Alpha", offer("20"), markdown=markdown
    )
    return Shop(PAN_SHOP.search, {**PAN_SHOP.pages, LINKED.link or "": page})


def test_the_linked_product_that_fails_an_answer_stays_first_with_its_page_as_the_source(
    tmp_path: Path,
) -> None:
    fails = fit(1, "fails", "not for induction", "Geschikt voor inductie: Nee", by="seller")
    ran = run(
        tmp_path,
        shop=with_linked_page("Geschikt voor inductie: Nee"),
        linked=LINKED,
        factors=(HOB,),
        questions=(HOB_QUESTION,),
        answers=(INDUCTION,),
        evidence={"Alpha Cheapo": ()},
        evidence_reads={"Alpha Cheapo": reading(fits=[fails])},
    )

    first = ran.output.options[0]
    assert first.id == "option-link"
    assert first.factor_values == (
        FactorValue(
            factor_id=HOB.id,
            value="not for induction",
            fit=Fit.FAILS,
            source=Source(kind=SourceKind.URL, reference=LINKED.link, stated_by=StatedBy.SELLER),
        ),
    )
    assert 'Left out "Alpha Cheapo"' not in [
        summary
        for summary, reason in excluded(ran).items()
        if reason != "it is the product at your link"
    ]


def test_an_options_product_page_is_one_more_result_of_the_read(tmp_path: Path) -> None:
    alpha = page_url("Alpha Cheapo")
    page = product_page(
        alpha, "Alpha Cheapo", "Alpha", offer("20"), markdown="Geschikt voor inductie: Ja"
    )
    ran = run(
        tmp_path,
        shop=Shop(PAN_SHOP.search, {**PAN_SHOP.pages, alpha: page}),
        factors=(HOB,),
        questions=(HOB_QUESTION,),
        answers=(INDUCTION,),
        evidence={"Alpha Cheapo": ()},
    )

    shown = evidence_input(ran, "Alpha Cheapo")
    assert alpha in shown
    assert "Geschikt voor inductie: Ja" in shown


def test_a_linked_product_with_no_brand_gets_only_unverified_values(tmp_path: Path) -> None:
    unbranded = LINKED.model_copy(update={"brand": None})
    meets = fit(1, "meets", "works on induction", "Geschikt voor inductie: Ja", by="seller")
    ran = run(
        tmp_path,
        shop=with_linked_page("Geschikt voor inductie: Ja"),
        request=PAN.model_copy(update={"category": None}),
        linked=unbranded,
        factors=(HOB,),
        questions=(HOB_QUESTION,),
        answers=(INDUCTION,),
        evidence={"Alpha Cheapo": ()},
        evidence_reads={"Alpha Cheapo": reading(fits=[meets])},
    )

    (linked,) = ran.output.options
    assert linked.factor_values[0].fit is Fit.UNVERIFIED
    assert fit_entry(ran, "Alpha Cheapo")[1] == (
        "Hob compatibility: the product has no brand to check the result against"
    )


# --- A slot refilled after an answer ---


def test_a_slot_whose_option_fails_an_answer_is_refilled_once_from_the_buyable_candidates_left(
    tmp_path: Path,
) -> None:
    shop = pan_shop(
        ("Alpha Cheapo", "20"), ("Beta Steelo", "40"), ("Gamma Plaino", "60"), ("Delta Basic", "30")
    )
    ran = run(
        tmp_path,
        shop=shop,
        factors=(HOB,),
        questions=(HOB_QUESTION,),
        answers=(INDUCTION,),
        evidence={"Alpha Cheapo": (NOT_INDUCTION,)},
        evidence_reads={"Alpha Cheapo": reading(fits=[ALPHA_FAILS])},
    )

    assert [each.name for each in ran.output.options] == [
        "Gamma Plaino",
        "Delta Basic",
        "Beta Steelo",
    ]
    assert (
        'Chose "Gamma Plaino" as the cheapest in place of "Alpha Cheapo"',
        "its option did not meet an answer; a slot is refilled once",
    ) in [
        (entry.summary, entry.reason)
        for entry in ran.output.trail
        if entry.kind is TrailKind.DECIDED
    ]
