"""The report's lines section by section, on reports that `assemble` built: each Line compared as
its parts or as plain text."""

from decimal import Decimal

from samples import MODEL_ESTIMATE, PRICE_SOURCE, STEEL_INPUT, model_estimate_parts, seen_price
from shopper.config import CAR_CO2_SOURCE_URL
from shopper.graph.report import DEFAULT_ASSUMPTIONS, assemble
from shopper.report_lines import (
    CheckGroup,
    CheckLines,
    FactorFigure,
    ReportLines,
    TrailLine,
    WarningLine,
    caveat_lines_of,
    check_lines_of,
    evidence_summary_lines_of,
    option_lines_of,
    report_lines_of,
    source_site,
    trail_lines_of,
    warning_lines_of,
)
from shopper.state import (
    Agent,
    Answer,
    AnswerStatus,
    Assumptions,
    CheckItem,
    CheckReason,
    DecisionFactor,
    DurabilityEvidence,
    FactorKind,
    FactorValue,
    Finding,
    FindingKind,
    FindingsState,
    Fit,
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
    TrailEntry,
    TrailKind,
    Warning,
    WarningCode,
)
from shopper.wording import (
    ConfidencePart,
    FigureLine,
    Line,
    LinkPart,
    TextPart,
    plain_text,
)

ESTIMATE = Source(kind=SourceKind.MODEL_ESTIMATE, reference="test")
WEB = Source(kind=SourceKind.URL, reference="https://www.example.com/pans")
RTINGS = Source(
    kind=SourceKind.URL, reference="https://www.rtings.com/pan", stated_by=StatedBy.TESTER
)
FONQ = Source(kind=SourceKind.URL, reference="https://www.fonq.nl/pan", stated_by=StatedBy.SELLER)
ROUGH = ConfidencePart(text="rough estimate", basis="estimate")
ESTIMATED = ConfidencePart(text="estimated", basis="estimate")
AI_ESTIMATE = ConfidencePart(text="AI synthetic estimate", basis="estimate")
BENCHMARK = ConfidencePart(text="benchmark estimate", basis="benchmark")

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


def text(line: Line | None) -> str | None:
    return None if line is None else plain_text(line)


def shown(figure: FigureLine | None) -> tuple[str, str, bool] | None:
    """A figure as its label's words, its value's words and whether it is missing."""
    if figure is None:
        return None
    return plain_text(figure.label), plain_text(figure.value), figure.missing


def benchmark(option_id: str, low: str, high: str, source: Source) -> LcaResult:
    return LcaResult(
        option_id=option_id,
        co2e_low=Decimal(low),
        co2e_high=Decimal(high),
        tier=2,
        source=source,
        boundary="cradle to gate",
    )


def footprint(option_id: str, low: str, high: str, **changes: object) -> LcaResult:
    """A model estimate of the option; `changes` replace its fields."""
    return LcaResult(
        option_id=option_id,
        co2e_low=Decimal(low),
        co2e_high=Decimal(high),
        source=MODEL_ESTIMATE,
        **(model_estimate_parts() | changes),
    )


# --- The whole report ---


def test_a_report_of_a_request_that_does_not_run_has_its_decline_only() -> None:
    request = Request(original_text="groceries", category="groceries", scope=Scope.NOT_A_PRODUCT)

    lines = report_lines_of(Report(request=request))

    assert text(lines.declined) == (
        "This app covers durable products such as cookware, appliances and tools. "
        """It can't help with "groceries"."""
    )
    assert lines == ReportLines(declined=lines.declined)


def test_a_link_that_gave_no_product_asks_for_its_name() -> None:
    linked = Request(
        original_text="https://shop.example/p/1",
        product_url="https://shop.example/p/1",
        scope=Scope.UNCLEAR,
    )

    assert text(report_lines_of(Report(request=linked)).declined) == (
        "We couldn't read the product at your link. "
        "Name the product to start, for example 'a frying pan, budget €50'."
    )


def test_a_report_with_no_options_has_every_section_but_the_options_and_the_price_line() -> None:
    lines = report_lines_of(report_of(scope=Scope.ENERGY_HEAVY))

    assert lines.declined is None
    assert text(lines.evidence_summary) == "Lifespan sourced for 0 of 0 options."
    assert len(lines.caveats) == 1
    assert lines.options == ()
    assert lines.check.confirm_price is None


# --- The evidence summary, the caveats and the warnings ---


def test_the_evidence_summary_is_one_line_of_counts() -> None:
    assert text(evidence_summary_lines_of(report_of(NON_STICK, CARBON_STEEL))) == (
        "Lifespan sourced for 1 of 2 options. CO2e to make: not found for 2."
    )


def test_a_caveat_is_one_text_part() -> None:
    (caveat,) = caveat_lines_of(report_of(NON_STICK, scope=Scope.GENERAL))

    assert caveat == Line(
        parts=(TextPart(text="This category is not one the app is tuned for; check the sources."),)
    )


def test_a_warning_carries_its_code_and_option_and_its_message_as_one_text_part() -> None:
    message = "We couldn't estimate the CO2e of making Non-stick pan, so no CO2e figure is shown."
    warning = Warning(code=WarningCode.CO2E_UNAVAILABLE, message=message, option_id="non-stick")

    assert warning_lines_of(report_of(NON_STICK, warnings=(warning,))) == (
        WarningLine(
            code=WarningCode.CO2E_UNAVAILABLE,
            option_id="non-stick",
            line=Line(parts=(TextPart(text=message),)),
        ),
    )


# --- The options ---


def test_each_figure_of_the_worked_example_is_a_label_and_a_value() -> None:
    report = report_of(
        NON_STICK, CARBON_STEEL, budget=Decimal("30"), assumptions=Assumptions(uses_per_year=50)
    )

    non_stick, carbon_steel = option_lines_of(report)

    assert non_stick.option_id == "non-stick"
    assert [
        shown(figure)
        for figure in (
            non_stick.price,
            non_stick.lifespan,
            non_stick.cost_per_year,
            non_stick.cost_per_use,
            non_stick.purchases,
            non_stick.horizon_cost,
            non_stick.co2e,
        )
    ] == [
        ("Price", "€20", False),
        ("Lifespan", "2 years (rough estimate)", False),
        ("Cost per year", "€10", False),
        ("Cost per use", "€0.20", False),
        ("Purchases over 10 years", "5", False),
        ("Cost over 10 years", "€100", False),
        ("CO2e", "not available (no CO2e estimate for this option)", True),
    ]
    assert non_stick.over_budget is None
    assert text(carbon_steel.over_budget) == "Over your budget"


def test_a_price_from_a_web_page_has_its_shipping_and_where_it_was_seen_linked() -> None:
    pan = NON_STICK.model_copy(update={"price_variant": "28 cm", "shipping": Decimal("4.95")})

    (lines,) = option_lines_of(report_of(pan))

    assert shown(lines.price) == ("Price", "€20 (28 cm)", False)
    assert text(lines.shipping) == "plus €4.95 shipping"
    assert lines.price_seen == Line(
        parts=(
            TextPart(text="price seen at "),
            LinkPart(text="example.com", url=PRICE_SOURCE.reference),
            TextPart(text=" on 17 October 2026"),
        )
    )


def test_a_price_not_from_a_web_page_has_no_shipping_or_where_it_was_seen() -> None:
    (lines,) = option_lines_of(report_of(NON_STICK.model_copy(update={"price_source": ESTIMATE})))

    assert (lines.shipping, lines.price_seen) == (None, None)


def test_an_option_with_a_link_has_its_name_linked_and_a_link_figure() -> None:
    url = "https://www.bol.com/nl/nl/p/pan/1"

    (lines,) = option_lines_of(report_of(NON_STICK.model_copy(update={"link": url})))

    assert lines.name == Line(parts=(LinkPart(text="Non-stick pan", url=url),))
    assert lines.link == FigureLine(
        label=Line(parts=(TextPart(text="Link"),)), value=Line(parts=(LinkPart(text=url, url=url),))
    )


def test_an_option_with_no_link_has_its_name_as_words_and_no_link_figure() -> None:
    (lines,) = option_lines_of(report_of(NON_STICK))

    assert lines.name == Line(parts=(TextPart(text="Non-stick pan"),))
    assert lines.link is None


def test_a_rough_estimate_of_a_lifespan_is_a_confidence_part() -> None:
    (lines,) = option_lines_of(report_of(NON_STICK))

    assert lines.lifespan.value == Line(
        parts=(TextPart(text="2 years ("), ROUGH, TextPart(text=")"))
    )


def test_a_lifespan_the_user_set_says_so_as_words() -> None:
    assumptions = Assumptions(lifespan_overrides={"non-stick": Decimal("4")})

    (lines,) = option_lines_of(report_of(NON_STICK, assumptions=assumptions))

    assert lines.lifespan.value == Line(parts=(TextPart(text="4 years (set by you)"),))


def test_a_missing_lifespan_and_what_it_blocks_are_missing_and_say_to_set_one() -> None:
    (lines,) = option_lines_of(report_of(ProductOption(id="mystery", name="Mystery pan")))

    not_read = "not available (durability evidence could not be read; set a lifespan to see it)"
    assert shown(lines.lifespan) == ("Lifespan", not_read, True)
    assert shown(lines.purchases) == ("Purchases over 10 years", not_read, True)
    assert shown(lines.price) == ("Price", "not available (price not known)", True)


HOB = DecisionFactor(
    id="hob", name="Hob compatibility", kind=FactorKind.COMPATIBILITY, why="w", source=RTINGS
)
LID = DecisionFactor(
    id="lid", name="Lid included", kind=FactorKind.REQUIREMENT, why="w", source=RTINGS
)


def test_each_factor_value_is_a_figure_by_its_factor_with_its_site_linked() -> None:
    values = (
        FactorValue(factor_id="lid", fit=Fit.UNVERIFIED, source=ESTIMATE),
        FactorValue(factor_id="hob", value="works on induction", fit=Fit.MEETS, source=FONQ),
    )
    pan = NON_STICK.model_copy(update={"factor_values": values})

    (lines,) = option_lines_of(report_of(pan, factors=(HOB, LID)))

    hob, lid = lines.factor_values
    assert hob == FactorFigure(
        factor_id="hob",
        figure=FigureLine(
            label=Line(parts=(TextPart(text="Hob compatibility"),)),
            value=Line(
                parts=(
                    TextPart(text="works on induction ("),
                    LinkPart(text="fonq.nl", url=FONQ.reference),
                    TextPart(text=") (the seller states)"),
                )
            ),
        ),
    )
    assert (lid.factor_id, shown(lid.figure)) == (
        "lid",
        ("Lid included", "could not be confirmed", True),
    )


def test_what_a_lifespan_rests_on_is_its_items_and_findings_then_their_state() -> None:
    test = Finding(kind=FindingKind.TEST, summary="Coating intact", source=RTINGS, rating="8/10")
    evidence = DurabilityEvidence(
        care=Sourced(value="hand wash only", source=RTINGS),
        findings=(test,),
        findings_state=FindingsState.FOUND,
    )
    pan = CARBON_STEEL.model_copy(update={"durability_evidence": evidence})

    (lines,) = option_lines_of(report_of(pan))

    assert [shown(figure) for figure in lines.rests_on] == [
        ("Care", "hand wash only (rtings.com)", False),
        ("Test", "Coating intact (rtings.com), overall rating 8/10", False),
    ]
    assert lines.rests_on[1].value.parts[1] == LinkPart(text="rtings.com", url=RTINGS.reference)
    assert lines.rests_on_state == ()


def test_a_rough_estimate_with_no_evidence_has_its_state_lines_only() -> None:
    (lines,) = option_lines_of(report_of(NON_STICK))

    assert lines.rests_on == ()
    assert [text(line) for line in lines.rests_on_state] == [
        "No durability evidence found",
        "Owner and tester reports not looked up",
    ]


def test_a_recurring_cost_not_found_is_missing_and_one_not_looked_for_has_no_figure() -> None:
    not_found = NON_STICK.model_copy(update={"recurring_cost_state": RecurringCostState.NOT_FOUND})

    (lines,) = option_lines_of(report_of(not_found))
    (plain,) = option_lines_of(report_of(NON_STICK))

    assert shown(lines.recurring_cost) == ("Recurring cost", "recurring costs not found", True)
    assert plain.recurring_cost is None


def test_the_co2e_over_the_horizon_carries_the_label_of_its_tier() -> None:
    (lines,) = option_lines_of(
        report_of(NON_STICK, lca_results=(footprint("non-stick", "4", "9"),))
    )

    assert lines.co2e.value == Line(
        parts=(
            TextPart(text="20 to 45 kg CO2e to make, over 10 years ("),
            AI_ESTIMATE,
            TextPart(text=")"),
        )
    )
    assert lines.co2e.missing is False


def test_with_no_lifespan_the_co2e_of_making_one_is_not_missing() -> None:
    mystery = ProductOption(id="mystery", name="Mystery pan")

    (lines,) = option_lines_of(report_of(mystery, lca_results=(footprint("mystery", "4", "9"),)))

    assert shown(lines.co2e) == (
        "CO2e",
        "4 to 9 kg CO2e to make (AI synthetic estimate)",
        False,
    )


def test_a_benchmark_names_its_dataset_and_a_published_figure_links_its_site() -> None:
    dataset = Source(kind=SourceKind.DATASET, reference="pans-dataset, row 12")
    published = benchmark("carbon-steel", "1", "2", WEB).model_copy(update={"tier": 1})
    report = report_of(
        NON_STICK, CARBON_STEEL, lca_results=(benchmark("non-stick", "4", "9", dataset), published)
    )

    non_stick, carbon_steel = option_lines_of(report)

    assert non_stick.co2e.value.parts[1:] == (
        BENCHMARK,
        TextPart(text=", pans-dataset, row 12)"),
    )
    assert carbon_steel.co2e.value.parts[2:4] == (
        TextPart(text=", "),
        LinkPart(text="example.com", url=WEB.reference),
    )


def test_less_co2e_than_the_baseline_carries_the_weaker_label_of_the_two() -> None:
    dataset = Source(kind=SourceKind.DATASET, reference="pans-dataset, row 12")
    report = report_of(
        NON_STICK,
        CARBON_STEEL,
        lca_results=(
            benchmark("non-stick", "4", "9", dataset),
            footprint("carbon-steel", "5", "10"),
        ),
    )

    non_stick, carbon_steel = option_lines_of(report)

    assert non_stick.co2e.value.parts[1] == BENCHMARK
    assert non_stick.co2e_less is None
    assert carbon_steel.co2e.value.parts[1] == AI_ESTIMATE
    assert shown(carbon_steel.co2e_less) == (
        "Against Non-stick pan",
        "About 10 to 40 kg CO2e less to make over 10 years (AI synthetic estimate); for scale, "
        "about 100 to 420 km in an average new car in Europe, electric cars included "
        "(car figure: EEA, 2025, tailpipe test; real drives emit more)",
        False,
    )
    assert carbon_steel.co2e_less is not None
    assert carbon_steel.co2e_less.value.parts[1] == AI_ESTIMATE
    assert carbon_steel.co2e_less.value.parts[3] == LinkPart(text="EEA", url=CAR_CO2_SOURCE_URL)


def test_the_kilometres_stand_only_beside_the_difference_and_not_when_it_is_too_small() -> None:
    report = report_of(
        NON_STICK,
        CARBON_STEEL,
        # The baseline's 0.5 to 0.75 kg against one pan's 0.05 to 0.1 kg: at most 0.7 kg, 7 km.
        lca_results=(
            footprint("non-stick", "0.1", "0.15"),
            footprint("carbon-steel", "0.05", "0.1"),
        ),
    )

    non_stick, carbon_steel = option_lines_of(report)

    assert "km" not in plain_text(non_stick.co2e.value)
    assert "km" not in plain_text(carbon_steel.co2e.value)
    assert carbon_steel.co2e_less is not None
    assert "for scale" not in plain_text(carbon_steel.co2e_less.value)


def test_built_from_marks_each_part_the_model_estimated_with_a_confidence_part() -> None:
    page_steel = STEEL_INPUT.model_copy(
        update={"name": "stainless steel", "material_source": WEB, "mass_source": WEB}
    )
    estimate = footprint("non-stick", "4", "9", inputs=(page_steel, STEEL_INPUT))

    (lines,) = option_lines_of(report_of(NON_STICK, lca_results=(estimate,)))

    assert lines.built_from == FigureLine(
        label=Line(parts=(TextPart(text="Built from"),)),
        value=Line(
            parts=(
                TextPart(text="stainless steel, 1.4 kg; carbon steel ("),
                ESTIMATED,
                TextPart(text="), 1.4 kg ("),
                ESTIMATED,
                TextPart(text=")"),
            )
        ),
    )


def test_built_from_an_estimate_the_model_made_whole_marks_its_label() -> None:
    (lines,) = option_lines_of(
        report_of(NON_STICK, lca_results=(footprint("non-stick", "4", "9"),))
    )

    assert lines.built_from is not None
    assert lines.built_from.label == Line(
        parts=(TextPart(text="Built from ("), ESTIMATED, TextPart(text=")"))
    )
    assert text(lines.built_from.value) == "carbon steel, 1.4 kg"


def test_an_option_set_against_the_baseline_has_its_savings_and_the_baseline_none() -> None:
    non_stick, carbon_steel = option_lines_of(report_of(NON_STICK, CARBON_STEEL))

    assert non_stick.savings is None
    assert text(carbon_steel.savings) == (
        "Over 10 years: Carbon steel pan costs €60 less than Non-stick pan. A lifespan behind "
        "this is a rough estimate."
    )


def test_the_marks_of_an_option_sold_incomplete_and_out_of_stock() -> None:
    bare = CARBON_STEEL.model_copy(update={"incomplete": True, "out_of_stock": True})

    _, lines = option_lines_of(report_of(NON_STICK, bare))

    assert [text(line) for line in lines.marks] == [
        "Out of stock when the price was seen",
        "Sold without a part it needs to work, so no savings or CO2e against Non-stick pan are "
        "shown",
    ]


# --- The check list ---


def test_the_check_list_groups_its_items_and_leaves_out_an_empty_group() -> None:
    report = report_of(NON_STICK, factors=(HOB, LID)).model_copy(
        update={
            "check_before_you_buy": (
                CheckItem(factor_id="lid", option_id="non-stick", reason=CheckReason.UNVERIFIED),
                CheckItem(reason=CheckReason.PRICE, option_id="non-stick"),
            )
        }
    )

    assert check_lines_of(report) == CheckLines(
        groups=(
            CheckGroup(
                label=Line(parts=(TextPart(text="Could not be confirmed"),)),
                items=(Line(parts=(TextPart(text="Lid included: w (Non-stick pan)"),)),),
            ),
        ),
        confirm_price=Line(
            parts=(
                TextPart(
                    text="Confirm the current price: Prices change after the day each was seen."
                ),
            )
        ),
    )


def test_a_factor_with_no_answer_is_not_yet_known() -> None:
    answer = Answer(factor_id="hob", status=AnswerStatus.SKIPPED)

    check = check_lines_of(report_of(NON_STICK, factors=(HOB,), answers=(answer,)))

    assert [
        (text(group.label), [text(item) for item in group.items]) for group in check.groups
    ] == [("Not yet known", ["Hob compatibility: w"])]


# --- The trail ---


def test_each_trail_entry_is_who_wrote_it_and_the_rest_with_a_web_source_linked() -> None:
    trail = (
        TrailEntry(
            agent=Agent.SUPERVISOR,
            kind=TrailKind.DECIDED,
            summary="Understood as: frying pan",
            model_tier="small",
            model="example/small-model",
        ),
        TrailEntry(
            agent=Agent.TCO,
            kind=TrailKind.EXCLUDED,
            summary="Aluminium pan",
            reason="does not work on induction",
            source=WEB,
        ),
        TrailEntry(agent=Agent.LCA, kind=TrailKind.FOUND, summary="Steel", source=MODEL_ESTIMATE),
    )

    supervisor, tco, lca = trail_lines_of(report_of(NON_STICK, trail=trail))

    assert supervisor == TrailLine(
        agent=Agent.SUPERVISOR,
        by=Line(parts=(TextPart(text="supervisor [small, example/small-model]"),)),
        line=Line(parts=(TextPart(text="decided: Understood as: frying pan"),)),
    )
    assert text(tco.by) == "tco"
    assert tco.line == Line(
        parts=(
            TextPart(text="excluded: Aluminium pan; reason: does not work on induction; source: "),
            LinkPart(text=WEB.reference, url=WEB.reference),
        )
    )
    assert text(lca.line) == "found: Steel; source: model estimate"
    assert all(isinstance(part, TextPart) for part in lca.line.parts)


# --- Links ---


def test_a_site_is_a_link_only_for_a_web_address() -> None:
    assert source_site(WEB) == LinkPart(text="example.com", url=WEB.reference)
    assert source_site(Source(kind=SourceKind.URL, reference="javascript:alert(1)")) == (
        "javascript:alert(1)"
    )
    assert source_site(Source(kind=SourceKind.DATASET, reference="pans-dataset")) == "pans-dataset"
