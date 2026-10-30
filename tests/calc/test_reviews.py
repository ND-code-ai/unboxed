import pytest

from shopper.calc.reviews import review_count


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("4.5/5 (212 reviews)", 212),
        ("4,5 van 5 sterren, 1.234 beoordelingen", 1234),
        ("Rated 4.6 out of 5 from 1,234 ratings", 1234),
        ("4.4 von 5 Sternen 2 345 Bewertungen", 2345),
        ("8/10 op basis van 37 recensies", 37),
        ("one review: 5/5, 1 review", 1),
    ],
)
def test_the_review_count_is_the_number_before_a_word_for_reviews(text: str, count: int) -> None:
    assert review_count(text) == count


@pytest.mark.parametrize(
    "text",
    [
        "4.5/5",
        "Rated 4.5 out of 5 by owners",
        "12 months later",
        "4.5/5 rating",
        "4.5 / 5 rating",
        "Rated 4.5 out of 5 rating",
        "4,5 van 5 beoordeling",
    ],
)
def test_a_rating_with_no_number_before_a_word_for_reviews_has_no_count(text: str) -> None:
    assert review_count(text) is None
