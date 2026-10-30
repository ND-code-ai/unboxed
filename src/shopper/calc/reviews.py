"""The number of reviews an overall rating rests on, read from the words that state it.

An owner report's rating is kept only with this count (docs/architecture/option_evidence.md,
"Findings"). A count is a whole number, so a dot, a comma or a space before three digits groups
thousands: "1.234 beoordelingen" is 1234.
"""

import re

# Words for reviews in the languages the findings search returns.
REVIEW_WORDS = (
    "reviews",
    "review",
    "ratings",
    "rating",
    "beoordelingen",
    "beoordeling",
    "recensies",
    "recensie",
    "bewertungen",
    "bewertung",
)
_COUNT = re.compile(
    r"(?<![0-9.,])([0-9]{1,3}(?:[.,   ][0-9]{3})+|[0-9]+)\s*(?:" + "|".join(REVIEW_WORDS) + r")\b",
    re.IGNORECASE,
)
_GROUPING = re.compile(r"[.,   ]")


# A value and a scale word before a number ("4.5/5", "4.5 out of 5", "4,5 van 5"): that number is
# the rating's scale, not a count, also when a word for reviews follows ("4.5/5 rating"). Without
# the value, "op basis van 37 recensies" is a count.
_BEFORE_A_SCALE = re.compile(r"[0-9]\s*(?:/|\b(?:out of|of|van|uit|von))\s*$", re.IGNORECASE)


def review_count(text: str) -> int | None:
    """The number written just before the first word for reviews that is not a rating's scale;
    missing when there is none."""
    for found in _COUNT.finditer(text):
        if _BEFORE_A_SCALE.search(text[: found.start()]) is None:
            return int(_GROUPING.sub("", found.group(1)))
    return None
