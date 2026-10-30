"""The checks on a finding's summary and rating, by direct call with plain text
(option_evidence.md, "Findings")."""

import pytest

from shopper.agents.tco.finding_checks import copied_fault, rating_in, summary_fault

SEEN = (
    "After eight months of daily use the non-stick coating started to flake off near the "
    "rim of my Alpha Cheapo 28 cm pan."
)
NAME_WORDS = ("alpha", "cheapo", "28", "cm")


def test_a_summary_sharing_six_words_in_a_row_with_the_text_seen_is_copied() -> None:
    summary = "One owner saw the non-stick coating started to flake off"

    assert copied_fault(summary, (SEEN,), NAME_WORDS) == (
        "its summary copies six or more words in a row from the search results"
    )


def test_a_summary_sharing_five_words_in_a_row_is_not_copied() -> None:
    summary = "One owner's non-stick coating started to flake after eight months"

    assert copied_fault(summary, (SEEN,), NAME_WORDS) is None


def test_the_check_runs_after_the_plain_normalisation() -> None:
    summary = "One owner: the NON‑STICK coating  started to flake OFF"

    assert copied_fault(summary, (SEEN,), NAME_WORDS) is not None


def test_a_run_made_only_of_the_name_and_brand_words_does_not_count() -> None:
    seen = ("Alpha Cheapo 28 cm Alpha Cheapo review",)
    summary = "The Alpha Cheapo 28 cm Alpha Cheapo lost its coating"

    assert copied_fault(summary, seen, NAME_WORDS) is None


@pytest.mark.parametrize(
    ("summary", "quote"),
    [
        ("One owner's pan lost its coating after 8 months", "lost the coating after 8 months"),
        ("One owner's pan lost its coating after eight months", "after 8 months it flaked"),
        ("Many owners saw the coating flake", "many owners saw the coating flake within a year"),
        ("One tester's pan warped", "the pan warped in our test"),
    ],
)
def test_a_summary_with_only_what_its_quote_holds_passes(summary: str, quote: str) -> None:
    assert summary_fault(summary, quote) is None


@pytest.mark.parametrize(
    ("summary", "quote", "fault"),
    [
        (
            "One owner's pan lost its coating after 6 months",
            "the coating went after half a year",
            "its summary holds a number that is not in its quote",
        ),
        (
            "Many owners report the coating flaking within a year",
            "my coating flaked within a year",
            'its summary generalises ("many", "owners") where its quote does not',
        ),
        (
            "The coating often flakes",
            "the coating flaked on mine",
            'its summary generalises ("often") where its quote does not',
        ),
        (
            "One owner's eco-friendly pan lost its coating",
            "lost its coating",
            "its summary holds a generic environmental term",
        ),
        (
            " ".join(["word"] * 26),
            "word",
            "its summary is longer than 25 words",
        ),
        ("  ", "word", "it has no summary"),
    ],
)
def test_a_summary_that_says_more_than_its_quote_fails(
    summary: str, quote: str, fault: str
) -> None:
    assert summary_fault(summary, quote) == fault


@pytest.mark.parametrize(
    ("quote", "rating"),
    [
        ("Overall rating: 4.5/5 (212 reviews)", "4.5/5"),
        ("Rated 4.5 out of 5 stars", "4.5 out of 5"),
        ("Our score: 8/10", "8/10"),
        ("4,5 van 5 sterren", "4,5 van 5"),
        ("Score 8.1 / 10", "8.1 / 10"),
    ],
)
def test_a_rating_is_its_value_with_its_scale_as_the_quote_writes_it(
    quote: str, rating: str
) -> None:
    assert rating_in(quote) == rating


@pytest.mark.parametrize("quote", ["Rated 4.5 stars", "212 reviews", "5 out of 4", "Excellent"])
def test_a_quote_with_no_value_on_a_scale_holds_no_rating(quote: str) -> None:
    assert rating_in(quote) is None
