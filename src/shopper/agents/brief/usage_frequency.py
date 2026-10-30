"""The usage frequencies: the fixed how-often choices, and the question built from four of them.

How often the product is used is the one decision factor the app always asks about. The words of
each frequency are in wording.py; the uses per year are here, for `calc/`, and never written by a
model. Rules: docs/architecture/interview.md ("The usage question").
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from shopper import wording
from shopper.state import Choice, DecisionFactor, FactorKind, Question

# Uses per year by frequency id, from the most often to the least. A choice's id is its
# frequency's id.
USES_PER_YEAR: Mapping[str, int] = MappingProxyType(
    {
        "several_times_a_day": 1000,
        "every_day": 365,
        "a_few_times_a_week": 150,
        "about_once_a_week": 50,
        "about_once_a_month": 12,
        "a_few_times_a_year": 4,
        "about_once_a_year": 1,
    }
)
FREQUENCIES_OFFERED = 4
# Offered when no model picked frequencies for the category, or its pick was not valid.
DEFAULT_FREQUENCIES = ("every_day", "a_few_times_a_week", "about_once_a_week", "about_once_a_month")

USAGE_FACTOR = DecisionFactor(
    id="usage-1",
    name=wording.USAGE_FACTOR_NAME,
    kind=FactorKind.USAGE,
    why=wording.USAGE_REASON,
)


def frequency_pick(frequencies: Sequence[str]) -> tuple[str, ...] | None:
    """The picked frequencies, most often first; missing unless they are four different
    known ones.

    A pick may skip frequencies.
    """
    picked = set(frequencies)
    is_four_different = len(frequencies) == len(picked) == FREQUENCIES_OFFERED
    if not is_four_different or not picked <= set(USES_PER_YEAR):
        return None
    return tuple(frequency for frequency in USES_PER_YEAR if frequency in picked)


def usage_question(frequencies: Sequence[str] = DEFAULT_FREQUENCIES) -> Question:
    """The question about how often the product is used, offering these frequencies."""
    return Question(
        id=f"question-{USAGE_FACTOR.id}",
        factor_id=USAGE_FACTOR.id,
        text=wording.USAGE_QUESTION,
        reason=wording.USAGE_REASON,
        choices=tuple(
            Choice(
                id=frequency,
                text=wording.USAGE_FREQUENCIES[frequency],
                uses_per_year=USES_PER_YEAR[frequency],
            )
            for frequency in frequencies
        ),
    )
