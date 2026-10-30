"""The LCA agent: one call to the large tier estimates every option (tier 3).

The model returns a factor table and each option's inputs pointing at it; code copies the
factors in, checks them, scales the masses to a stated weight and sums
(docs/adr/0006-tier-3-returns-factors-code-multiplies.md). Rules: docs/architecture/lca.md.
"""

import asyncio
from collections.abc import Sequence

from shopper import wording
from shopper.agents.bundle import LcaOutput
from shopper.agents.lca import trail
from shopper.agents.lca.checks import estimates
from shopper.agents.lca.models import Declined, Estimate, EstimateReply
from shopper.agents.lca.prompt import ESTIMATE_PROMPT
from shopper.calc.co2e import estimated_co2e, scaled_to_weight
from shopper.config import (
    LCA_MAX_TOKENS,
    LCA_MIN_SPREAD,
    LCA_TIME_CAP_SECONDS,
    LCA_TIMEOUT_SECONDS,
    MODEL_IDS,
    WEIGHT_SCALE_WINDOW,
    Tier,
)
from shopper.llm import ChatModel, Completion, LlmFailure, complete_structured
from shopper.state import (
    TIER_3_BOUNDARY,
    LcaResult,
    ProductOption,
    Source,
    SourceKind,
    TrailEntry,
    Warning,
    WarningCode,
)

TIER: Tier = "large"


async def estimate_co2e(
    options: Sequence[ProductOption],
    chat: ChatModel,
    *,
    time_cap: float = LCA_TIME_CAP_SECONDS,
) -> LcaOutput:
    """A tier 3 result for each option the model estimated and whose inputs pass the checks; a
    warning for each other option, or one for the report when the call failed."""
    if not options:
        return LcaOutput()
    try:
        async with asyncio.timeout(time_cap):
            reply = await complete_structured(
                chat,
                TIER,
                estimate_input(options),
                EstimateReply,
                system=ESTIMATE_PROMPT,
                max_tokens=LCA_MAX_TOKENS,
                timeout=LCA_TIMEOUT_SECONDS,
            )
    except TimeoutError:
        return _unavailable(trail.out_of_time(time_cap, TIER, MODEL_IDS[TIER]))
    if isinstance(reply, LlmFailure):
        return _unavailable(trail.model_call_failed("estimate the CO2e of the options", reply))
    return _results(options, reply)


def estimate_input(options: Sequence[ProductOption]) -> str:
    """The numbered options as the model reads them, with what the product page states."""
    return "Options:\n\n" + "\n\n".join(
        _option_text(number, option) for number, option in enumerate(options, start=1)
    )


def _option_text(number: int, option: ProductOption) -> str:
    lines = [f"{number}. {option.name}"]
    if option.brand:
        lines.append(f"   Brand: {option.brand}")
    if option.piece_count is not None:
        lines.append(f"   A set of {option.piece_count} pieces")
    fixed = _fixed_inputs(option)
    if fixed:
        lines.append("   Fixed inputs from the product page:")
        lines.extend(f"   [{index}] {text}" for index, text in enumerate(fixed, start=1))
    return "\n".join(lines)


def _fixed_inputs(option: ProductOption) -> list[str]:
    """The page's materials, numbered from 1, then its weight, each with its URL."""
    materials = [
        f"material: {material.name}"
        + (f", form: {material.form}" if material.form else "")
        + (f", mass: {material.mass_kg} kg" if material.mass_kg is not None else "")
        + f" ({material.source.reference})"
        for material in option.materials
    ]
    if option.weight_kg is None or option.weight_source is None:
        return materials
    weight = f"weight of the whole item: {option.weight_kg} kg ({option.weight_source.reference})"
    return [*materials, weight]


def _results(options: Sequence[ProductOption], reply: Completion[EstimateReply]) -> LcaOutput:
    estimated = Source(kind=SourceKind.MODEL_ESTIMATE, reference=reply.model)
    results: list[LcaResult] = []
    entries: list[TrailEntry] = []
    warnings: list[Warning] = []
    for option, outcome in zip(options, estimates(options, reply.value, estimated), strict=True):
        if isinstance(outcome, Declined):
            entries.append(trail.by_model(trail.declined(option.name, outcome.reason), reply))
            warnings.append(_option_unavailable(option))
            continue
        result, written = _result(option, outcome, estimated)
        results.append(result)
        entries.append(trail.by_model(trail.estimated(option.name, outcome), reply))
        entries.extend(written)
    return LcaOutput(results=tuple(results), trail=tuple(entries), warnings=tuple(warnings))


def _result(
    option: ProductOption, estimate: Estimate, source: Source
) -> tuple[LcaResult, tuple[TrailEntry, ...]]:
    """The summed result, after scaling the masses to the page's weight when it states one."""
    inputs, written = estimate.inputs, ()
    if option.weight_kg is not None and option.weight_source is not None:
        scaling = scaled_to_weight(inputs, option.weight_kg, WEIGHT_SCALE_WINDOW)
        inputs = scaling.inputs
        written = (
            trail.weight_scaling(
                option.name, option.weight_kg, option.weight_source, scaling, WEIGHT_SCALE_WINDOW
            ),
        )
    low, high = estimated_co2e(
        inputs, estimate.manufacturing_low, estimate.manufacturing_high, LCA_MIN_SPREAD
    )
    result = LcaResult(
        option_id=option.id,
        co2e_low=low,
        co2e_high=high,
        tier=3,
        source=source,
        boundary=TIER_3_BOUNDARY,
        inputs=inputs,
        manufacturing_low=estimate.manufacturing_low,
        manufacturing_high=estimate.manufacturing_high,
        manufacturing_source=source,
    )
    return result, written


def _option_unavailable(option: ProductOption) -> Warning:
    return Warning(
        code=WarningCode.CO2E_UNAVAILABLE,
        message=wording.co2e_unavailable(option.name),
        option_id=option.id,
    )


def _unavailable(entry: TrailEntry) -> LcaOutput:
    warning = Warning(code=WarningCode.CO2E_UNAVAILABLE, message=wording.co2e_unavailable(None))
    return LcaOutput(trail=(entry,), warnings=(warning,))
