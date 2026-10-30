"""Domain models, defined once. Terms are in GLOSSARY.md; rules in docs/architecture/agents.md.

Only what is always true is validated here. Ids are assigned by code, never by a model.
Money is a `Decimal` in EUR (docs/adr/0001-euro-only.md).
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shopper.config import Tier

Currency = Literal["EUR"]
PositiveDecimal = Annotated[Decimal, Field(gt=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Count = Annotated[int, Field(ge=0)]

# The researched factors the brief agent keeps, the one about how often the product is used, and
# the user's own: requirements the request states that fit no researched factor.
MAX_RESEARCHED_FACTORS = 8
MAX_USER_FACTORS = 3
MAX_FACTORS = MAX_RESEARCHED_FACTORS + 1 + MAX_USER_FACTORS
MAX_RESEARCHED_QUESTIONS = 4
MAX_QUESTIONS = MAX_RESEARCHED_QUESTIONS + 1
MIN_CHOICES = 2
MAX_CHOICES = 4
DEFAULT_HORIZON_YEARS = 10


class DomainModel(BaseModel):
    # A model as the API sends it always has every field, so its OpenAPI schema says so: the
    # frontend's generated types then need no check for a field with a default.
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_serialization_defaults_required=True
    )


class SourceKind(StrEnum):
    URL = "url"
    DATASET = "dataset"
    MODEL_ESTIMATE = "model_estimate"
    USER = "user"


class StatedBy(StrEnum):
    """Who is speaking in a web source, as the model that read it judged."""

    TESTER = "tester"
    OWNER = "owner"
    MANUFACTURER = "manufacturer"
    SELLER = "seller"


class Source(DomainModel):
    """Where a stated value came from. `stated_by` is known only for a web source that was read."""

    kind: SourceKind
    reference: str
    label: str | None = None
    stated_by: StatedBy | None = None


def _require_both_or_neither(value: object, source: Source | None, name: str) -> None:
    """Raise unless a value and its source are both present or both missing."""
    if (value is None) != (source is None):
        raise ValueError(f"{name} and its source are given together or not at all")


class Scope(StrEnum):
    TUNED = "tuned"
    GENERAL = "general"
    ENERGY_HEAVY = "energy_heavy"
    CLOTHING = "clothing"
    NOT_A_PRODUCT = "not_a_product"
    SEVERAL_PRODUCTS = "several_products"
    UNCLEAR = "unclear"


SCOPES_WITHOUT_CATEGORY = frozenset({Scope.UNCLEAR, Scope.SEVERAL_PRODUCTS})
SCOPES_THAT_DO_NOT_RUN = frozenset({Scope.NOT_A_PRODUCT, Scope.SEVERAL_PRODUCTS, Scope.UNCLEAR})


class Request(DomainModel):
    original_text: str
    product_url: str | None = None
    category: str | None = None
    budget: PositiveDecimal | None = None
    currency: Currency = "EUR"
    scope: Scope

    @model_validator(mode="after")
    def _scope_without_a_category_has_none(self) -> Self:
        if self.scope in SCOPES_WITHOUT_CATEGORY and self.category is not None:
            raise ValueError(f"a request with scope '{self.scope}' has no category")
        return self


# The currencies a recurring cost may be converted from (docs/adr/0002).
ConvertedCurrency = Literal["USD", "GBP"]
# The LCA tier: 1 published figure, 2 benchmark, 3 model estimate. A higher number is weaker.
LcaTier = Literal[1, 2, 3]


class FactorKind(StrEnum):
    COMPATIBILITY = "compatibility"
    REQUIREMENT = "requirement"
    RECURRING_COST = "recurring_cost"
    CARE = "care"
    USAGE = "usage"


class DecisionFactor(DomainModel):
    """A researched factor's source is a web URL, the user's own factor's is the user, and the
    factor of kind usage has none. Only a recurring-cost factor has a typical yearly cost, in
    euro, converted at a fixed rate when its source stated USD or GBP."""

    id: str
    name: str
    kind: FactorKind
    why: str
    source: Source | None = None
    typical_yearly_cost: NonNegativeDecimal | None = None
    typical_yearly_cost_source: Source | None = None
    typical_yearly_cost_converted_from: ConvertedCurrency | None = None

    @model_validator(mode="after")
    def _source_is_a_url_or_the_user_unless_usage(self) -> Self:
        if self.kind is FactorKind.USAGE:
            if self.source is not None:
                raise ValueError("the factor of kind usage has no source")
            return self
        if self.source is not None and self.source.kind is SourceKind.USER:
            if self.kind is not FactorKind.REQUIREMENT:
                raise ValueError("a factor the user stated is of kind requirement")
            return self
        if (
            self.source is None
            or self.source.kind is not SourceKind.URL
            or not self.source.reference.startswith(("http://", "https://"))
        ):
            raise ValueError("a decision factor's source is a web URL or the user")
        return self

    @model_validator(mode="after")
    def _typical_yearly_cost_is_sourced(self) -> Self:
        _require_both_or_neither(
            self.typical_yearly_cost, self.typical_yearly_cost_source, "typical yearly cost"
        )
        has_cost = self.typical_yearly_cost is not None
        if has_cost and self.kind is not FactorKind.RECURRING_COST:
            raise ValueError("only a recurring-cost factor has a typical yearly cost")
        if self.typical_yearly_cost_converted_from is not None and not has_cost:
            raise ValueError("only a typical yearly cost is converted")
        return self


# The choice of a care question that declines the care (interview.md, "How answers are used").
CARE_AVOID_CHOICE_ID = "care-avoid"


class Choice(DomainModel):
    id: str
    text: str
    uses_per_year: PositiveInt | None = None


class Question(DomainModel):
    id: str
    factor_id: str
    text: str
    reason: str
    choices: tuple[Choice, ...] = Field(min_length=MIN_CHOICES, max_length=MAX_CHOICES)


class AnswerStatus(StrEnum):
    CHOSEN = "chosen"
    STATED = "stated"
    NOT_SURE = "not_sure"
    SKIPPED = "skipped"


class StatedIn(StrEnum):
    """Where the user's own words of an answer stand: the request, or the reply to the
    questions."""

    REQUEST = "request"
    REPLY = "reply"


class Answer(DomainModel):
    """What is known about one decision factor. "Not sure" is a status, not a choice.

    Only a stated answer, or a "not sure" read in the reply, comes from the reply; that "not sure"
    keeps the phrase it was read from.
    """

    factor_id: str
    status: AnswerStatus
    choice_id: str | None = None
    stated_value: str | None = None
    stated_phrase: str | None = None
    uses_per_year: PositiveInt | None = None
    stated_in: StatedIn = StatedIn.REQUEST

    @model_validator(mode="after")
    def _content_matches_status(self) -> Self:
        has_choice = self.choice_id is not None
        has_value = self.stated_value is not None
        has_phrase = self.stated_phrase is not None
        from_reply = self.stated_in is StatedIn.REPLY
        expected = {
            AnswerStatus.CHOSEN: has_choice and not has_value and not has_phrase and not from_reply,
            # A stated answer carries a choice when code mapped its value onto one.
            AnswerStatus.STATED: has_value and has_phrase,
            AnswerStatus.NOT_SURE: not has_choice and not has_value and has_phrase == from_reply,
            AnswerStatus.SKIPPED: not (has_choice or has_value or has_phrase or from_reply),
        }
        if not expected[self.status]:
            raise ValueError(
                "a chosen answer has a choice, a stated answer has a value and its phrase, a "
                "not-sure answer read in the reply has its phrase alone, and any other not-sure "
                "or skipped answer has none; only a stated or not-sure answer is from the reply"
            )
        return self


class Sourced[T](DomainModel):
    value: T
    source: Source


class Fit(StrEnum):
    MEETS = "meets"
    FAILS = "fails"
    UNVERIFIED = "unverified"


class FactorValue(DomainModel):
    """A `meets` or `fails` says what its source states; an `unverified` value has no text."""

    factor_id: str
    value: str | None = None
    fit: Fit
    source: Source

    @model_validator(mode="after")
    def _text_exactly_when_settled(self) -> Self:
        if (self.value is None) != (self.fit is Fit.UNVERIFIED):
            raise ValueError("a factor value has its text exactly when its fit is not unverified")
        return self


class Material(DomainModel):
    name: str
    form: str | None = None
    mass_kg: Decimal | None = None
    source: Source


class FindingKind(StrEnum):
    TEST = "test"
    OWNER_REPORT = "owner_report"


class Finding(DomainModel):
    """One thing a tester or an owner reported, as a summary in the app's own words; the quote
    behind it is never kept (docs/adr/0005-findings-summarised-quote-logged.md). The rating is
    kept as the source states it, and an owner report's rating only with its review count."""

    kind: FindingKind
    summary: str
    source: Source
    rating: str | None = None
    review_count: Count | None = None
    published_date: date | None = None

    @model_validator(mode="after")
    def _an_owner_rating_has_its_review_count(self) -> Self:
        if self.kind is FindingKind.OWNER_REPORT and self.rating and self.review_count is None:
            raise ValueError("an owner report's rating is kept only with its review count")
        return self


class FindingsState(StrEnum):
    """Whether findings were found, looked for and none found, or not looked up
    (option_evidence.md, "Findings")."""

    FOUND = "found"
    NONE_FOUND = "none_found"
    NOT_SEARCHED = "not_searched"


class WarrantyTerm(DomainModel):
    """A warranty of a number of years, or for a lifetime; `limited` when its quote says so, as a
    "limited lifetime warranty" that excludes wear does."""

    years: PositiveDecimal | None = None
    lifetime: bool = False
    limited: bool = False

    @model_validator(mode="after")
    def _years_or_a_lifetime(self) -> Self:
        if (self.years is not None) != self.lifetime:
            return self
        raise ValueError("a warranty is a number of years or a lifetime, not both or neither")


class TypicalLifespan(DomainModel):
    """The lifespan typical for a kind of product, as a range of years, with the kind its quote
    names ("non-stick pans") when it names one."""

    low: PositiveDecimal
    high: PositiveDecimal
    type: str | None = None

    @model_validator(mode="after")
    def _low_is_not_above_high(self) -> Self:
        if self.low > self.high:
            raise ValueError("the low end of a range is not above its high end")
        return self


class DurabilityEvidence(DomainModel):
    """What supports a lifespan: one item per kind, the lifespan typical for the type, and what
    testers and owners report, with the state that says why there are none."""

    warranty: Sourced[WarrantyTerm] | None = None
    repairability: Sourced[str] | None = None
    wear_material: Sourced[str] | None = None
    care: Sourced[str] | None = None
    typical_lifespan: Sourced[TypicalLifespan] | None = None
    findings: tuple[Finding, ...] = ()
    findings_state: FindingsState = FindingsState.NOT_SEARCHED

    @model_validator(mode="after")
    def _found_exactly_when_there_are_findings(self) -> Self:
        if bool(self.findings) != (self.findings_state is FindingsState.FOUND):
            raise ValueError("the findings state is found exactly when there are findings")
        return self


class RecurringCostState(StrEnum):
    """Whether a recurring cost was found, looked for and not found, or not looked for because
    the category has no consumables (option_research.md, "Recurring cost")."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    NOT_LOOKED_FOR = "not_looked_for"


class ProductOption(DomainModel):
    """A product the comparison is about. Its price comes with where and when it was seen, and
    the size or variant it was quoted for when the source states one. `shipping` is the shipping
    the offer states, missing when it states none. `out_of_stock` marks an option no offer has
    in stock, and `incomplete` one sold without a part it needs to work (option_research.md,
    "Selection")."""

    id: str
    name: str
    brand: str | None = None
    price: NonNegativeDecimal | None = None
    price_source: Source | None = None
    price_seen_on: date | None = None
    price_variant: str | None = None
    shipping: NonNegativeDecimal | None = None
    out_of_stock: bool = False
    incomplete: bool = False
    currency: Currency = "EUR"
    link: str | None = None
    piece_count: PositiveInt | None = None
    lifespan_years: PositiveDecimal | None = None
    lifespan_source: Source | None = None
    durability_evidence: DurabilityEvidence = DurabilityEvidence()
    recurring_cost_per_year: NonNegativeDecimal | None = None
    recurring_cost_source: Source | None = None
    recurring_cost_state: RecurringCostState = RecurringCostState.NOT_LOOKED_FOR
    recurring_cost_converted_from: ConvertedCurrency | None = None
    other_consumables_left_out: bool = False
    factor_values: tuple[FactorValue, ...] = ()
    materials: tuple[Material, ...] = ()
    weight_kg: PositiveDecimal | None = None
    weight_source: Source | None = None

    @model_validator(mode="after")
    def _price_lifespan_and_recurring_cost_are_sourced(self) -> Self:
        given = (self.price is None, self.price_source is None, self.price_seen_on is None)
        if len(set(given)) > 1:
            raise ValueError("a price, its source and the date it was seen are given together")
        if self.shipping is not None and self.price is None:
            raise ValueError("only a price has a shipping cost")
        _require_both_or_neither(self.lifespan_years, self.lifespan_source, "lifespan")
        _require_both_or_neither(self.weight_kg, self.weight_source, "weight")
        _require_both_or_neither(
            self.recurring_cost_per_year, self.recurring_cost_source, "recurring cost"
        )
        found = self.recurring_cost_state is RecurringCostState.FOUND
        if found != (self.recurring_cost_per_year is not None):
            raise ValueError("a recurring cost is found exactly when it has a value")
        if not found and (self.recurring_cost_converted_from or self.other_consumables_left_out):
            raise ValueError("only a recurring cost found is converted or leaves others out")
        return self


class LcaInput(DomainModel):
    """One material of an estimate: its mass and its emission factor range in kg CO2e per kg.

    The form has its own source: a page can name a material and leave its form to the model. A
    separate component (electronics, a motor, a battery) keeps its mass when the masses are
    scaled to the product's stated weight (docs/architecture/calculations.md).
    """

    name: str
    form: str | None = None
    form_source: Source | None = None
    material_source: Source
    component: bool = False
    mass_kg: PositiveDecimal
    mass_source: Source
    factor_low: PositiveDecimal
    factor_high: PositiveDecimal
    factor_source: Source

    @model_validator(mode="after")
    def _factor_is_a_range_and_a_form_has_its_source(self) -> Self:
        if self.factor_low > self.factor_high:
            raise ValueError("factor_low is not above factor_high")
        _require_both_or_neither(self.form, self.form_source, "form")
        return self


# What a model estimate covers, fixed by code
# (docs/adr/0006-tier-3-returns-factors-code-multiplies.md).
TIER_3_BOUNDARY = "cradle to gate: materials and manufacturing"


class LcaResult(DomainModel):
    """A CO2e range in kg per unit. An option with no estimate has no LCA result at all.

    A model estimate (tier 3) always has inputs, a manufacturing and assembly range and the
    fixed boundary; a benchmark may cover materials only.
    """

    option_id: str
    co2e_low: NonNegativeDecimal
    co2e_high: NonNegativeDecimal
    tier: LcaTier
    source: Source
    boundary: str
    inputs: tuple[LcaInput, ...] = ()
    manufacturing_low: NonNegativeDecimal | None = None
    manufacturing_high: NonNegativeDecimal | None = None
    manufacturing_source: Source | None = None

    @model_validator(mode="after")
    def _low_is_not_above_high(self) -> Self:
        if self.co2e_low > self.co2e_high:
            raise ValueError("co2e_low is not above co2e_high")
        return self

    @model_validator(mode="after")
    def _manufacturing_is_a_sourced_range(self) -> Self:
        given = {
            field is not None
            for field in (
                self.manufacturing_low,
                self.manufacturing_high,
                self.manufacturing_source,
            )
        }
        if len(given) > 1:
            raise ValueError(
                "a manufacturing range and its source are given together or not at all"
            )
        if self.manufacturing_low is not None and self.manufacturing_high is not None:
            if self.manufacturing_low > self.manufacturing_high:
                raise ValueError("manufacturing_low is not above manufacturing_high")
        return self

    @model_validator(mode="after")
    def _model_estimate_is_complete(self) -> Self:
        if self.tier == 3 and (
            not self.inputs or self.manufacturing_source is None or self.boundary != TIER_3_BOUNDARY
        ):
            raise ValueError("a model estimate has inputs, manufacturing and the fixed boundary")
        return self


class Listing(DomainModel):
    """A used or refurbished item. A missing shipping cost means unknown, not free."""

    id: str
    option_id: str | None = None
    title: str
    price: NonNegativeDecimal
    shipping_cost: NonNegativeDecimal | None = None
    currency: Currency = "EUR"
    condition: str
    link: str
    country: str
    ships_to_nl: bool
    marketplace: str


class Assumptions(DomainModel):
    """The values the user may change. An override never replaces the option's own lifespan."""

    horizon_years: PositiveInt = DEFAULT_HORIZON_YEARS
    uses_per_year: PositiveInt | None = None
    lifespan_overrides: dict[str, PositiveDecimal] = {}


class Agent(StrEnum):
    SUPERVISOR = "supervisor"
    BRIEF = "brief"
    TCO = "tco"
    LCA = "lca"
    SECOND_HAND = "second_hand"


class TrailKind(StrEnum):
    FOUND = "found"
    DECIDED = "decided"
    EXCLUDED = "excluded"


class TrailEntry(DomainModel):
    agent: Agent
    kind: TrailKind
    summary: str
    source: Source | None = None
    reason: str | None = None
    model_tier: Tier | None = None
    model: str | None = None

    @model_validator(mode="after")
    def _exclusion_has_a_reason(self) -> Self:
        if self.kind is TrailKind.EXCLUDED and self.reason is None:
            raise ValueError("an exclusion carries its reason")
        return self


class InterviewAnswers(DomainModel):
    """What the interview resumes with: the answers the user picked, the answers their reply was
    read to give, the factors of the user's own it adds, and the reply's trail entries. Nothing
    at all is "skip all"."""

    given: tuple[Answer, ...] = ()
    from_reply: tuple[Answer, ...] = ()
    factors: tuple[DecisionFactor, ...] = ()
    trail: tuple[TrailEntry, ...] = ()


class Figure(StrEnum):
    """The computed figures of a comparison row, as defined in calculations.md."""

    COST_PER_YEAR = "cost_per_year"
    COST_PER_USE = "cost_per_use"
    PURCHASES = "purchases"
    HORIZON_COST = "horizon_cost"
    HORIZON_CO2E = "horizon_co2e"
    SAVINGS = "savings"
    CO2E_AVOIDED = "co2e_avoided"


class ComparisonRow(DomainModel):
    """One option's figures. A missing figure has its reason in `missing_reasons`."""

    option_id: str
    cost_per_year: Decimal | None = None
    cost_per_use: Decimal | None = None
    purchases: int | None = None
    horizon_cost: Decimal | None = None
    horizon_co2e_low: Decimal | None = None
    horizon_co2e_high: Decimal | None = None
    horizon_co2e_tier: LcaTier | None = None
    savings: Decimal | None = None
    co2e_avoided_low: Decimal | None = None
    co2e_avoided_high: Decimal | None = None
    co2e_avoided_tier: LcaTier | None = None
    missing_reasons: dict[Figure, str] = {}
    recurring_costs_not_found: bool = False
    recurring_cost_converted_from: ConvertedCurrency | None = None
    within_budget: bool | None = None


class Comparison(DomainModel):
    baseline_option_id: str | None = None
    rows: tuple[ComparisonRow, ...] = ()


class CaveatCode(StrEnum):
    NOT_TUNED = "not_tuned"
    ENERGY_HEAVY = "energy_heavy"
    CLOTHING = "clothing"


class Caveat(DomainModel):
    """A fixed statement that follows from the scope. Its wording is applied when shown."""

    code: CaveatCode


class WarningCode(StrEnum):
    """The closed set of warning codes; the table is in docs/architecture/agents.md."""

    BUDGET_UNREADABLE = "budget_unreadable"
    BUDGET_NOT_POSITIVE = "budget_not_positive"
    BUDGET_OTHER_CURRENCY = "budget_other_currency"
    NOTHING_WITHIN_BUDGET = "nothing_within_budget"
    LINK_UNREADABLE = "link_unreadable"
    LINK_PRICE_OTHER_CURRENCY = "link_price_other_currency"
    RESEARCH_UNAVAILABLE = "research_unavailable"
    QUESTIONS_UNAVAILABLE = "questions_unavailable"
    STATED_ANSWERS_UNAVAILABLE = "stated_answers_unavailable"
    ONE_OPTION_ONLY = "one_option_only"
    NO_OPTIONS_FOUND = "no_options_found"
    CO2E_UNAVAILABLE = "co2e_unavailable"


class Warning(DomainModel):
    code: WarningCode
    message: str
    option_id: str | None = None


class CheckReason(StrEnum):
    UNANSWERED = "unanswered"
    UNVERIFIED = "unverified"
    # A price to confirm before buying: the one reason that is about no factor.
    PRICE = "price"


class CheckItem(DomainModel):
    factor_id: str | None = None
    option_id: str | None = None
    reason: CheckReason

    @model_validator(mode="after")
    def _only_a_price_is_about_no_factor(self) -> Self:
        if (self.reason is CheckReason.PRICE) != (self.factor_id is None):
            raise ValueError("a price to confirm has no factor, and every other item has one")
        if self.reason is CheckReason.PRICE and self.option_id is None:
            raise ValueError("a price to confirm is about an option")
        return self


class EvidenceSummary(DomainModel):
    """Counts only; turning them into a sentence is presentation."""

    lifespans_sourced: Count = 0
    lifespans_estimated: Count = 0
    lifespans_user_set: Count = 0
    lifespans_missing: Count = 0
    footprints_published: Count = 0
    footprints_benchmark: Count = 0
    footprints_model_estimate: Count = 0
    footprints_missing: Count = 0


class Report(DomainModel):
    """One shape for every outcome: declined, unclear, all skipped and no options included."""

    request: Request
    factors: tuple[DecisionFactor, ...] = Field(default=(), max_length=MAX_FACTORS)
    questions: tuple[Question, ...] = Field(default=(), max_length=MAX_QUESTIONS)
    answers: tuple[Answer, ...] = ()
    options: tuple[ProductOption, ...] = ()
    lca_results: tuple[LcaResult, ...] = ()
    listings: tuple[Listing, ...] = ()
    assumptions: Assumptions = Assumptions()
    comparison: Comparison | None = None
    evidence_summary: EvidenceSummary = EvidenceSummary()
    caveats: tuple[Caveat, ...] = ()
    check_before_you_buy: tuple[CheckItem, ...] = ()
    trail: tuple[TrailEntry, ...] = ()
    warnings: tuple[Warning, ...] = ()
