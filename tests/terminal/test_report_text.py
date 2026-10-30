"""The report as plain lines, one section at a time, on reports that `assemble` built."""

from decimal import Decimal

from samples import (
    MODEL_ESTIMATE,
    PRICE_SEEN_ON,
    STEEL_INPUT,
    model_estimate_parts,
    seen_price,
)
from shopper.graph.report import DEFAULT_ASSUMPTIONS, assemble
from shopper.state import (
    Agent,
    Answer,
    AnswerStatus,
    Assumptions,
    DecisionFactor,
    DurabilityEvidence,
    FactorKind,
    FactorValue,
    Finding,
    FindingKind,
    FindingsState,
    Fit,
    LcaInput,
    LcaResult,
    ProductOption,
    RecurringCostState,
    Report,
    Request,
    Scope,
    Source,
    Sourced,
    SourceKind,
    StatedBy,
    StatedIn,
    TrailEntry,
    TrailKind,
    TypicalLifespan,
    Warning,
    WarningCode,
    WarrantyTerm,
)
from shopper.terminal.report_text import (
    caveat_lines,
    check_lines,
    evidence_summary_lines,
    option_lines,
    printed_report,
    savings_lines,
    stated_lines,
    trail_lines,
    typical_cost_lines,
    warning_lines,
)

WEB = Source(kind=SourceKind.URL, reference="https://example.com/pans")
ESTIMATE = Source(kind=SourceKind.MODEL_ESTIMATE, reference="test")
# The two options of the frying pan worked example in docs/architecture/calculations.md.
NON_STICK = ProductOption(
    id="non-stick",
    name="Non-stick pan",
    **seen_price("20"),
    lifespan_years=Decimal("2"),
    lifespan_source=ESTIMATE,
)
CARBON_STEEL = ProductOption(
    id="carbon-steel",
    name="Carbon steel pan",
    **seen_price("40"),
    lifespan_years=Decimal("30"),
    lifespan_source=WEB,
)


def report_of(
    *options: ProductOption,
    scope: Scope = Scope.TUNED,
    budget: Decimal | None = None,
    assumptions: Assumptions = DEFAULT_ASSUMPTIONS,
    factors: tuple[DecisionFactor, ...] = (),
    answers: tuple[Answer, ...] = (),
    lca_results: tuple[LcaResult, ...] = (),
    trail: tuple[TrailEntry, ...] = (),
    warnings: tuple[Warning, ...] = (),
) -> Report:
    request = Request(
        original_text="a frying pan", category="frying pan", scope=scope, budget=budget
    )
    return assemble(
        request,
        trail,
        warnings,
        factors=factors,
        answers=answers,
        options=options,
        lca_results=lca_results,
        assumptions=assumptions,
    )


# --- The evidence summary line ---


def test_the_evidence_summary_is_one_line_of_counts() -> None:
    report = report_of(NON_STICK, CARBON_STEEL)

    assert evidence_summary_lines(report) == (
        "Lifespan sourced for 1 of 2 options. CO2e to make: not found for 2.",
    )


def test_a_lifespan_the_user_set_is_counted_as_set_by_them() -> None:
    assumptions = Assumptions(lifespan_overrides={"non-stick": Decimal("3")})

    report = report_of(NON_STICK, CARBON_STEEL, assumptions=assumptions)

    assert evidence_summary_lines(report) == (
        "Lifespan sourced for 1 of 2 options, set by you for 1. CO2e to make: not found for 2.",
    )


def test_a_report_with_no_options_still_has_its_evidence_summary_line() -> None:
    assert evidence_summary_lines(report_of()) == ("Lifespan sourced for 0 of 0 options.",)


# --- The caveat and the warnings ---

ENERGY_CAVEAT = (
    "Energy and water use are not included in these figures. For this kind of product they "
    "are a large part of the cost, so the order of these options can change once they are "
    "counted."
)


def test_an_energy_heavy_request_prints_its_caveat() -> None:
    report = report_of(NON_STICK, scope=Scope.ENERGY_HEAVY)

    assert caveat_lines(report) == (ENERGY_CAVEAT,)


def test_a_tuned_request_prints_no_caveat() -> None:
    assert caveat_lines(report_of(NON_STICK)) == ()


def test_every_warning_prints_its_message_in_order() -> None:
    unreadable = Warning(code=WarningCode.BUDGET_UNREADABLE, message="The budget was not read.")

    report = report_of(NON_STICK, budget=Decimal("10"), warnings=(unreadable,))

    assert warning_lines(report) == (
        "The budget was not read.",
        "Nothing found within €10; the cheapest option is €20.",
    )


# --- One block per option ---


def test_each_option_is_a_block_with_the_figures_of_the_worked_example() -> None:
    report = report_of(
        NON_STICK, CARBON_STEEL, budget=Decimal("30"), assumptions=Assumptions(uses_per_year=50)
    )

    assert option_lines(report) == (
        "Non-stick pan",
        "Price: €20, shipping not stated, price seen at example.com on 17 October 2026",
        "Lifespan: 2 years (rough estimate)",
        "  No durability evidence found",
        "  Owner and tester reports not looked up",
        "Cost per year: €10",
        "Cost per use: €0.20",
        "Purchases over 10 years: 5",
        "Cost over 10 years: €100",
        "CO2e: not available (no CO2e estimate for this option)",
        "",
        "Carbon steel pan",
        "Price: €40, shipping not stated, price seen at example.com on 17 October 2026",
        "Lifespan: 30 years (example.com)",
        "  Owner and tester reports not looked up",
        "Cost per year: €1.33",
        "Cost per use: €0.03",
        "Purchases over 10 years: 1",
        "Cost over 10 years: €40",
        "CO2e: not available (no CO2e estimate for this option)",
        "Over your budget",
    )


def test_a_price_says_where_it_was_seen_and_what_it_was_quoted_for_with_its_link() -> None:
    kettle = ProductOption(
        id="option-1",
        name="Fellow Corvo EKG",
        price=Decimal("86.98"),
        price_source=Source(kind=SourceKind.URL, reference="https://www.bol.com/nl/nl/p/ekg/1"),
        price_seen_on=PRICE_SEEN_ON,
        price_variant="900 ml",
        link="https://www.bol.com/nl/nl/p/ekg/1",
    )

    lines = option_lines(report_of(kettle))

    assert lines[:3] == (
        "Fellow Corvo EKG",
        "Price: €86.98 (900 ml), shipping not stated, price seen at bol.com on 17 October 2026",
        "Link: https://www.bol.com/nl/nl/p/ekg/1",
    )


def test_an_offer_on_a_comparison_site_names_its_shop_and_its_shipping() -> None:
    pan = NON_STICK.model_copy(
        update={
            "price": Decimal("39.95"),
            "price_source": Source(
                kind=SourceKind.URL,
                reference="https://www.beslist.nl/p/tramontina-professional/1",
                label="Kookexpert.nl",
            ),
            "shipping": Decimal("4.95"),
        }
    )

    assert option_lines(report_of(pan))[1] == (
        "Price: €39.95, plus €4.95 shipping, price seen at Kookexpert.nl via beslist.nl on "
        "17 October 2026"
    )


def test_an_offer_that_ships_for_nothing_says_so() -> None:
    pan = NON_STICK.model_copy(update={"shipping": Decimal("0")})

    assert option_lines(report_of(pan))[1] == (
        "Price: €20, free shipping, price seen at example.com on 17 October 2026"
    )


# --- Factor values (terminal_app.md, "Factor values") ---

HOB_FACTOR = DecisionFactor(
    id="hob", name="Hob compatibility", kind=FactorKind.COMPATIBILITY, why="w", source=WEB
)
CARE_FACTOR = DecisionFactor(id="care", name="Care", kind=FactorKind.CARE, why="w", source=WEB)
FONQ = Source(kind=SourceKind.URL, reference="https://www.fonq.nl/pan", stated_by=StatedBy.SELLER)
RTINGS = Source(
    kind=SourceKind.URL, reference="https://www.rtings.com/pan", stated_by=StatedBy.TESTER
)


def valued(option: ProductOption, *values: FactorValue) -> ProductOption:
    return option.model_copy(update={"factor_values": values, "link": "https://example.com/p"})


def test_the_factor_values_follow_the_link_in_the_order_of_the_factors() -> None:
    pan = valued(
        NON_STICK,
        FactorValue(factor_id="care", value="hand wash only", fit=Fit.FAILS, source=RTINGS),
        FactorValue(factor_id="hob", value="works on induction", fit=Fit.MEETS, source=FONQ),
    )

    lines = option_lines(report_of(pan, factors=(HOB_FACTOR, CARE_FACTOR)))

    assert lines[2:5] == (
        "Link: https://example.com/p",
        "Hob compatibility: works on induction (fonq.nl) (the seller states)",
        "Care: hand wash only (rtings.com). You said you'd rather avoid this; the lifespan shown "
        "assumes it is done.",
    )


def test_a_value_no_source_settled_could_not_be_confirmed() -> None:
    pan = valued(NON_STICK, FactorValue(factor_id="hob", fit=Fit.UNVERIFIED, source=WEB))

    lines = option_lines(report_of(pan, factors=(HOB_FACTOR,)))

    assert lines[3] == "Hob compatibility: could not be confirmed"


def test_a_failed_answer_that_is_not_care_shows_the_mismatch_line() -> None:
    bol = Source(
        kind=SourceKind.URL, reference="https://www.bol.com/p/1", stated_by=StatedBy.SELLER
    )
    pan = valued(
        NON_STICK,
        FactorValue(factor_id="hob", value="not suitable for induction", fit=Fit.FAILS, source=bol),
    )

    lines = option_lines(report_of(pan, factors=(HOB_FACTOR,)))

    assert lines[3] == (
        "Does not match your answer for Hob compatibility: not suitable for induction (bol.com) "
        "(the seller states)"
    )


def test_a_factor_of_the_users_own_quotes_the_phrase_it_is_named_by() -> None:
    # "for for induction" in task 1.8.6's live run.
    own = DecisionFactor(
        id="user-1",
        name="for induction",
        kind=FactorKind.REQUIREMENT,
        why="You asked for this.",
        source=Source(kind=SourceKind.USER, reference="for induction"),
    )
    meets = valued(
        NON_STICK,
        FactorValue(factor_id="user-1", value="works on induction", fit=Fit.MEETS, source=FONQ),
    )
    fails = valued(
        NON_STICK,
        FactorValue(factor_id="user-1", value="gas only", fit=Fit.FAILS, source=FONQ),
    )

    assert option_lines(report_of(meets, factors=(own,)))[3] == (
        'You asked for "for induction": works on induction (fonq.nl) (the seller states)'
    )
    assert option_lines(report_of(fails, factors=(own,)))[3] == (
        'Does not match what you asked for, "for induction": gas only (fonq.nl) (the seller states)'
    )


def test_a_price_that_is_not_from_a_web_page_names_no_site() -> None:
    estimated = NON_STICK.model_copy(update={"price_source": ESTIMATE})

    assert option_lines(report_of(estimated))[1] == "Price: €20"


def test_cost_per_use_keeps_its_line_when_uses_per_year_is_not_given() -> None:
    lines = option_lines(report_of(NON_STICK))

    assert "Cost per use: not available (uses per year not given)" in lines
    assert "Over your budget" not in lines


def test_an_option_with_no_price_and_no_lifespan_keeps_every_line_with_its_reason() -> None:
    report = report_of(ProductOption(id="mystery", name="Mystery pan"))

    assert option_lines(report) == (
        "Mystery pan",
        "Price: not available (price not known)",
        "Lifespan: not available (durability evidence could not be read; set a lifespan to see it)",
        "  Owner and tester reports not looked up",
        "Cost per year: not available (price not known)",
        "Cost per use: not available (price not known)",
        "Purchases over 10 years: not available (durability evidence could not be read; set a "
        "lifespan to see it)",
        "Cost over 10 years: not available (price not known)",
        "CO2e: not available (no CO2e estimate for this option)",
    )


def test_a_lifespan_the_user_set_is_shown_as_set_by_them_in_place_of_the_rough_estimate() -> None:
    assumptions = Assumptions(lifespan_overrides={"non-stick": Decimal("4")})

    lines = option_lines(report_of(NON_STICK, assumptions=assumptions))

    assert "Lifespan: 4 years (set by you)" in lines
    # €20 over 4 years.
    assert "Cost per year: €5" in lines


MAKER = Source(
    kind=SourceKind.URL, reference="https://www.tefal.nl/pan", stated_by=StatedBy.MANUFACTURER
)
TESTER = Source(
    kind=SourceKind.URL, reference="https://www.rtings.com/pan", stated_by=StatedBy.TESTER
)


def test_what_a_lifespan_rests_on_is_one_indented_line_per_item_with_its_site() -> None:
    pan = CARBON_STEEL.model_copy(
        update={
            "lifespan_source": TESTER,
            "durability_evidence": DurabilityEvidence(
                warranty=Sourced(value=WarrantyTerm(lifetime=True), source=MAKER),
                wear_material=Sourced(value="non-stick coating", source=TESTER),
                repairability=Sourced(value="spare handles sold", source=MAKER),
                care=Sourced(value="hand wash only", source=TESTER),
                typical_lifespan=Sourced(
                    value=TypicalLifespan(low=Decimal("2"), high=Decimal("5")), source=TESTER
                ),
            ),
        }
    )

    lines = option_lines(report_of(pan))

    start = lines.index("Lifespan: 30 years (rtings.com)")
    assert lines[start + 1 : start + 6] == (
        "  Warranty: lifetime (tefal.nl) (the manufacturer states)",
        "  Wears: non-stick coating (rtings.com)",
        "  Repairs: spare handles sold (tefal.nl) (the manufacturer states)",
        "  Care: hand wash only (rtings.com)",
        "  Typical for this kind of product: 2 to 5 years (rtings.com)",
    )


def test_a_warranty_of_years_and_a_makers_lifespan_say_who_states_them() -> None:
    pan = CARBON_STEEL.model_copy(
        update={
            "lifespan_source": MAKER,
            "durability_evidence": DurabilityEvidence(
                warranty=Sourced(value=WarrantyTerm(years=Decimal("10")), source=MAKER)
            ),
        }
    )

    lines = option_lines(report_of(pan))

    assert "Lifespan: 30 years (tefal.nl) (the manufacturer states)" in lines
    assert "  Warranty: 10 years (tefal.nl) (the manufacturer states)" in lines


def test_years_from_months_show_one_decimal_and_a_makers_typical_lifespan_says_so() -> None:
    pan = CARBON_STEEL.model_copy(
        update={
            "lifespan_years": Decimal(20) / Decimal(12),
            "lifespan_source": TESTER,
            "durability_evidence": DurabilityEvidence(
                typical_lifespan=Sourced(
                    value=TypicalLifespan(low=Decimal("1.5"), high=Decimal(3)), source=MAKER
                )
            ),
        }
    )

    lines = option_lines(report_of(pan))

    assert "Lifespan: 1.7 years (rtings.com)" in lines
    assert (
        "  Typical for this kind of product: 1.5 to 3 years (tefal.nl) (the manufacturer states)"
        in lines
    )


def test_one_year_is_written_in_the_singular() -> None:
    one = NON_STICK.model_copy(update={"lifespan_years": Decimal(1)})

    assert "Lifespan: 1 year (rough estimate)" in option_lines(report_of(one))


def test_a_lifespan_that_shows_as_one_year_is_written_in_the_singular() -> None:
    almost = NON_STICK.model_copy(update={"lifespan_years": Decimal("0.96")})

    assert "Lifespan: 1 year (rough estimate)" in option_lines(report_of(almost))


def test_the_typical_lifespan_rounds_outward() -> None:
    pan = CARBON_STEEL.model_copy(
        update={
            "durability_evidence": DurabilityEvidence(
                typical_lifespan=Sourced(
                    value=TypicalLifespan(low=Decimal("1.25"), high=Decimal("2.21")),
                    source=TESTER,
                )
            ),
        }
    )

    assert "  Typical for this kind of product: 1.2 to 2.3 years (rtings.com)" in option_lines(
        report_of(pan)
    )


def test_a_typical_lifespan_names_the_type_its_quote_names_and_a_limited_warranty_says_so() -> None:
    pan = CARBON_STEEL.model_copy(
        update={
            "lifespan_source": TESTER,
            "durability_evidence": DurabilityEvidence(
                warranty=Sourced(value=WarrantyTerm(lifetime=True, limited=True), source=MAKER),
                typical_lifespan=Sourced(
                    value=TypicalLifespan(low=Decimal(2), high=Decimal(5), type="Non-stick pans"),
                    source=TESTER,
                ),
            ),
        }
    )

    lines = option_lines(report_of(pan))

    assert "  Warranty: limited lifetime (tefal.nl) (the manufacturer states)" in lines
    assert "  Typical for Non-stick pans: 2 to 5 years (rtings.com)" in lines


FORUM = Source(
    kind=SourceKind.URL,
    reference="https://www.reddit.com/r/cookware/comments/abc",
    stated_by=StatedBy.OWNER,
)
OWNER_REPORT = Finding(
    kind=FindingKind.OWNER_REPORT,
    summary="One owner's handle came loose after about a year",
    source=FORUM,
    rating="4.5/5",
    review_count=1234,
)
TEST = Finding(
    kind=FindingKind.TEST,
    summary="Coating still intact after a year of daily use",
    source=TESTER,
    rating="8.1/10",
)


def reported(option: ProductOption, *findings: Finding, **evidence: object) -> ProductOption:
    state = FindingsState.FOUND if findings else evidence.pop("findings_state")
    durability = DurabilityEvidence(findings=findings, findings_state=state, **evidence)
    return option.model_copy(update={"durability_evidence": durability})


def test_findings_follow_the_evidence_tests_first_each_with_its_site() -> None:
    pan = reported(
        CARBON_STEEL.model_copy(update={"lifespan_source": TESTER}),
        OWNER_REPORT,
        TEST,
        care=Sourced(value="hand wash only", source=TESTER),
    )

    lines = option_lines(report_of(pan))

    start = lines.index("Lifespan: 30 years (rtings.com)")
    assert lines[start + 1 : start + 4] == (
        "  Care: hand wash only (rtings.com)",
        "  Test: Coating still intact after a year of daily use (rtings.com), "
        "overall rating 8.1/10",
        "  Owner report: One owner's handle came loose after about a year (reddit.com), "
        "overall rating 4.5/5 from 1,234 reviews",
    )


def test_a_finding_with_no_rating_ends_with_its_site() -> None:
    plain = OWNER_REPORT.model_copy(update={"rating": None, "review_count": None})

    lines = option_lines(report_of(reported(CARBON_STEEL, plain)))

    assert (
        "  Owner report: One owner's handle came loose after about a year (reddit.com)"
    ) in lines


def test_with_no_findings_the_line_says_whether_they_were_looked_up() -> None:
    none_found = reported(CARBON_STEEL, findings_state=FindingsState.NONE_FOUND)
    not_searched = reported(CARBON_STEEL, findings_state=FindingsState.NOT_SEARCHED)

    assert "  No owner or tester reports found" in option_lines(report_of(none_found))
    assert "  Owner and tester reports not looked up" in option_lines(report_of(not_searched))


def test_a_rough_estimate_with_findings_shows_them_and_not_no_durability_evidence() -> None:
    lines = option_lines(report_of(reported(NON_STICK, TEST)))

    start = lines.index("Lifespan: 2 years (rough estimate)")
    assert lines[start + 1].startswith("  Test: Coating still intact")
    assert "  No durability evidence found" not in lines


def test_a_rough_estimate_with_no_evidence_and_no_findings_has_one_line_for_both() -> None:
    lines = option_lines(report_of(reported(NON_STICK, findings_state=FindingsState.NONE_FOUND)))

    start = lines.index("Lifespan: 2 years (rough estimate)")
    assert lines[start + 1 : start + 3] == ("  No durability evidence found", "Cost per year: €10")


def test_a_rough_estimate_whose_reports_were_not_looked_up_says_so_under_no_evidence() -> None:
    lines = option_lines(report_of(reported(NON_STICK, findings_state=FindingsState.NOT_SEARCHED)))

    start = lines.index("Lifespan: 2 years (rough estimate)")
    assert lines[start + 1 : start + 3] == (
        "  No durability evidence found",
        "  Owner and tester reports not looked up",
    )


def recurring(state: RecurringCostState, **found: object) -> ProductOption:
    return CARBON_STEEL.model_copy(update={"recurring_cost_state": state, **found})


def test_a_recurring_cost_found_shows_its_yearly_amount_and_consumable() -> None:
    kettle = recurring(
        RecurringCostState.FOUND,
        recurring_cost_per_year=Decimal("12"),
        recurring_cost_source=WEB.model_copy(update={"label": "replacement filter"}),
        recurring_cost_converted_from="USD",
        other_consumables_left_out=True,
    )

    assert (
        "Recurring cost: €12 a year, replacement filter (example.com), converted from USD at a "
        "fixed rate, other consumables not counted"
    ) in option_lines(report_of(kettle))


def test_a_recurring_cost_not_found_says_so_and_one_not_looked_for_has_no_line() -> None:
    assert "Recurring cost: recurring costs not found" in option_lines(
        report_of(recurring(RecurringCostState.NOT_FOUND))
    )
    assert not any(
        line.startswith("Recurring cost") for line in option_lines(report_of(CARBON_STEEL))
    )


PAGE = Source(kind=SourceKind.URL, reference="https://shop.example/pan")


def footprint(
    option_id: str, low: str, high: str, *inputs: LcaInput, **changes: object
) -> LcaResult:
    """A model estimate of the option; `changes` replace its fields."""
    parts = model_estimate_parts() | ({"inputs": inputs} if inputs else {})
    return LcaResult(
        option_id=option_id,
        co2e_low=Decimal(low),
        co2e_high=Decimal(high),
        source=MODEL_ESTIMATE,
        **(parts | changes),
    )


# A range widened around its geometric midpoint, as code gives it: sqrt(6) to sqrt(24).
WIDENED_LOW = "2.449489742783178098197284075"
WIDENED_HIGH = "4.898979485566356196394568149"


def test_a_co2e_figure_is_its_range_over_the_horizon_rounded_outward_with_its_label() -> None:
    lines = option_lines(
        report_of(NON_STICK, lca_results=(footprint("non-stick", WIDENED_LOW, WIDENED_HIGH),))
    )

    # Five purchases over the horizon: 12.2 to 24.5 kg, two significant figures, outward.
    assert "CO2e: 12 to 25 kg CO2e to make, over 10 years (AI synthetic estimate)" in lines


def test_a_benchmark_estimate_carries_its_own_label_and_its_dataset() -> None:
    benchmark = LcaResult(
        option_id="non-stick",
        co2e_low=Decimal("4"),
        co2e_high=Decimal("9"),
        tier=2,
        source=Source(kind=SourceKind.DATASET, reference="pans-dataset, row 12"),
        boundary="cradle to gate",
    )

    lines = option_lines(report_of(NON_STICK, lca_results=(benchmark,)))

    assert (
        "CO2e: 20 to 45 kg CO2e to make, over 10 years (benchmark estimate, pans-dataset, row 12)"
    ) in lines
    assert not any("Built from" in line for line in lines)


def test_a_set_names_its_pieces_before_the_label() -> None:
    pans = NON_STICK.model_copy(update={"piece_count": 3})

    lines = option_lines(report_of(pans, lca_results=(footprint("non-stick", "4", "9"),)))

    assert (
        "CO2e: 20 to 45 kg CO2e to make, over 10 years, for the set of 3 (AI synthetic estimate)"
    ) in lines


def test_with_no_lifespan_the_co2e_is_the_range_of_making_one() -> None:
    mystery = ProductOption(id="mystery", name="Mystery pan")

    lines = option_lines(
        report_of(mystery, lca_results=(footprint("mystery", WIDENED_LOW, WIDENED_HIGH),))
    )

    assert "CO2e: 2.4 to 4.9 kg CO2e to make (AI synthetic estimate)" in lines


def test_built_from_lists_each_material_and_marks_what_was_estimated() -> None:
    page_name = STEEL_INPUT.model_copy(
        update={
            "name": "plastic",
            "form": "primary",
            "form_source": MODEL_ESTIMATE,
            "material_source": PAGE,
            "mass_kg": Decimal("0.675"),
        }
    )
    page_all = STEEL_INPUT.model_copy(
        update={
            "name": "stainless steel",
            "form": "recycled",
            "form_source": PAGE,
            "material_source": PAGE,
            "mass_kg": Decimal("0.45"),
            "mass_source": PAGE,
        }
    )
    model_all = STEEL_INPUT.model_copy(
        update={"name": "nichrome", "form": "primary", "form_source": MODEL_ESTIMATE}
    )
    estimate = footprint("non-stick", "4", "9", STEEL_INPUT, page_name, page_all, model_all)

    lines = option_lines(report_of(NON_STICK, lca_results=(estimate,)))

    co2e = lines.index("CO2e: 20 to 45 kg CO2e to make, over 10 years (AI synthetic estimate)")
    assert lines[co2e + 1] == (
        "  Built from: carbon steel (estimated), 1.4 kg (estimated); plastic, primary (estimated), "
        "0.68 kg (estimated); stainless steel, recycled, 0.45 kg; nichrome (estimated), primary "
        "(estimated), 1.4 kg (estimated)"
    )


def test_built_from_names_a_component_without_its_form() -> None:
    element = STEEL_INPUT.model_copy(
        update={
            "name": "heating element",
            "form": "typical",
            "form_source": MODEL_ESTIMATE,
            "component": True,
            "mass_kg": Decimal("0.15"),
        }
    )
    estimate = footprint("non-stick", "4", "9", STEEL_INPUT, element)

    lines = option_lines(report_of(NON_STICK, lca_results=(estimate,)))

    assert "  Built from (estimated): carbon steel, 1.4 kg; heating element, 0.15 kg" in lines


def test_built_from_an_estimate_the_model_made_whole_has_one_mark_after_its_label() -> None:
    nichrome = STEEL_INPUT.model_copy(
        update={"name": "nichrome", "form": "typical", "form_source": MODEL_ESTIMATE}
    )
    estimate = footprint("non-stick", "4", "9", STEEL_INPUT, nichrome)

    lines = option_lines(report_of(NON_STICK, lca_results=(estimate,)))

    assert "  Built from (estimated): carbon steel, 1.4 kg; nichrome, typical, 1.4 kg" in lines


def test_less_co2e_than_the_baseline_follows_the_co2e_with_the_weaker_label() -> None:
    benchmark = LcaResult(
        option_id="non-stick",
        co2e_low=Decimal("4"),
        co2e_high=Decimal("9"),
        tier=2,
        source=Source(kind=SourceKind.DATASET, reference="pans-dataset, row 12"),
        boundary="cradle to gate",
    )
    carbon_steel = footprint("carbon-steel", "5", "10")

    lines = option_lines(report_of(NON_STICK, CARBON_STEEL, lca_results=(benchmark, carbon_steel)))

    # The baseline's 20 to 45 kg against one carbon steel pan's 5 to 10 kg.
    co2e = "CO2e: 5 to 10 kg CO2e to make, over 10 years (AI synthetic estimate)"
    assert lines[lines.index(co2e) :] == (
        co2e,
        "  Built from (estimated): carbon steel, 1.4 kg",
        "Against Non-stick pan: About 10 to 40 kg CO2e less to make over 10 years "
        "(AI synthetic estimate); for scale, about 100 to 420 km in an average new car in Europe, "
        "electric cars included (car figure: EEA, 2025, tailpipe test; real drives emit more)",
    )
    assert not any(line.startswith("Against") for line in lines[: lines.index("Carbon steel pan")])


def test_ranges_that_overlap_give_no_line_for_less_co2e() -> None:
    estimates = (footprint("non-stick", "1", "3"), footprint("carbon-steel", "5", "10"))

    lines = option_lines(report_of(NON_STICK, CARBON_STEEL, lca_results=estimates))

    assert not any(line.startswith("Against") for line in lines)


def test_an_option_out_of_stock_ends_with_its_own_mark_beside_over_your_budget() -> None:
    sold_out = CARBON_STEEL.model_copy(update={"out_of_stock": True})

    lines = option_lines(report_of(NON_STICK, sold_out, budget=Decimal("30")))

    assert lines[-2:] == ("Out of stock when the price was seen", "Over your budget")


def test_an_option_sold_incomplete_says_it_is_not_set_against_the_baseline() -> None:
    bare = CARBON_STEEL.model_copy(update={"incomplete": True})

    lines = option_lines(report_of(NON_STICK, bare))

    assert lines[-1] == (
        "Sold without a part it needs to work, so no savings or CO2e against Non-stick pan "
        "are shown"
    )


def test_an_option_sold_incomplete_with_nothing_to_set_it_against_says_only_that() -> None:
    bare = CARBON_STEEL.model_copy(update={"incomplete": True})

    assert option_lines(report_of(bare))[-1] == "Sold without a part it needs to work"


def test_a_report_with_no_options_has_no_option_lines() -> None:
    assert option_lines(report_of()) == ()


# --- The savings lines ---


def pan(name: str, price: str) -> ProductOption:
    """A pan that lasts longer than the horizon, so its horizon cost is its price."""
    return ProductOption(
        id=name,
        name=name,
        lifespan_years=Decimal("30"),
        lifespan_source=WEB,
        **seen_price(price),
    )


def test_the_worked_example_saves_60_against_the_baseline_on_a_rough_estimate() -> None:
    # The non-stick pan's 2 years are a model estimate.
    assert savings_lines(report_of(NON_STICK, CARBON_STEEL)) == (
        "Over 10 years: Carbon steel pan costs €60 less than Non-stick pan. A lifespan behind "
        "this is a rough estimate.",
    )


def test_an_option_that_costs_more_over_the_horizon_says_so() -> None:
    # The baseline costs €100 over 10 years.
    baseline = NON_STICK.model_copy(update={"lifespan_source": WEB})
    report = report_of(baseline, pan("Cast iron pan", "150"))

    assert savings_lines(report) == (
        "Over 10 years: Cast iron pan costs €50 more than Non-stick pan.",
    )


def test_savings_of_zero_or_missing_give_no_line() -> None:
    report = report_of(
        NON_STICK, pan("Steel pan", "100"), ProductOption(id="mystery", name="Mystery pan")
    )

    assert savings_lines(report) == ()


def test_one_option_alone_has_no_savings_line() -> None:
    assert savings_lines(report_of(NON_STICK)) == ()
    assert savings_lines(report_of()) == ()


# --- The check-before-you-buy list ---

HOB = DecisionFactor(
    id="hob",
    name="Hob compatibility",
    kind=FactorKind.COMPATIBILITY,
    why="Not every pan works on every hob.",
    source=WEB,
)
CARE = DecisionFactor(
    id="care",
    name="Seasoning",
    kind=FactorKind.CARE,
    why="A carbon steel pan needs seasoning to last.",
    source=WEB,
)
HOB_CHOSEN = Answer(factor_id="hob", status=AnswerStatus.CHOSEN, choice_id="induction")


HOB_STATED = Answer(
    factor_id="hob",
    status=AnswerStatus.STATED,
    choice_id="induction",
    stated_value="Induction",
    stated_phrase="for induction",
)
USAGE = DecisionFactor(
    id="usage-1",
    name="Usage frequency",
    kind=FactorKind.USAGE,
    why="It sets the cost per use.",
)
USAGE_STATED = Answer(
    factor_id="usage-1",
    status=AnswerStatus.STATED,
    stated_value="Several times a day",
    stated_phrase="three times a day",
    uses_per_year=1000,
)


def test_each_stated_answer_is_a_line_with_the_request_s_own_words() -> None:
    report = report_of(NON_STICK, factors=(HOB, USAGE), answers=(HOB_STATED, USAGE_STATED))

    assert stated_lines(report) == (
        'From your request: Hob compatibility: Induction ("for induction")',
        'From your request: Several times a day, 1,000 uses a year ("three times a day")',
    )


def test_a_requirement_of_the_users_own_is_a_line_with_only_their_words() -> None:
    battery = DecisionFactor(
        id="user-1",
        name="with a spare battery",
        kind=FactorKind.REQUIREMENT,
        why="You asked for this.",
        source=Source(kind=SourceKind.USER, reference="with a spare battery"),
    )
    stated = Answer(
        factor_id="user-1",
        status=AnswerStatus.STATED,
        stated_value="with a spare battery",
        stated_phrase="with a spare battery",
    )

    report = report_of(NON_STICK, factors=(battery,), answers=(stated,))

    assert stated_lines(report) == ('From your request: "with a spare battery"',)


def test_the_replys_answers_follow_the_requests_each_with_the_replys_own_words() -> None:
    oven_safe = DecisionFactor(
        id="user-1",
        name="oven safe",
        kind=FactorKind.REQUIREMENT,
        why="You asked for this.",
        source=Source(kind=SourceKind.USER, reference="oven safe"),
    )
    from_reply = {"stated_in": StatedIn.REPLY}
    answers = (
        HOB_STATED,
        Answer(
            factor_id="user-1",
            status=AnswerStatus.STATED,
            stated_value="oven safe",
            stated_phrase="oven safe",
            **from_reply,
        ),
        USAGE_STATED.model_copy(update={"stated_phrase": "about once a week", **from_reply}),
        Answer(
            factor_id="care",
            status=AnswerStatus.NOT_SURE,
            stated_phrase="no idea about seasoning",
            **from_reply,
        ),
    )

    report = report_of(NON_STICK, factors=(HOB, CARE, oven_safe, USAGE), answers=answers)

    assert stated_lines(report) == (
        'From your request: Hob compatibility: Induction ("for induction")',
        'From your reply: "oven safe"',
        'From your reply: Several times a day, 1,000 uses a year ("about once a week")',
        'From your reply: Seasoning: not sure ("no idea about seasoning")',
    )


def test_chosen_answers_have_no_stated_line() -> None:
    assert stated_lines(report_of(NON_STICK, factors=(HOB,), answers=(HOB_CHOSEN,))) == ()


def hob_unverified(option: ProductOption) -> ProductOption:
    value = FactorValue(factor_id="hob", fit=Fit.UNVERIFIED, source=ESTIMATE)
    return option.model_copy(update={"factor_values": (value,)})


def test_a_factor_with_no_answer_is_listed_as_not_yet_known() -> None:
    report = report_of(NON_STICK, factors=(HOB,))

    assert check_lines(report) == (
        "Check before you buy",
        "Not yet known",
        "- Hob compatibility: Not every pan works on every hob.",
        "- Confirm the current price: Prices change after the day each was seen.",
    )


def test_a_factor_that_could_not_be_verified_is_one_line_naming_its_options() -> None:
    report = report_of(
        hob_unverified(NON_STICK),
        hob_unverified(CARBON_STEEL),
        factors=(HOB,),
        answers=(HOB_CHOSEN,),
    )

    assert check_lines(report) == (
        "Check before you buy",
        "Could not be confirmed",
        "- Hob compatibility: Not every pan works on every hob. (Non-stick pan, Carbon steel pan)",
        "- Confirm the current price: Prices change after the day each was seen.",
    )


def test_a_factor_of_the_users_own_is_quoted_on_its_option_and_on_the_check_list() -> None:
    # "boils quickly: could not be confirmed" and "- boils quickly: You asked for this." in task
    # 1.10's kettle run.
    own = DecisionFactor(
        id="user-1",
        name="boils quickly",
        kind=FactorKind.REQUIREMENT,
        why="You asked for this.",
        source=Source(kind=SourceKind.USER, reference="boils quickly"),
    )
    unverified = FactorValue(factor_id="user-1", fit=Fit.UNVERIFIED, source=ESTIMATE)
    pan = valued(NON_STICK, unverified)
    stated = Answer(
        factor_id="user-1",
        status=AnswerStatus.STATED,
        stated_value="boils quickly",
        stated_phrase="boils quickly",
    )

    report = report_of(pan, factors=(own,), answers=(stated,))

    assert option_lines(report)[3] == 'You asked for "boils quickly": could not be confirmed'
    assert check_lines(report)[2] == '- "boils quickly": You asked for this. (Non-stick pan)'


def test_both_labels_are_printed_when_both_have_items() -> None:
    report = report_of(
        hob_unverified(NON_STICK), CARBON_STEEL, factors=(HOB, CARE), answers=(HOB_CHOSEN,)
    )

    assert check_lines(report) == (
        "Check before you buy",
        "Not yet known",
        "- Seasoning: A carbon steel pan needs seasoning to last.",
        "Could not be confirmed",
        "- Hob compatibility: Not every pan works on every hob. (Non-stick pan)",
        "- Confirm the current price: Prices change after the day each was seen.",
    )


def test_an_empty_check_list_prints_nothing() -> None:
    unpriced = ProductOption(id="mystery", name="Mystery pan")

    assert check_lines(report_of(unpriced, factors=(HOB,), answers=(HOB_CHOSEN,))) == ()


# --- The trail ---


def test_each_trail_entry_is_one_line_with_what_it_carries() -> None:
    trail = (
        TrailEntry(agent=Agent.TCO, kind=TrailKind.DECIDED, summary="Stub: two fixed frying pans"),
        TrailEntry(
            agent=Agent.SUPERVISOR,
            kind=TrailKind.DECIDED,
            summary="Understood as: frying pan",
            model_tier="small",
            model="example/small-model",
        ),
        TrailEntry(
            agent=Agent.BRIEF, kind=TrailKind.FOUND, summary="Two factors", model_tier="medium"
        ),
        TrailEntry(
            agent=Agent.TCO,
            kind=TrailKind.EXCLUDED,
            summary="Aluminium pan",
            reason="does not work on induction",
            source=WEB,
        ),
    )

    assert trail_lines(report_of(NON_STICK, trail=trail)) == (
        "Trail",
        "tco decided: Stub: two fixed frying pans",
        "supervisor [small, example/small-model] decided: Understood as: frying pan",
        "brief [medium] found: Two factors",
        "tco excluded: Aluminium pan; reason: does not work on induction; "
        "source: https://example.com/pans",
    )


def test_an_empty_trail_prints_nothing() -> None:
    assert trail_lines(report_of(NON_STICK)) == ()


# --- The whole report ---


def test_the_sections_come_in_their_fixed_order_with_an_empty_line_before_each() -> None:
    trail = (TrailEntry(agent=Agent.TCO, kind=TrailKind.DECIDED, summary="Stub"),)
    report = report_of(
        NON_STICK,
        CARBON_STEEL,
        scope=Scope.ENERGY_HEAVY,
        budget=Decimal("10"),
        factors=(HOB, CARE),
        answers=(HOB_STATED,),
        trail=trail,
    )

    lines = printed_report(report)

    first_lines = (
        "Lifespan sourced for 1 of 2 options. CO2e to make: not found for 2.",
        ENERGY_CAVEAT,
        "Nothing found within €10; the cheapest option is €20.",
        'From your request: Hob compatibility: Induction ("for induction")',
        "Non-stick pan",
        "Over 10 years: Carbon steel pan costs €60 less than Non-stick pan. A lifespan behind "
        "this is a rough estimate.",
        "Check before you buy",
        "Trail",
    )
    positions = [lines.index(line) for line in first_lines]
    assert positions == sorted(positions)
    assert positions[0] == 0
    assert all(lines[position - 1] == "" for position in positions[1:])


def test_a_section_with_nothing_to_show_leaves_no_empty_line_behind() -> None:
    lines = printed_report(report_of(NON_STICK))

    assert lines[:3] == (
        "Lifespan sourced for 0 of 1 options. CO2e to make: not found for 1.",
        "",
        "Non-stick pan",
    )
    assert lines[-1] == "- Confirm the current price: Prices change after the day each was seen."


FILTER_GUIDE = Source(kind=SourceKind.URL, reference="https://www.consumentenbond.nl/filters")


def filters(cost: Decimal | None, converted_from: str | None = None) -> DecisionFactor:
    return DecisionFactor(
        id="researched-2",
        name="Filters",
        kind=FactorKind.RECURRING_COST,
        why="Filters have to be bought again.",
        source=FILTER_GUIDE,
        typical_yearly_cost=cost,
        typical_yearly_cost_source=None if cost is None else FILTER_GUIDE,
        typical_yearly_cost_converted_from=converted_from,
    )


def test_a_typical_yearly_cost_is_a_line_with_its_site_labelled_when_converted() -> None:
    report = report_of(NON_STICK, factors=(filters(Decimal("28.8"), "USD"),))

    assert typical_cost_lines(report) == (
        "Filters: typically €28.80 a year (consumentenbond.nl), converted from USD at a fixed "
        "rate.",
    )


def test_a_recurring_cost_factor_with_no_amount_has_no_line_and_stays_on_the_list() -> None:
    report = report_of(NON_STICK, factors=(filters(None),))

    assert typical_cost_lines(report) == ()
    assert "- Filters: Filters have to be bought again." in check_lines(report)
