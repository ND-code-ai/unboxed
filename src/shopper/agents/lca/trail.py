"""The LCA agent's trail entries: the shared ones (`agents/shared/trail.py`), written as it, and
one per option saying what tier 3 estimated or declined."""

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from shopper.agents.lca.models import Estimate
from shopper.agents.shared import trail
from shopper.agents.shared.trail import by_model, counted
from shopper.calc.co2e import WeightScaling
from shopper.config import Tier
from shopper.llm import LlmFailure
from shopper.state import Agent, Source, TrailEntry, TrailKind

__all__ = [
    "by_model",
    "declined",
    "estimated",
    "model_call_failed",
    "out_of_time",
    "weight_scaling",
]

HUNDREDTH = Decimal("0.01")


def model_call_failed(doing: str, failure: LlmFailure) -> TrailEntry:
    return trail.model_call_failed(Agent.LCA, doing, failure)


def out_of_time(time_cap: float, tier: Tier, model: str) -> TrailEntry:
    stopped = trail.entry(
        Agent.LCA,
        TrailKind.EXCLUDED,
        "Could not estimate the CO2e of the options",
        reason=f"the estimate took longer than {time_cap:g} s",
    )
    return stopped.model_copy(update={"model_tier": tier, "model": model})


def estimated(name: str, estimate: Estimate) -> TrailEntry:
    """What tier 3 estimated for one option: its materials and its manufacturing."""
    materials = counted(len(estimate.inputs), "material")
    return trail.entry(
        Agent.LCA,
        TrailKind.DECIDED,
        f'LCA tier 3 estimated "{name}": {materials} and manufacturing and assembly',
    )


def declined(name: str, reason: str) -> TrailEntry:
    return trail.entry(
        Agent.LCA, TrailKind.EXCLUDED, f'LCA tier 3 gave no estimate for "{name}"', reason=reason
    )


def weight_scaling(
    name: str,
    weight_kg: Decimal,
    source: Source,
    scaling: WeightScaling,
    window: tuple[Decimal, Decimal],
) -> TrailEntry:
    """Whether the assumed masses were scaled to the weight the page states, and by what."""
    stated = f"the page's weight of {weight_kg} kg"
    if scaling.scaled and scaling.scale is not None:
        shown = _shown(scaling.scale, window)
        summary = f'Scaled the assumed masses of "{name}" by {shown} to {stated}'
    elif scaling.scale is None:
        summary = f'Kept the masses of "{name}": none is an assumed mass of a bulk material'
    else:
        lowest, highest = window
        summary = (
            f'Kept the assumed masses of "{name}": {stated} would scale them by '
            f"{_shown(scaling.scale, window)}, outside {lowest} to {highest}"
        )
    return trail.entry(Agent.LCA, TrailKind.DECIDED, summary, source=source)


def _shown(scale: Decimal, window: tuple[Decimal, Decimal]) -> str:
    """The scale to two decimals, rounded half up, without trailing zeros; a scale outside the
    window rounds away from it instead, so it never shows as the bound it is past."""
    lowest, highest = window
    rounding = ROUND_HALF_UP
    if scale > highest:
        rounding = ROUND_CEILING
    elif scale < lowest:
        rounding = ROUND_FLOOR
    return f"{scale.quantize(HUNDREDTH, rounding=rounding).normalize():f}"
