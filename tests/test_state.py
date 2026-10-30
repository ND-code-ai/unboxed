from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from shopper.state import (
    TIER_3_BOUNDARY,
    Agent,
    Answer,
    AnswerStatus,
    Assumptions,
    Caveat,
    CaveatCode,
    CheckItem,
    CheckReason,
    Choice,
    Comparison,
    ComparisonRow,
    DecisionFactor,
    DurabilityEvidence,
    EvidenceSummary,
    FactorKind,
    FactorValue,
    Figure,
    Finding,
    FindingKind,
    FindingsState,
    Fit,
    LcaInput,
    LcaResult,
    Listing,
    Material,
    ProductOption,
    Question,
    RecurringCostState,
    Report,
    Request,
    Scope,
    Source,
    Sourced,
    SourceKind,
    StatedIn,
    TrailEntry,
    TrailKind,
    TypicalLifespan,
    Warning,
    WarningCode,
    WarrantyTerm,
)

FRYING_PAN_TEXT = "I need a new frying pan, budget 50 euro"
SEEN_ON = date(2026, 10, 17)


def seen(price: str) -> dict[str, object]:
    """A price with the search result it was seen in and the date."""
    return {
        "price": Decimal(price),
        "price_source": Source(kind=SourceKind.URL, reference="https://www.bol.com/p/1"),
        "price_seen_on": SEEN_ON,
    }


def test_request_holds_what_the_user_asked_for() -> None:
    request = Request.model_validate(
        {
            "original_text": FRYING_PAN_TEXT,
            "category": "frying pan",
            "budget": "50",
            "scope": "tuned",
        }
    )

    assert request.budget == Decimal("50")
    assert request.currency == "EUR"
    assert request.scope is Scope.TUNED
    assert request.product_url is None


def test_request_in_another_currency_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Request(original_text="a pan, budget £40", scope=Scope.TUNED, currency="GBP")


@pytest.mark.parametrize("budget", ["0", "-5"])
def test_budget_that_is_not_above_zero_is_rejected(budget: str) -> None:
    with pytest.raises(ValidationError):
        Request(original_text="a pan, budget 0", scope=Scope.TUNED, budget=Decimal(budget))


def test_unclear_request_with_a_category_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Request(original_text="pan or kettle", scope=Scope.UNCLEAR, category="frying pan")


def test_several_products_request_with_a_category_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Request(
            original_text="a pan and a kettle", scope=Scope.SEVERAL_PRODUCTS, category="frying pan"
        )


def test_declined_request_may_name_its_category() -> None:
    request = Request(original_text="a pizza", scope=Scope.NOT_A_PRODUCT, category="pizza")

    assert request.category == "pizza"


def url_source(reference: str = "https://example.org/pan-guide") -> Source:
    return Source(kind=SourceKind.URL, reference=reference)


def choices(count: int) -> tuple[Choice, ...]:
    return tuple(Choice(id=f"c{n}", text=f"Choice {n}") for n in range(1, count + 1))


def question(number: int = 1, choice_count: int = 3) -> Question:
    return Question(
        id=f"q{number}",
        factor_id=f"f{number}",
        text="Which hob do you cook on?",
        reason="Not every pan works on induction.",
        choices=choices(choice_count),
    )


def test_typical_yearly_cost_without_its_source_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DecisionFactor(
            id="f1",
            name="Filter cost",
            kind=FactorKind.RECURRING_COST,
            why="Filters need replacing every year.",
            source=url_source(),
            typical_yearly_cost=Decimal("25"),
        )


def test_a_typical_yearly_cost_converted_without_a_cost_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DecisionFactor(
            id="f1",
            name="Filter cost",
            kind=FactorKind.RECURRING_COST,
            why="Filters need replacing every year.",
            source=url_source(),
            typical_yearly_cost_converted_from="USD",
        )


def test_a_typical_yearly_cost_on_a_factor_not_about_a_recurring_cost_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DecisionFactor(
            id="f1",
            name="Hob compatibility",
            kind=FactorKind.COMPATIBILITY,
            why="Not every pan works on induction.",
            source=url_source(),
            typical_yearly_cost=Decimal("25"),
            typical_yearly_cost_source=url_source(),
        )


@pytest.mark.parametrize("count", [1, 5])
def test_question_with_fewer_than_two_or_more_than_four_choices_is_rejected(count: int) -> None:
    with pytest.raises(ValidationError):
        question(choice_count=count)


def test_answer_holds_each_status() -> None:
    chosen = Answer(factor_id="f1", status=AnswerStatus.CHOSEN, choice_id="c2", uses_per_year=52)
    stated = Answer(
        factor_id="f2",
        status=AnswerStatus.STATED,
        stated_value="induction",
        stated_phrase="for induction",
    )
    not_sure = Answer(factor_id="f3", status=AnswerStatus.NOT_SURE)
    skipped = Answer(factor_id="f4", status=AnswerStatus.SKIPPED)

    assert (chosen.choice_id, stated.stated_phrase) == ("c2", "for induction")
    assert (not_sure.choice_id, skipped.stated_value) == (None, None)


def test_a_stated_answer_may_carry_the_choice_code_mapped_it_onto() -> None:
    stated = Answer(
        factor_id="f2",
        status=AnswerStatus.STATED,
        choice_id="c1",
        stated_value="Induction",
        stated_phrase="for induction",
    )

    assert stated.choice_id == "c1"


def test_an_answer_is_stated_in_the_request_unless_it_says_otherwise() -> None:
    stated = Answer(
        factor_id="f2",
        status=AnswerStatus.STATED,
        stated_value="induction",
        stated_phrase="for induction",
    )

    assert stated.stated_in is StatedIn.REQUEST


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "stated", "stated_value": "induction", "stated_phrase": "on induction"},
        {"status": "not_sure", "stated_phrase": "no idea which hob"},
    ],
    ids=["stated", "not sure, with its phrase"],
)
def test_a_stated_or_not_sure_answer_may_be_from_the_reply(fields: dict[str, str]) -> None:
    assert Answer.model_validate({"factor_id": "f1", "stated_in": "reply", **fields})


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "chosen"},
        {"status": "stated", "stated_value": "induction"},
        {"status": "skipped", "choice_id": "c1"},
        {"status": "not_sure", "stated_value": "induction", "stated_phrase": "for induction"},
        {"status": "chosen", "choice_id": "c1", "stated_in": "reply"},
        {"status": "skipped", "stated_in": "reply"},
        {"status": "not_sure", "stated_in": "reply"},
        {"status": "not_sure", "stated_phrase": "no idea"},
        {
            "status": "not_sure",
            "choice_id": "c1",
            "stated_phrase": "no idea",
            "stated_in": "reply",
        },
    ],
    ids=[
        "chosen with no choice",
        "stated with no phrase",
        "skipped with a choice",
        "not sure with a value",
        "chosen from the reply",
        "skipped from the reply",
        "not sure from the reply with no phrase",
        "not sure picked with a phrase",
        "not sure from the reply with a choice",
    ],
)
def test_answer_whose_content_does_not_match_its_status_is_rejected(
    fields: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        Answer.model_validate({"factor_id": "f1", **fields})


def carbon_steel_pan() -> ProductOption:
    return ProductOption(
        id="o1",
        name="Carbon steel pan 28 cm",
        **seen("40"),
        link="https://example.org/carbon-steel-pan",
        lifespan_years=Decimal("30"),
        lifespan_source=url_source("https://example.org/pan-test"),
        durability_evidence=DurabilityEvidence(
            warranty=Sourced(value=WarrantyTerm(years=Decimal("10")), source=url_source()),
            typical_lifespan=Sourced(
                value=TypicalLifespan(low=Decimal("2"), high=Decimal("5")), source=url_source()
            ),
            care=Sourced(value="Season before first use", source=url_source()),
            findings=(
                Finding(
                    kind=FindingKind.TEST,
                    summary="No warping after 500 heating cycles.",
                    source=url_source("https://example.org/pan-test"),
                    rating="4.6 out of 5",
                ),
            ),
            findings_state=FindingsState.FOUND,
        ),
        factor_values=(
            FactorValue(factor_id="f1", value="Induction", fit=Fit.MEETS, source=url_source()),
        ),
        materials=(Material(name="carbon steel", mass_kg=Decimal("1.4"), source=url_source()),),
        weight_kg=Decimal("1.5"),
        weight_source=url_source(),
    )


@pytest.mark.parametrize(
    ("fit", "value"),
    [(Fit.MEETS, None), (Fit.FAILS, None), (Fit.UNVERIFIED, "works on induction")],
)
def test_a_factor_value_has_its_text_exactly_when_its_fit_is_settled(
    fit: Fit, value: str | None
) -> None:
    with pytest.raises(ValidationError):
        FactorValue(factor_id="f1", value=value, fit=fit, source=url_source())


def test_product_option_with_nothing_known_is_valid() -> None:
    option = ProductOption(id="o2", name="Unknown pan")

    assert (option.price, option.lifespan_years) == (None, None)
    assert option.durability_evidence.findings == ()


def owner_report(rating: str | None, review_count: int | None) -> Finding:
    return Finding(
        kind=FindingKind.OWNER_REPORT,
        summary="One owner's pan lost its coating after a year",
        source=url_source("https://example.org/forum"),
        rating=rating,
        review_count=review_count,
    )


def test_an_owner_reports_rating_is_rejected_without_a_review_count() -> None:
    with pytest.raises(ValidationError):
        owner_report("4.5/5", None)


def test_an_owner_report_with_a_rating_and_its_review_count_is_valid() -> None:
    assert owner_report("4.5/5", 120).review_count == 120


@pytest.mark.parametrize(
    ("findings", "state"),
    [
        ((), FindingsState.FOUND),
        (("finding",), FindingsState.NONE_FOUND),
        (("finding",), FindingsState.NOT_SEARCHED),
    ],
)
def test_the_findings_state_is_found_exactly_when_there_are_findings(
    findings: tuple[str, ...], state: FindingsState
) -> None:
    with pytest.raises(ValidationError):
        DurabilityEvidence(
            findings=tuple(owner_report(None, None) for _ in findings), findings_state=state
        )


def test_lifespan_without_a_source_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductOption(id="o2", name="Non-stick pan", lifespan_years=Decimal("2"))


def test_lifespan_source_without_a_lifespan_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductOption(id="o2", name="Non-stick pan", lifespan_source=url_source())


def test_a_weight_and_its_source_are_given_together() -> None:
    with pytest.raises(ValidationError):
        ProductOption(id="o2", name="Carbon steel pan", weight_kg=Decimal("2.1"))
    with pytest.raises(ValidationError):
        ProductOption(id="o2", name="Carbon steel pan", weight_source=url_source())


def test_recurring_cost_without_its_source_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductOption(id="o3", name="Bagged vacuum", recurring_cost_per_year=Decimal("25"))


def test_a_recurring_cost_is_found_exactly_when_it_has_a_value() -> None:
    found = ProductOption(
        id="o3",
        name="Bagged vacuum",
        recurring_cost_per_year=Decimal("25"),
        recurring_cost_source=url_source(),
        recurring_cost_state=RecurringCostState.FOUND,
    )
    assert found.recurring_cost_state is RecurringCostState.FOUND
    with pytest.raises(ValidationError):
        ProductOption(id="o3", name="Bagged vacuum", recurring_cost_state=RecurringCostState.FOUND)
    with pytest.raises(ValidationError):
        ProductOption(
            id="o3",
            name="Bagged vacuum",
            recurring_cost_per_year=Decimal("25"),
            recurring_cost_source=url_source(),
            recurring_cost_state=RecurringCostState.NOT_FOUND,
        )


def test_only_a_recurring_cost_found_can_be_converted_or_leave_others_out() -> None:
    with pytest.raises(ValidationError):
        ProductOption(id="o3", name="Kettle", recurring_cost_converted_from="USD")
    with pytest.raises(ValidationError):
        ProductOption(id="o3", name="Kettle", other_consumables_left_out=True)


def test_a_warranty_is_years_or_a_lifetime() -> None:
    assert WarrantyTerm(lifetime=True).years is None
    with pytest.raises(ValidationError):
        WarrantyTerm()
    with pytest.raises(ValidationError):
        WarrantyTerm(years=Decimal("10"), lifetime=True)


def test_a_typical_lifespan_runs_from_low_to_high() -> None:
    with pytest.raises(ValidationError):
        TypicalLifespan(low=Decimal("5"), high=Decimal("2"))


def test_product_option_in_another_currency_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductOption(id="o2", name="Pan", currency="GBP", **seen("30"))


def test_a_price_with_its_source_and_the_date_it_was_seen_is_valid() -> None:
    option = ProductOption(id="o2", name="Kettle", price_variant="900 ml", **seen("86.98"))

    assert option.price_seen_on == SEEN_ON


@pytest.mark.parametrize("left_out", ["price", "price_source", "price_seen_on"])
def test_a_price_without_its_source_or_date_is_rejected(left_out: str) -> None:
    given = {key: value for key, value in seen("86.98").items() if key != left_out}
    with pytest.raises(ValidationError):
        ProductOption(id="o2", name="Kettle", **given)


def test_only_a_price_has_a_shipping_cost() -> None:
    with pytest.raises(ValidationError):
        ProductOption(id="o2", name="Kettle", shipping=Decimal("2.99"))


def test_a_price_to_confirm_is_about_an_option_and_no_factor() -> None:
    item = CheckItem(option_id="option-1", reason=CheckReason.PRICE)

    assert item.factor_id is None


@pytest.mark.parametrize(
    ("factor_id", "option_id", "reason"),
    [
        ("researched-1", "option-1", CheckReason.PRICE),
        (None, None, CheckReason.PRICE),
        (None, "option-1", CheckReason.UNANSWERED),
        (None, "option-1", CheckReason.UNVERIFIED),
    ],
    ids=["price with a factor", "price for no option", "unanswered", "unverified"],
)
def test_only_a_price_to_confirm_is_about_no_factor(
    factor_id: str | None, option_id: str | None, reason: CheckReason
) -> None:
    with pytest.raises(ValidationError):
        CheckItem(factor_id=factor_id, option_id=option_id, reason=reason)


MODEL_ESTIMATE = Source(kind=SourceKind.MODEL_ESTIMATE, reference="model estimate")


def carbon_steel(mass: str = "1.4", low: str = "1.5", high: str = "3") -> LcaInput:
    return LcaInput(
        name="carbon steel",
        material_source=url_source(),
        mass_kg=Decimal(mass),
        mass_source=url_source(),
        factor_low=Decimal(low),
        factor_high=Decimal(high),
        factor_source=MODEL_ESTIMATE,
    )


@pytest.mark.parametrize(("form", "form_source"), [("recycled", None), (None, MODEL_ESTIMATE)])
def test_an_lca_input_has_a_form_exactly_with_its_source(
    form: str | None, form_source: Source | None
) -> None:
    with pytest.raises(ValidationError):
        LcaInput.model_validate(
            carbon_steel().model_dump() | {"form": form, "form_source": form_source}
        )


def pan_lca(low: str = "4.2", high: str = "9.8", **changes: object) -> LcaResult:
    """A tier 3 result; `changes` replace or drop (None) its fields before validation."""
    fields: dict[str, object] = {
        "option_id": "o1",
        "co2e_low": Decimal(low),
        "co2e_high": Decimal(high),
        "tier": 3,
        "source": MODEL_ESTIMATE,
        "boundary": TIER_3_BOUNDARY,
        "inputs": (carbon_steel(),),
        "manufacturing_low": Decimal("1"),
        "manufacturing_high": Decimal("2"),
        "manufacturing_source": MODEL_ESTIMATE,
        **changes,
    }
    return LcaResult.model_validate(
        {key: value for key, value in fields.items() if value is not None}
    )


def test_lca_result_may_be_a_single_point_range() -> None:
    assert pan_lca(low="5", high="5").co2e_low == Decimal("5")


def test_co2e_low_above_high_is_rejected() -> None:
    with pytest.raises(ValidationError):
        pan_lca(low="9.8", high="4.2")


@pytest.mark.parametrize("mass", ["0", "-1.4"])
def test_lca_input_with_a_mass_not_above_zero_is_rejected(mass: str) -> None:
    with pytest.raises(ValidationError):
        carbon_steel(mass=mass)


@pytest.mark.parametrize("low, high", [("0", "3"), ("-1", "3")])
def test_lca_input_with_a_factor_not_above_zero_is_rejected(low: str, high: str) -> None:
    with pytest.raises(ValidationError):
        carbon_steel(low=low, high=high)


def test_lca_input_with_its_low_factor_above_its_high_is_rejected() -> None:
    with pytest.raises(ValidationError):
        carbon_steel(low="3", high="1.5")


def test_manufacturing_low_above_high_is_rejected() -> None:
    with pytest.raises(ValidationError):
        pan_lca(manufacturing_low=Decimal("2"), manufacturing_high=Decimal("1"))


def test_manufacturing_without_its_source_is_rejected() -> None:
    with pytest.raises(ValidationError):
        pan_lca(tier=2, boundary="cradle to gate", manufacturing_source=None)


@pytest.mark.parametrize(
    "changes",
    [
        {"inputs": ()},
        {"manufacturing_low": None, "manufacturing_high": None, "manufacturing_source": None},
        {"boundary": "manufacturing only"},
    ],
)
def test_model_estimate_without_inputs_manufacturing_or_its_fixed_boundary_is_rejected(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        pan_lca(**changes)


def test_benchmark_may_cover_materials_only() -> None:
    pan_lca(
        tier=2,
        boundary="cradle to gate: materials only",
        manufacturing_low=None,
        manufacturing_high=None,
        manufacturing_source=None,
    )


def used_pan() -> Listing:
    return Listing(
        id="l1",
        option_id="o1",
        title="De Buyer koekenpan 28 cm, gebruikt",
        price=Decimal("22.50"),
        condition="used",
        link="https://www.ebay.nl/itm/1",
        country="NL",
        ships_to_nl=True,
        marketplace="EBAY_NL",
    )


def test_listing_in_another_currency_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Listing.model_validate({**used_pan().model_dump(), "currency": "GBP"})


def test_exclusion_without_a_reason_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TrailEntry(agent=Agent.TCO, kind=TrailKind.EXCLUDED, summary="Aluminium pan")


def pan_comparison() -> Comparison:
    return Comparison(
        baseline_option_id="o1",
        rows=(
            ComparisonRow(
                option_id="o1",
                cost_per_year=Decimal("1.33"),
                purchases=1,
                horizon_cost=Decimal("40"),
                savings=Decimal("0"),
                missing_reasons={Figure.COST_PER_USE: "Uses per year was not given"},
                recurring_costs_not_found=True,
                within_budget=True,
            ),
        ),
    )


def test_unknown_warning_code_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Warning.model_validate({"code": "budget_unreadible", "message": "Typo in the code."})


def factor(number: int) -> DecisionFactor:
    return DecisionFactor(
        id=f"f{number}",
        name=f"Factor {number}",
        kind=FactorKind.REQUIREMENT,
        why="It decides which options fit.",
        source=url_source(),
    )


def test_report_where_every_question_was_skipped_is_valid() -> None:
    questions = tuple(question(number) for number in range(1, 4))
    report = Report(
        request=Request(
            original_text=FRYING_PAN_TEXT,
            category="frying pan",
            budget=Decimal("50"),
            scope=Scope.TUNED,
        ),
        factors=tuple(factor(number) for number in range(1, 4)),
        questions=questions,
        answers=tuple(
            Answer(factor_id=asked.factor_id, status=AnswerStatus.SKIPPED) for asked in questions
        ),
        options=(carbon_steel_pan(),),
        lca_results=(pan_lca(),),
        listings=(used_pan(),),
        comparison=pan_comparison(),
        evidence_summary=EvidenceSummary(lifespans_sourced=1, footprints_model_estimate=1),
        check_before_you_buy=tuple(
            CheckItem(factor_id=asked.factor_id, reason=CheckReason.UNANSWERED)
            for asked in questions
        ),
        trail=(TrailEntry(agent=Agent.BRIEF, kind=TrailKind.FOUND, summary="3 factors"),),
    )

    assert all(answer.status is AnswerStatus.SKIPPED for answer in report.answers)
    assert len(report.check_before_you_buy) == 3
    assert Report.model_validate_json(report.model_dump_json()) == report


def test_declined_report_is_valid() -> None:
    report = Report(
        request=Request(original_text="a pizza", category="pizza", scope=Scope.NOT_A_PRODUCT)
    )

    assert report.request.scope is Scope.NOT_A_PRODUCT
    assert (report.questions, report.options, report.comparison) == ((), (), None)


def test_unclear_report_is_valid() -> None:
    report = Report(request=Request(original_text="asdf qwer", scope=Scope.UNCLEAR))

    assert report.request.category is None
    assert report.evidence_summary == EvidenceSummary()


def test_report_with_no_options_is_valid() -> None:
    report = Report(
        request=Request(
            original_text="a left-handed tile cutter, budget 5 euro",
            category="tile cutter",
            budget=Decimal("5"),
            scope=Scope.TUNED,
        ),
        questions=(question(),),
        answers=(Answer(factor_id="f1", status=AnswerStatus.NOT_SURE),),
        caveats=(Caveat(code=CaveatCode.NOT_TUNED),),
        warnings=(Warning(code=WarningCode.NOTHING_WITHIN_BUDGET, message="Nothing found."),),
    )

    assert report.options == ()
    assert report.lca_results == ()
    assert report.evidence_summary.lifespans_missing == 0


def test_report_with_a_sixth_question_is_rejected() -> None:
    request = Request(original_text=FRYING_PAN_TEXT, scope=Scope.TUNED)

    assert len(Report(request=request, questions=tuple(map(question, range(5)))).questions) == 5
    with pytest.raises(ValidationError):
        Report(request=request, questions=tuple(map(question, range(6))))


def test_report_with_a_thirteenth_factor_is_rejected() -> None:
    # Eight researched factors, the one about how often the product is used and three of the
    # user's own.
    request = Request(original_text=FRYING_PAN_TEXT, scope=Scope.TUNED)

    assert len(Report(request=request, factors=tuple(map(factor, range(12)))).factors) == 12
    with pytest.raises(ValidationError):
        Report(request=request, factors=tuple(map(factor, range(13))))


@pytest.mark.parametrize("price", ["-1", "-0.01"])
def test_negative_price_is_rejected(price: str) -> None:
    with pytest.raises(ValidationError):
        ProductOption(id="o2", name="Pan", price=Decimal(price))


@pytest.mark.parametrize("lifespan", ["0", "-2"])
def test_zero_or_negative_lifespan_is_rejected(lifespan: str) -> None:
    with pytest.raises(ValidationError):
        ProductOption(
            id="o2", name="Pan", lifespan_years=Decimal(lifespan), lifespan_source=url_source()
        )


@pytest.mark.parametrize("lifespan", ["0", "-2"])
def test_zero_or_negative_lifespan_override_is_rejected(lifespan: str) -> None:
    with pytest.raises(ValidationError):
        Assumptions(lifespan_overrides={"o1": Decimal(lifespan)})


@pytest.mark.parametrize("low, high", [("-1", "5"), ("-5", "-1")])
def test_negative_co2e_is_rejected(low: str, high: str) -> None:
    with pytest.raises(ValidationError):
        pan_lca(low=low, high=high)


@pytest.mark.parametrize("reference", ["pan guide", "ftp://example.org/guide", ""])
def test_decision_factor_with_a_source_that_is_not_a_url_is_rejected(reference: str) -> None:
    with pytest.raises(ValidationError):
        DecisionFactor(
            id="f1",
            name="Induction",
            kind=FactorKind.COMPATIBILITY,
            why="The pan must work on the hob.",
            source=url_source(reference),
        )


def test_decision_factor_with_a_non_url_kind_of_source_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DecisionFactor(
            id="f1",
            name="Induction",
            kind=FactorKind.COMPATIBILITY,
            why="The pan must work on the hob.",
            source=Source(kind=SourceKind.MODEL_ESTIMATE, reference="https://example.org/x"),
        )


def test_decision_factor_the_user_stated_has_the_user_as_its_source() -> None:
    battery = {
        "id": "user-1",
        "name": "with a spare battery",
        "why": "You asked for this.",
        "source": Source(kind=SourceKind.USER, reference="with a spare battery"),
    }

    DecisionFactor(**battery, kind=FactorKind.REQUIREMENT)
    with pytest.raises(ValidationError):
        DecisionFactor(**battery, kind=FactorKind.COMPATIBILITY)


def test_only_the_usage_factor_has_no_source() -> None:
    usage = {"id": "f1", "name": "Usage", "kind": FactorKind.USAGE, "why": "It sets cost per use."}
    hob = {**usage, "name": "Induction", "kind": FactorKind.COMPATIBILITY}

    assert DecisionFactor(**usage).source is None
    assert DecisionFactor(**hob, source=url_source()).source == url_source()
    with pytest.raises(ValidationError):
        DecisionFactor(**usage, source=url_source())
    with pytest.raises(ValidationError):
        DecisionFactor(**hob)


def test_negative_recurring_cost_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductOption(
            id="o3",
            name="Bagged vacuum",
            recurring_cost_per_year=Decimal("-1"),
            recurring_cost_source=url_source(),
        )


def test_negative_typical_yearly_cost_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DecisionFactor(
            id="f1",
            name="Filter cost",
            kind=FactorKind.RECURRING_COST,
            why="Filters need replacing every year.",
            source=url_source(),
            typical_yearly_cost=Decimal("-25"),
            typical_yearly_cost_source=url_source(),
        )


@pytest.mark.parametrize("field", ["price", "shipping_cost"])
def test_negative_listing_price_or_shipping_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        Listing.model_validate({**used_pan().model_dump(), field: Decimal("-1")})
