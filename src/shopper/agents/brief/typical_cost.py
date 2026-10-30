"""The typical yearly cost of a category's first recurring-cost factor, read by code from the
amount, interval and pack count the read quoted from the result the factor cites.

Rules: docs/architecture/category_brief.md ("Decision factors") and
docs/adr/0002-fixed-rate-conversion-recurring-costs.md. The figure is one line above the
questions and on the report, never asked about; the comparison uses each option's own recurring
cost.
"""

from collections.abc import Sequence

from shopper.agents.brief.models import Cited
from shopper.agents.brief.trail import entry
from shopper.agents.shared.yearly_cost import yearly_cost
from shopper.calc.display import euros
from shopper.state import FactorKind, TrailEntry, TrailKind

NO_AMOUNT_QUOTED = "the read quoted no amount"


def with_typical_cost(cited: Sequence[Cited]) -> tuple[tuple[Cited, ...], tuple[TrailEntry, ...]]:
    """The factors with the first recurring-cost factor's typical yearly cost, when its quotes
    pass the checks, and the trail entry that says how it was read or why it has none."""
    first = next(
        (
            number
            for number, found in enumerate(cited)
            if found.factor.kind is FactorKind.RECURRING_COST
        ),
        None,
    )
    if first is None:
        return tuple(cited), ()
    found = cited[first]
    proposed = found.read
    name = found.factor.name
    cost = (
        NO_AMOUNT_QUOTED
        if proposed.amount_quote is None
        else yearly_cost(
            found.result,
            proposed.amount_quote,
            proposed.interval_quote,
            proposed.pack_count_quote,
        )
    )
    if isinstance(cost, str):
        summary = f'No typical yearly cost for "{name}"'
        return tuple(cited), (entry(TrailKind.EXCLUDED, summary, reason=cost),)
    factor = found.factor.model_copy(
        update={
            "typical_yearly_cost": cost.per_year,
            "typical_yearly_cost_source": found.factor.source,
            "typical_yearly_cost_converted_from": cost.converted_from,
        }
    )
    kept = entry(
        TrailKind.FOUND,
        f'Typical yearly cost of "{name}": {euros(cost.per_year)} a year',
        reason="; ".join(cost.notes) or None,
        source=found.factor.source,
    )
    updated = (*cited[:first], found._replace(factor=factor), *cited[first + 1 :])
    return updated, (kept,)
