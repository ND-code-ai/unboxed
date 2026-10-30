from datetime import timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

import pytest

from shopper.calc.display import car_kilometres, euros, kilograms, whole_minutes, years

CAR_GRAMS_PER_KM = Decimal("96.7")


# "CO2e for scale" in docs/architecture/calculations.md.
@pytest.mark.parametrize(
    ("low", "high", "shown"),
    [
        ("10", "30", ("100", "320")),
        ("5", "37", ("50", "390")),
        ("23", "59", ("230", "620")),
        ("0.5", "2", ("0", "30")),
        # From 1,000 km, two significant figures, as the kilograms beside them have.
        ("100", "2000", ("1,000", "21,000")),
        ("150", "300", ("1,500", "3,200")),
    ],
)
def test_kilometres_for_scale_round_outward_to_tens_and_large_ones_to_two_figures(
    low: str, high: str, shown: tuple[str, str]
) -> None:
    assert car_kilometres(Decimal(low), Decimal(high), CAR_GRAMS_PER_KM) == shown


def test_kilometres_on_a_whole_ten_stay_on_it() -> None:
    assert car_kilometres(Decimal("9.67"), Decimal("19.34"), CAR_GRAMS_PER_KM) == ("100", "200")


def test_kilometres_for_scale_are_left_out_under_ten_at_the_high_end() -> None:
    assert car_kilometres(Decimal("0.1"), Decimal("0.96"), CAR_GRAMS_PER_KM) is None


def test_kilometres_for_scale_keep_a_high_end_of_exactly_ten() -> None:
    assert car_kilometres(Decimal("0.1"), Decimal("0.967"), CAR_GRAMS_PER_KM) == ("0", "10")


# The edge cases of "Display rounding" in docs/architecture/calculations.md.
@pytest.mark.parametrize(
    ("amount", "shown"),
    [
        ("0.004", "under €0.01"),
        ("0.005", "€0.01"),
        ("0.125", "€0.13"),
        ("2.675", "€2.68"),
        ("9.996", "€10"),
        ("12.995", "€13"),
        ("12.5", "€12.50"),
        ("0", "€0"),
    ],
)
def test_an_amount_rounds_half_up_to_the_cent_and_drops_the_cents_of_a_whole_one(
    amount: str, shown: str
) -> None:
    assert euros(Decimal(amount)) == shown


@pytest.mark.parametrize(
    ("value", "shown"),
    [("0.04", "0"), ("0.96", "1"), ("2.25", "2.3"), ("2.96", "3"), ("1.7", "1.7")],
)
def test_years_round_half_up_to_one_decimal_and_drop_the_decimal_of_a_whole_one(
    value: str, shown: str
) -> None:
    assert years(Decimal(value)) == shown


def test_the_ends_of_a_range_of_years_round_outward() -> None:
    assert years(Decimal("2.25"), ROUND_FLOOR) == "2.2"
    assert years(Decimal("2.96"), ROUND_FLOOR) == "2.9"
    assert years(Decimal("2.91"), ROUND_CEILING) == "3"
    assert years(Decimal("0.04"), ROUND_CEILING) == "0.1"


@pytest.mark.parametrize(
    ("value", "rounding", "shown"),
    [
        ("12.2474", ROUND_FLOOR, "12"),
        ("24.4949", ROUND_CEILING, "25"),
        ("2.449", ROUND_FLOOR, "2.4"),
        ("0.675", ROUND_HALF_UP, "0.68"),
        ("5.0", ROUND_HALF_UP, "5"),
        ("0", ROUND_FLOOR, "0"),
        ("150", ROUND_CEILING, "150"),
    ],
)
def test_a_mass_shows_two_significant_figures_rounded_the_given_way(
    value: str, rounding: str, shown: str
) -> None:
    assert kilograms(Decimal(value), rounding) == shown


@pytest.mark.parametrize(
    ("wait", "shown"),
    [
        (timedelta(minutes=50), 50),
        (timedelta(seconds=30), 1),
        (timedelta(minutes=9, seconds=1), 10),
    ],
    ids=["whole minutes", "under a minute", "a second over"],
)
def test_a_wait_is_shown_in_whole_minutes_rounded_up(wait: timedelta, shown: int) -> None:
    assert whole_minutes(wait) == shown
