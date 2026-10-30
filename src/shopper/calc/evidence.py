"""The evidence summary: counts of where lifespans and footprints came from.

Counting only; turning the counts into a sentence is presentation.
"""

from collections import Counter
from collections.abc import Sequence

from shopper.state import (
    Assumptions,
    EvidenceSummary,
    LcaResult,
    ProductOption,
    SourceKind,
)

FOOTPRINT_FIELD_BY_TIER = {
    1: "footprints_published",
    2: "footprints_benchmark",
    3: "footprints_model_estimate",
}


def summarise_evidence(
    options: Sequence[ProductOption],
    lca_results: Sequence[LcaResult],
    assumptions: Assumptions,
) -> EvidenceSummary:
    """One lifespan count and one footprint count per option."""
    tiers = {result.option_id: result.tier for result in lca_results}
    counts = Counter(_lifespan_field(option, assumptions) for option in options)
    counts.update(
        FOOTPRINT_FIELD_BY_TIER[tiers[option.id]] if option.id in tiers else "footprints_missing"
        for option in options
    )
    return EvidenceSummary(**counts)


def options_counted(summary: EvidenceSummary) -> int:
    """How many options a summary counts: every option has exactly one lifespan count."""
    return (
        summary.lifespans_sourced
        + summary.lifespans_estimated
        + summary.lifespans_user_set
        + summary.lifespans_missing
    )


def _lifespan_field(option: ProductOption, assumptions: Assumptions) -> str:
    """A value the user set counts as set by the user, whatever the option's own source."""
    if option.id in assumptions.lifespan_overrides:
        return "lifespans_user_set"
    if option.lifespan_source is None:
        return "lifespans_missing"
    if option.lifespan_source.kind is SourceKind.USER:
        return "lifespans_user_set"
    if option.lifespan_source.kind is SourceKind.MODEL_ESTIMATE:
        return "lifespans_estimated"
    return "lifespans_sourced"
