"""Recalculation from changed assumptions: no agent runs, no model is called, nothing is fetched."""

from collections.abc import Sequence
from decimal import Decimal

from shopper.calc.comparison import compare
from shopper.calc.evidence import summarise_evidence
from shopper.state import Assumptions, Comparison, EvidenceSummary, LcaResult, ProductOption


def recalculate(
    options: Sequence[ProductOption],
    lca_results: Sequence[LcaResult],
    assumptions: Assumptions,
    budget: Decimal | None = None,
    baseline_option_id: str | None = None,
) -> tuple[Comparison, EvidenceSummary]:
    """The new comparison and evidence summary together: a user-set lifespan changes both."""
    comparison = compare(options, lca_results, assumptions, budget, baseline_option_id)
    return comparison, summarise_evidence(options, lca_results, assumptions)
