"""What the checkpointer saves comes back equal, as model instances, for every state type."""

import logging
from datetime import date
from decimal import Decimal

import pytest

from samples import seen_price
from shopper.calc.recalculation import recalculate
from shopper.graph.graph import state_serde
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
    DecisionFactor,
    DurabilityEvidence,
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
    TrailEntry,
    TrailKind,
    TypicalLifespan,
    Warning,
    WarningCode,
    WarrantyTerm,
)

WEB = Source(kind=SourceKind.URL, reference="https://example.com/pans", label="A test page")
ESTIMATE = Source(kind=SourceKind.MODEL_ESTIMATE, reference="test")
REQUEST = Request(
    original_text="a frying pan, budget €50",
    product_url="https://example.com/pan",
    category="frying pan",
    budget=Decimal("50"),
    scope=Scope.TUNED,
)
FACTOR = DecisionFactor(
    id="filter",
    name="Filter cost",
    kind=FactorKind.RECURRING_COST,
    why="Filters are replaced every year.",
    source=WEB,
    typical_yearly_cost=Decimal("12.50"),
    typical_yearly_cost_source=WEB,
)
QUESTION = Question(
    id="q-usage",
    factor_id="usage",
    text="How often will you use it?",
    reason="It sets the cost per use.",
    choices=(Choice(id="daily", text="Every day", uses_per_year=365), Choice(id="no", text="No")),
)
CHOSEN = Answer(factor_id="usage", status=AnswerStatus.CHOSEN, choice_id="daily")
STATED = Answer(
    factor_id="hob",
    status=AnswerStatus.STATED,
    stated_value="induction",
    stated_phrase="for induction",
    uses_per_year=365,
)
MATERIAL = Material(name="steel", form="recycled", mass_kg=Decimal("1.2"), source=WEB)
OPTION = ProductOption(
    id="carbon-steel",
    name="Carbon steel pan",
    price_variant="28 cm",
    piece_count=1,
    **seen_price("40"),
    link="https://example.com/carbon-steel",
    lifespan_years=Decimal("30"),
    lifespan_source=ESTIMATE,
    durability_evidence=DurabilityEvidence(
        warranty=Sourced[WarrantyTerm](value=WarrantyTerm(years=Decimal("2.5")), source=WEB),
        typical_lifespan=Sourced[TypicalLifespan](
            value=TypicalLifespan(low=Decimal("2"), high=Decimal("5")), source=WEB
        ),
        care=Sourced[str](value="Season it", source=WEB),
        findings=(
            Finding(
                kind=FindingKind.OWNER_REPORT,
                summary="One owner's pan was still flat after ten years",
                source=WEB,
                rating="4.5 out of 5",
                review_count=120,
                published_date=date(2025, 3, 1),
            ),
        ),
        findings_state=FindingsState.FOUND,
    ),
    recurring_cost_per_year=Decimal("0.99"),
    recurring_cost_source=WEB,
    recurring_cost_state=RecurringCostState.FOUND,
    recurring_cost_converted_from="USD",
    other_consumables_left_out=True,
    factor_values=(FactorValue(factor_id="hob", value="All hobs", fit=Fit.MEETS, source=WEB),),
    materials=(MATERIAL,),
    weight_kg=Decimal("1.4"),
    weight_source=WEB,
)
LCA_INPUT = LcaInput(
    name="steel",
    form="recycled",
    form_source=ESTIMATE,
    material_source=WEB,
    mass_kg=Decimal("1.2"),
    mass_source=WEB,
    factor_low=Decimal("1.1"),
    factor_high=Decimal("2.4"),
    factor_source=ESTIMATE,
)
HEATING_ELEMENT = LcaInput(
    name="heating element",
    material_source=ESTIMATE,
    component=True,
    mass_kg=Decimal("0.2"),
    mass_source=ESTIMATE,
    factor_low=Decimal("20"),
    factor_high=Decimal("40"),
    factor_source=ESTIMATE,
)
UNKNOWN_OPTION = ProductOption(id="unknown", name="A pan with nothing known")
LCA_RESULT = LcaResult(
    option_id="carbon-steel",
    co2e_low=Decimal("3.1"),
    co2e_high=Decimal("5.9"),
    tier=3,
    source=ESTIMATE,
    boundary=TIER_3_BOUNDARY,
    inputs=(LCA_INPUT, HEATING_ELEMENT),
    manufacturing_low=Decimal("0.8"),
    manufacturing_high=Decimal("1.6"),
    manufacturing_source=ESTIMATE,
)
LISTING = Listing(
    id="listing-1",
    option_id="carbon-steel",
    title="Carbon steel pan, used",
    price=Decimal("18.50"),
    shipping_cost=Decimal("6.95"),
    condition="used",
    link="https://example.com/listing",
    country="NL",
    ships_to_nl=True,
    marketplace="ebay",
)
ASSUMPTIONS = Assumptions(
    horizon_years=15, uses_per_year=50, lifespan_overrides={"carbon-steel": Decimal("12.5")}
)
DECIDED = TrailEntry(
    agent=Agent.SUPERVISOR,
    kind=TrailKind.DECIDED,
    summary="Understood as: frying pan",
    source=WEB,
    model_tier="small",
    model="a-model",
)
EXCLUDED = TrailEntry(
    agent=Agent.TCO, kind=TrailKind.EXCLUDED, summary="Dropped a pan", reason="not for induction"
)
WARNING = Warning(
    code=WarningCode.NOTHING_WITHIN_BUDGET, message="Nothing found", option_id="carbon-steel"
)
COMPARISON, EVIDENCE = recalculate(
    (OPTION, UNKNOWN_OPTION), (LCA_RESULT,), ASSUMPTIONS, REQUEST.budget
)
REPORT = Report(
    request=REQUEST,
    factors=(FACTOR,),
    questions=(QUESTION,),
    answers=(CHOSEN, STATED),
    options=(OPTION, UNKNOWN_OPTION),
    lca_results=(LCA_RESULT,),
    listings=(LISTING,),
    assumptions=ASSUMPTIONS,
    comparison=COMPARISON,
    evidence_summary=EVIDENCE,
    caveats=(Caveat(code=CaveatCode.NOT_TUNED),),
    check_before_you_buy=(
        CheckItem(factor_id="hob", option_id="unknown", reason=CheckReason.UNVERIFIED),
    ),
    trail=(DECIDED, EXCLUDED),
    warnings=(WARNING,),
)
SAMPLES = {
    "request": REQUEST,
    "decision factor": FACTOR,
    "question": QUESTION,
    "chosen answer": CHOSEN,
    "stated answer": STATED,
    "product option": OPTION,
    "LCA input": LCA_INPUT,
    "LCA result": LCA_RESULT,
    "listing": LISTING,
    "assumptions": ASSUMPTIONS,
    "trail entry": DECIDED,
    "exclusion": EXCLUDED,
    "warning": WARNING,
    "report": REPORT,
}


def test_the_sample_report_has_decimals_and_missing_reasons() -> None:
    known, unknown = REPORT.comparison.rows

    assert isinstance(known.cost_per_year, Decimal)
    assert Figure.COST_PER_YEAR in unknown.missing_reasons


@pytest.mark.parametrize("sample", SAMPLES.values(), ids=SAMPLES.keys())
def test_a_saved_value_comes_back_equal_and_of_its_type(
    sample: object, caplog: pytest.LogCaptureFixture
) -> None:
    serde = state_serde()

    with caplog.at_level(logging.WARNING):
        loaded = serde.loads_typed(serde.dumps_typed(sample))

    assert type(loaded) is type(sample)
    assert loaded == sample
    assert caplog.records == []


def test_a_saved_collection_comes_back_as_model_instances() -> None:
    serde = state_serde()

    loaded = serde.loads_typed(serde.dumps_typed((DECIDED, EXCLUDED)))

    assert tuple(loaded) == (DECIDED, EXCLUDED)
    assert all(type(entry) is TrailEntry for entry in loaded)
