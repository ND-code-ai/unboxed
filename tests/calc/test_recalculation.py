from decimal import Decimal

from samples import seen_price
from shopper.calc.recalculation import recalculate
from shopper.state import Assumptions, ProductOption, Source, SourceKind

WEB = Source(kind=SourceKind.URL, reference="https://example.com/test")


def option(option_id: str, price: str, lifespan: str) -> ProductOption:
    return ProductOption(
        id=option_id,
        name=option_id,
        **seen_price(price),
        lifespan_years=Decimal(lifespan),
        lifespan_source=WEB,
    )


NON_STICK = option("non-stick", "20", "2")
CARBON_STEEL = option("carbon-steel", "40", "30")


def test_recalculation_with_a_user_set_lifespan() -> None:
    assumptions = Assumptions(lifespan_overrides={"non-stick": Decimal("5")})

    comparison, summary = recalculate((NON_STICK, CARBON_STEEL), (), assumptions)

    non_stick = next(row for row in comparison.rows if row.option_id == "non-stick")
    assert non_stick.cost_per_year == Decimal("4")
    assert non_stick.purchases == 2
    assert non_stick.horizon_cost == Decimal("40")
    assert summary.lifespans_user_set == 1
    assert summary.lifespans_sourced == 1


def test_removing_the_override_restores_the_estimate() -> None:
    comparison, summary = recalculate((NON_STICK, CARBON_STEEL), (), Assumptions())

    non_stick = next(row for row in comparison.rows if row.option_id == "non-stick")
    assert non_stick.horizon_cost == Decimal("100")
    assert summary.lifespans_user_set == 0
    assert summary.lifespans_sourced == 2
