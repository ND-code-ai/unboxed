"""A recurring cost read with its currency (option_research.md, "Recurring cost")."""

from decimal import Decimal

import pytest

from shopper.calc.money import QuotedMoney, quoted_money


@pytest.mark.parametrize(
    ("quote", "amount", "currency"),
    [
        ("€12,95 per filter", "12.95", "EUR"),
        ("12.95 euro", "12.95", "EUR"),
        ("filters cost $15", "15", "$"),
        ("US$15.99 a pack", "15.99", "USD"),
        ("15 USD", "15", "USD"),
        ("£8.50 each", "8.50", "GBP"),
        ("8 GBP", "8", "GBP"),
    ],
)
def test_a_quoted_cost_is_read_with_its_currency(quote: str, amount: str, currency: str) -> None:
    assert quoted_money(quote) == QuotedMoney(amount=Decimal(amount), currency=currency)


@pytest.mark.parametrize("quote", ["CHF 20", "20 kr", "¥2000"])
def test_another_currency_is_named_as_other(quote: str) -> None:
    found = quoted_money(quote)
    assert found is not None and found.currency == "other"


@pytest.mark.parametrize("quote", ["a pack of 3", "€5 to €8", "about 20"])
def test_a_quote_without_one_marked_amount_has_none(quote: str) -> None:
    assert quoted_money(quote) is None
