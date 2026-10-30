"""What the TCO analyzer's model calls return, and what its steps hand to each other.

The pydantic models are the schemas of the durability judgements, the page read and the
evidence and findings reads; the tuples carry results between the steps in `agent.py`. Rules:
docs/architecture/option_research.md.
"""

from decimal import Decimal
from typing import Annotated, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from shopper.agents.tco.prompt import JUDGEMENT_DESCRIPTION, REASON_DESCRIPTION
from shopper.state import (
    ConvertedCurrency,
    DecisionFactor,
    ProductOption,
    RecurringCostState,
    Source,
    StatedBy,
    TrailEntry,
)
from shopper.tools.results import ListedProduct, ProductPage, SearchResult

DurabilityJudgement = Literal["long", "medium", "short", "unknown"]
# The order in which the judgement ranks a candidate in a slot, best first.
JUDGEMENT_ORDER: tuple[DurabilityJudgement, ...] = ("long", "medium", "unknown", "short")


class ReadJudgement(BaseModel):
    """The model's durability judgement of one numbered candidate, with the reason that names its
    make."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: int
    durability_judgement: DurabilityJudgement | None = Field(description=JUDGEMENT_DESCRIPTION)
    durability_reason: str | None = Field(description=REASON_DESCRIPTION)


class NamesJudged(BaseModel):
    """The fields the model fills when it judges the candidates by their listed names, and
    nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    set_requested: bool
    candidates: list[ReadJudgement]


class PagesJudged(BaseModel):
    """The fields the model fills when it judges the candidates read by their product pages, and
    nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidates: list[ReadJudgement]


class Gap(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    what: str
    reason: str


# What the page of an amount sells, against the category (tasks 1.11 and 1.13).
Sells = Literal[
    "the_item", "set_or_bundle", "incomplete", "part_or_accessory", "other_kind", "unclear"
]


class ReadAmount(BaseModel):
    """One euro amount the page states, with the name of the product it is for and what that
    product's page sells."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quote: str
    name: str
    sells: Sells
    sells_quote: str
    piece_count: int | None
    piece_count_quote: str | None


class ReadPageResult(BaseModel):
    """What the page says, as the model reads it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: int
    amounts: list[ReadAmount]


class PageReading(BaseModel):
    """The fields the model fills when it reads a product page, and nothing else.

    The schema of the price read of tasks 1.8.2 and 1.11, which task 1.12 measured on product
    pages against the category, cut in task 1.14 to the fields code reads; one entry per result,
    though the read is given one page.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    results: list[ReadPageResult]


# A result as the evidence read cites it: numbered from 1, so a zero fails validation and the
# read is asked again (in task 1.8.3 the model cited a lone result as 0).
ResultNumber = Annotated[int, Field(ge=1)]
LifespanAbout = Literal["product", "line", "type"]
EvidenceKind = Literal["lifespan", "warranty", "repairability", "wear_material", "care"]


class ReadLifespan(BaseModel):
    """A statement of how long the product, its line or its type lasts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: ResultNumber
    quote: str
    stated_by: StatedBy
    about: LifespanAbout
    # For a lifespan about the type: the type as the quote names it ("non-stick pans").
    type: str | None


class ReadWarranty(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    result: ResultNumber
    quote: str
    stated_by: StatedBy


class ReadEvidenceItem(BaseModel):
    """One kind of durability evidence: a material, a part or an action, quoted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: ResultNumber
    value: str
    quote: str
    stated_by: StatedBy


class ReadConsumable(BaseModel):
    """The main consumable, with its amount, interval and pack count, each quoted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: ResultNumber
    name: str
    stated_by: StatedBy
    amount_quote: str
    interval_quote: str | None
    pack_count_quote: str | None


class ReadFactorFit(BaseModel):
    """How the product fits one numbered answered factor: a short value, the result and the
    quote that show it; all three null when no result settles it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    factor: int
    fit: Literal["meets", "fails", "unverified"]
    value: str | None
    result: ResultNumber | None
    quote: str | None
    stated_by: StatedBy | None


class EvidenceReading(BaseModel):
    """The fields the model fills when it reads a product option's evidence results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lifespans: list[ReadLifespan]
    warranty: ReadWarranty | None
    repairability: ReadEvidenceItem | None
    wear_material: ReadEvidenceItem | None
    care: ReadEvidenceItem | None
    consumable: ReadConsumable | None
    other_consumables: list[str]
    # At least a year: with no evidence the read answered 0 in task 1.8.3; a zero is asked again.
    estimated_years: Annotated[int, Field(ge=1)]
    estimate_rests_on: list[EvidenceKind]
    fits: list[ReadFactorFit]
    gaps: list[Gap]


class ReadFinding(BaseModel):
    """One thing a tester or an owner reports, quoted from the result it comes from and told in
    the model's own words; the quote is checked and never kept."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: ResultNumber
    # The model's judgement, checked by code: a shop's customer reviews are not used.
    on_shop_page: bool
    quote: str
    summary: str
    stated_by: StatedBy
    rating_quote: str | None


class FindingsReading(BaseModel):
    """The fields the model fills when it reads a product option's findings results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: list[ReadFinding]
    gaps: list[Gap]


class Judgement(NamedTuple):
    """The model's durability judgement of a candidate, with the reason that names its make; it
    orders candidates in selection, and is never on the report."""

    value: DurabilityJudgement
    reason: str | None = None


UNKNOWN = Judgement("unknown")


class Candidate(NamedTuple):
    """A product the listing pages name, numbered from 1 in the order of the merged lists, with
    its durability judgement by name."""

    number: int
    listed: ListedProduct
    judgement: Judgement = UNKNOWN


class ListedCandidates(NamedTuple):
    """What the listing pages gave: the candidates in listing order, the local term a product
    page's name is checked for (missing when that check is skipped), the trail, how many pages
    were read, and whether every listing search, or every listing page fetch, failed."""

    candidates: tuple[Candidate, ...]
    name_term: str | None
    trail: tuple[TrailEntry, ...]
    pages_read: int
    failed: bool


class NamesJudgement(NamedTuple):
    """The candidates with their judgement by name, whether a set is asked for, and the trail."""

    candidates: tuple[Candidate, ...]
    set_requested: bool
    trail: tuple[TrailEntry, ...]


class Offered(NamedTuple):
    """A candidate as its product page offers it: its name and brand, the page, the price without
    shipping and the stated shipping of the offer that stands, its seller, the day the page was
    read, its marks and, for a set, its piece count. `judgement` is its judgement by page once
    that call ran, else its judgement by name."""

    candidate: Candidate
    name: str
    brand: str | None
    page: ProductPage
    price: Decimal
    shipping: Decimal | None
    seller: str | None
    out_of_stock: bool
    incomplete: bool
    piece_count: int | None
    judgement: Judgement = UNKNOWN


class PageContext(NamedTuple):
    """What every page read needs: the category, the local term a page's name is checked for
    (missing when that check is skipped), whether a set is asked for, and whether most products
    listed for the category name a size."""

    category: str
    name_term: str | None
    set_requested: bool
    sized: bool


class Sold(NamedTuple):
    """What a product page sells, once the read's answer passes the checks: the item, a set when
    a set is asked for, or the item sold incomplete; missing with the reason when it is none of
    them. A set carries its quoted piece count."""

    sells: Sells | None
    reason: str | None = None
    piece_count: int | None = None


class PageRead(NamedTuple):
    """What reading one candidate's product page gave: the candidate offered, or none when it was
    left out, the trail, and whether the page was fetched at all."""

    offered: Offered | None
    trail: tuple[TrailEntry, ...]
    fetched: bool


class Reads(NamedTuple):
    """The candidates the product pages offer, in listing order, the trail, how many pages were
    fetched, and whether every fetch failed."""

    offered: tuple[Offered, ...]
    trail: tuple[TrailEntry, ...]
    fetched: int
    failed: bool


class PagesJudgement(NamedTuple):
    """The candidates read, with their judgement by page, and the trail."""

    offered: tuple[Offered, ...]
    trail: tuple[TrailEntry, ...]


class Slot(NamedTuple):
    """A slot taken by a candidate, or left empty with the reason; `name` is how the trail names
    it, and `by_price` is set when the durability judgement did not decide the pick."""

    name: str
    taken: Offered | None
    reason: str | None = None
    by_price: bool = False


class EvidenceContext(NamedTuple):
    """What every check of an evidence read needs: the option, the brand a result must name, the
    category (empty when the request has none) and the results the read saw, numbered from 1."""

    option: ProductOption
    brand: str | None
    category: str
    results: tuple[SearchResult, ...]


class Lifespan(NamedTuple):
    years: Decimal
    source: Source


class RecurringCost(NamedTuple):
    """A recurring cost found, or the state that says why there is none."""

    state: RecurringCostState
    per_year: Decimal | None = None
    source: Source | None = None
    converted_from: ConvertedCurrency | None = None
    others_left_out: bool = False


class AnsweredFactor(NamedTuple):
    """A factor the evidence read judges, with its question and the answer as text; a care
    factor also carries its care statement."""

    factor: DecisionFactor
    question: str | None
    answer: str
    care: str | None = None


class FailedAnswer(NamedTuple):
    """A `fails` that passed the checks: the factor, and the quote and the page that show it."""

    factor: DecisionFactor
    quote: str
    url: str
