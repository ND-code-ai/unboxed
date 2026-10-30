"""Sample values the tests share."""

from datetime import date
from decimal import Decimal

from shopper.state import TIER_3_BOUNDARY, LcaInput, Source, SourceKind

PRICE_SOURCE = Source(kind=SourceKind.URL, reference="https://www.example.com/shop/product")
PRICE_SEEN_ON = date(2026, 10, 17)


def seen_price(price: str | None) -> dict[str, object]:
    """An option's price with the source and date it comes with; nothing for no price."""
    if price is None:
        return {}
    return {"price": Decimal(price), "price_source": PRICE_SOURCE, "price_seen_on": PRICE_SEEN_ON}


MODEL_ESTIMATE = Source(kind=SourceKind.MODEL_ESTIMATE, reference="model estimate")
STEEL_INPUT = LcaInput(
    name="carbon steel",
    material_source=MODEL_ESTIMATE,
    mass_kg=Decimal("1.4"),
    mass_source=MODEL_ESTIMATE,
    factor_low=Decimal("1.5"),
    factor_high=Decimal("3"),
    factor_source=MODEL_ESTIMATE,
)


def model_estimate_parts() -> dict[str, object]:
    """What a tier 3 result carries besides its range and source: inputs, manufacturing and
    the fixed boundary."""
    return {
        "tier": 3,
        "boundary": TIER_3_BOUNDARY,
        "inputs": (STEEL_INPUT,),
        "manufacturing_low": Decimal("1"),
        "manufacturing_high": Decimal("2"),
        "manufacturing_source": MODEL_ESTIMATE,
    }
