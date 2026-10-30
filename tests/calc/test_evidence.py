from decimal import Decimal
from typing import Literal

from samples import model_estimate_parts, seen_price
from shopper.calc.evidence import options_counted, summarise_evidence
from shopper.state import (
    Assumptions,
    EvidenceSummary,
    LcaResult,
    ProductOption,
    Source,
    SourceKind,
)

WEB = Source(kind=SourceKind.URL, reference="https://example.com/test")
DATASET = Source(kind=SourceKind.DATASET, reference="dataset row")
ESTIMATE = Source(kind=SourceKind.MODEL_ESTIMATE, reference="rough estimate")


def option(
    option_id: str, price: str, lifespan: str | None, source: Source | None
) -> ProductOption:
    return ProductOption(
        id=option_id,
        name=option_id,
        **seen_price(price),
        lifespan_years=None if lifespan is None else Decimal(lifespan),
        lifespan_source=source,
    )


def footprint(option_id: str, tier: Literal[1, 2, 3]) -> LcaResult:
    return LcaResult(
        option_id=option_id,
        co2e_low=Decimal("4"),
        co2e_high=Decimal("6"),
        source=WEB,
        **(model_estimate_parts() if tier == 3 else {"tier": tier, "boundary": "cradle to gate"}),
    )


NON_STICK = option("non-stick", "20", "2", WEB)
CARBON_STEEL = option("carbon-steel", "40", "30", DATASET)
CAST_IRON = option("cast-iron", "60", "40", ESTIMATE)
UNKNOWN = option("unknown", "25", None, None)


def test_nothing_sourced() -> None:
    options = (CAST_IRON, option("guess", "20", "3", ESTIMATE), UNKNOWN)

    summary = summarise_evidence(options, (), Assumptions())

    assert summary == EvidenceSummary(
        lifespans_estimated=2, lifespans_missing=1, footprints_missing=3
    )


def test_lifespans_and_footprints_are_counted_by_where_they_came_from() -> None:
    options = (NON_STICK, CARBON_STEEL, CAST_IRON, UNKNOWN)
    footprints = (
        footprint("non-stick", 1),
        footprint("carbon-steel", 2),
        footprint("cast-iron", 3),
    )

    summary = summarise_evidence(options, footprints, Assumptions())

    assert summary == EvidenceSummary(
        lifespans_sourced=2,
        lifespans_estimated=1,
        lifespans_missing=1,
        footprints_published=1,
        footprints_benchmark=1,
        footprints_model_estimate=1,
        footprints_missing=1,
    )


def test_a_lifespan_the_user_set_is_not_counted_as_sourced() -> None:
    assumptions = Assumptions(lifespan_overrides={"non-stick": Decimal("5")})

    summary = summarise_evidence((NON_STICK, CARBON_STEEL), (), assumptions)

    assert summary.lifespans_user_set == 1
    assert summary.lifespans_sourced == 1


def test_the_options_counted_are_one_per_lifespan_count() -> None:
    summary = EvidenceSummary(
        lifespans_sourced=2, lifespans_estimated=1, lifespans_user_set=1, lifespans_missing=1
    )

    assert options_counted(summary) == 5
    assert options_counted(EvidenceSummary()) == 0
