"""Fixed-rate conversion of a recurring cost (docs/adr/0002)."""

from datetime import date
from decimal import Decimal

from shopper.calc.conversion import FixedRate, to_euros

RATES = {
    "USD": FixedRate(per_euro=Decimal("1.25"), on=date(2026, 10, 16), source="ECB"),
    "GBP": FixedRate(per_euro=Decimal("0.80"), on=date(2026, 10, 16), source="ECB"),
}


def test_an_amount_is_divided_by_the_rate_per_euro() -> None:
    assert to_euros(Decimal(10), "USD", RATES) == Decimal("8.00")
    assert to_euros(Decimal(10), "GBP", RATES) == Decimal("12.50")


def test_the_result_is_rounded_to_the_cent() -> None:
    assert to_euros(Decimal(1), "USD", {"USD": RATES["USD"]._replace(per_euro=Decimal(3))}) == (
        Decimal("0.33")
    )


def test_a_currency_with_no_rate_gives_nothing() -> None:
    assert to_euros(Decimal(10), "CHF", RATES) is None
