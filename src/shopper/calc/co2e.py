"""The CO2e of a model estimate, by docs/architecture/calculations.md ("CO2e of a model estimate").

The model gives the masses, the emission factors and the manufacturing range; the sum is done
here (docs/adr/0006-tier-3-returns-factors-code-multiplies.md). Nothing here rounds.
"""

from collections.abc import Sequence
from decimal import Decimal

from shopper.state import DomainModel, LcaInput, SourceKind


class WeightScaling(DomainModel):
    """The inputs after scaling to a stated weight. `scale` is missing when no mass could be
    scaled; `scaled` is false when every mass was kept."""

    inputs: tuple[LcaInput, ...]
    scale: Decimal | None
    scaled: bool


def estimated_co2e(
    inputs: Sequence[LcaInput],
    manufacturing_low: Decimal,
    manufacturing_high: Decimal,
    min_spread: Decimal,
) -> tuple[Decimal, Decimal]:
    """Mass times factor plus manufacturing at each end, widened so high is at least
    `min_spread` times low."""
    low = sum((item.mass_kg * item.factor_low for item in inputs), manufacturing_low)
    high = sum((item.mass_kg * item.factor_high for item in inputs), manufacturing_high)
    return _widened(low, high, min_spread)


def _widened(low: Decimal, high: Decimal, min_spread: Decimal) -> tuple[Decimal, Decimal]:
    """The range kept when wide enough, else spread around its geometric midpoint."""
    if high >= min_spread * low:
        return low, high
    product = low * high
    return (product / min_spread).sqrt(), (product * min_spread).sqrt()


def scaled_to_weight(
    inputs: Sequence[LcaInput], weight_kg: Decimal, window: tuple[Decimal, Decimal]
) -> WeightScaling:
    """The assumed masses of bulk materials scaled so that every mass adds up to the stated
    weight, when that scale lies inside `window`, both ends included."""
    assumed = sum((item.mass_kg for item in inputs if _scalable(item)), Decimal(0))
    if not assumed:
        return WeightScaling(inputs=tuple(inputs), scale=None, scaled=False)
    fixed = sum((item.mass_kg for item in inputs if not _scalable(item)), Decimal(0))
    scale = (weight_kg - fixed) / assumed
    lowest, highest = window
    if not lowest <= scale <= highest:
        return WeightScaling(inputs=tuple(inputs), scale=scale, scaled=False)
    scaled = tuple(
        item.model_copy(update={"mass_kg": item.mass_kg * scale}) if _scalable(item) else item
        for item in inputs
    )
    return WeightScaling(inputs=scaled, scale=scale, scaled=True)


def _scalable(item: LcaInput) -> bool:
    """A bulk material whose mass the model assumed; never a sourced mass nor a component."""
    return item.mass_source.kind is SourceKind.MODEL_ESTIMATE and not item.component
