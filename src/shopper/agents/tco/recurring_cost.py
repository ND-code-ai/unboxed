"""What an evidence read says a product option costs to keep using: its recurring cost a year,
read by code from the quoted amount, interval and pack count (`agents/shared/yearly_cost.py`).

Rules: docs/architecture/option_research.md ("Recurring cost") and
docs/adr/0002-fixed-rate-conversion-recurring-costs.md.
"""

from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.yearly_cost import YearlyCost, yearly_cost
from shopper.agents.tco.evidence_checks import brand_fault, cited_source, quote_fault
from shopper.agents.tco.models import (
    EvidenceContext,
    EvidenceReading,
    ReadConsumable,
    RecurringCost,
)
from shopper.agents.tco.trail import entry, left_out_of
from shopper.calc.display import euros
from shopper.state import RecurringCostState, TrailEntry, TrailKind

NOT_FOUND = RecurringCost(state=RecurringCostState.NOT_FOUND)


def recurring_cost(
    context: EvidenceContext, reading: EvidenceReading
) -> tuple[RecurringCost, tuple[TrailEntry, ...]]:
    """The main consumable's cost a year, or not found with the reason on the trail."""
    name = context.option.name
    read = reading.consumable
    others = _others(reading)
    if read is None:
        named = f"; consumables named: {others}" if others else ""
        nothing = entry(
            TrailKind.DECIDED,
            f'No recurring cost found for "{name}"',
            reason=f"the results state no price with an interval{named}",
        )
        return NOT_FOUND, (nothing,)
    yearly = _yearly(context, read)
    if isinstance(yearly, str):
        return NOT_FOUND, (left_out_of(name, "a recurring cost", yearly),)
    consumable = read.name.strip()
    source = cited_source(read, context.results, label=consumable)
    left_out = (f"other consumables not counted: {others}",) if others else ()
    found = entry(
        TrailKind.FOUND,
        f'Recurring cost of "{name}": {euros(yearly.per_year)} a year, {consumable}',
        reason="; ".join((*yearly.notes, *left_out)) or None,
        source=source,
    )
    cost = RecurringCost(
        state=RecurringCostState.FOUND,
        per_year=yearly.per_year,
        source=source,
        converted_from=yearly.converted_from,
        others_left_out=bool(others),
    )
    return cost, (found,)


def _yearly(context: EvidenceContext, read: ReadConsumable) -> YearlyCost | str:
    """The yearly cost, or why there is none."""
    if not read.name.strip() or fault_in(read.name) is not None:
        return "its name holds what a model may not write"
    fault = quote_fault(read.result, read.amount_quote, context.results, holds_a_number=True)
    if fault is not None:
        return f"its amount: {fault}"
    fault = brand_fault(context, read.result, read.amount_quote)
    if fault is not None:
        return fault
    result = context.results[read.result - 1]
    return yearly_cost(result, read.amount_quote, read.interval_quote, read.pack_count_quote)


def _others(reading: EvidenceReading) -> str:
    names = [
        name.strip()
        for name in reading.other_consumables
        if name.strip() and fault_in(name) is None
    ]
    return ", ".join(dict.fromkeys(names))
