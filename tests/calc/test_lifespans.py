"""The lifespan a quote states, by the table in docs/architecture/option_research.md
("Sourced lifespan")."""

from decimal import Decimal

import pytest

from shopper.calc.lifespans import QuotedLifespan, quoted_lifespan


@pytest.mark.parametrize(
    "quote",
    [
        "non-stick pans last 2 to 5 years",
        "they last 2-5 years",
        "gaat tussen 2 en 5 jaar mee",
        "expect 2 – 5 years of use",
        "your pan should last two to five years",
        "most nonstick cookware has a two- to five-year lifespan",
        "they last between 2 and 5 years",
    ],
)
def test_a_range_of_years_gives_its_low_end(quote: str) -> None:
    assert quoted_lifespan(quote) == QuotedLifespan(
        years=Decimal(2), low=Decimal(2), high=Decimal(5)
    )


@pytest.mark.parametrize(
    "quote",
    ["lasts at least 5 years", "will last over 5 years", "good for 5+ years", "lasts five years"],
)
def test_a_lower_bound_gives_that_number(quote: str) -> None:
    assert quoted_lifespan(quote) == QuotedLifespan(years=Decimal(5))


def test_either_of_two_numbers_gives_the_lower() -> None:
    assert quoted_lifespan("good for 2 or 3 years") == QuotedLifespan(
        years=Decimal(2), low=Decimal(2), high=Decimal(3)
    )


def test_a_number_in_two_words_is_read_whole() -> None:
    assert quoted_lifespan("it lasts twenty-five years") == QuotedLifespan(years=Decimal(25))


def test_an_upper_bound_may_have_a_word_between_it_and_the_number() -> None:
    found = quoted_lifespan("lasts up to about 10 years")
    assert found is not None and found.up_to


def test_months_are_converted_to_years() -> None:
    assert quoted_lifespan("it lasted 18 months") == QuotedLifespan(years=Decimal("1.5"))


def test_up_to_is_marked_so_a_makers_claim_can_be_refused() -> None:
    assert quoted_lifespan("lasts up to 10 years") == QuotedLifespan(years=Decimal(10), up_to=True)


@pytest.mark.parametrize(
    "quote",
    [
        "rated for 500 hours of use",
        "good for 3000 cycles",
        "a pan for a lifetime",
        "it will last for generations",
        "a sturdy pan",
    ],
)
def test_hours_cycles_and_a_lifetime_give_no_years(quote: str) -> None:
    assert quoted_lifespan(quote) is None
