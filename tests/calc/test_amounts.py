from decimal import Decimal

import pytest

from shopper.calc.amounts import parse_amount


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("50", "50"),
        ("49,99", "49.99"),
        ("49.99", "49.99"),
        ("1.000", "1000"),
        ("1 000", "1000"),
        ("1.234,56", "1234.56"),
        ("1,234.56", "1234.56"),
        ("12.5", "12.5"),
        (" 49,99 ", "49.99"),
    ],
)
def test_a_separator_before_three_digits_is_thousands_and_before_one_or_two_decimals(
    text: str, amount: str
) -> None:
    assert parse_amount(text) == Decimal(amount)


@pytest.mark.parametrize(
    "text", ["1.2345", "1.234.56", "1,234,56", "12 345,6 7", "", "€", "50 euro"]
)
def test_any_other_pattern_is_not_an_amount(text: str) -> None:
    assert parse_amount(text) is None
