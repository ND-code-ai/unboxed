"""How often a consumable is replaced and what it costs a year, by the rules in
docs/architecture/option_research.md ("Recurring cost")."""

from decimal import Decimal

import pytest

from shopper.calc.recurring import (
    is_a_pack,
    pack_count,
    recurring_cost_per_year,
    replacements_per_year,
)


@pytest.mark.parametrize(
    ("quote", "per_year"),
    [
        ("replace the filter every 6 months", "2"),
        ("every 2 years", "0.5"),
        ("every 4 weeks", "13"),
        ("every 73 days", "5"),
        ("every month", "12"),
        ("every year", "1"),
        ("replace it yearly", "1"),
        ("annually", "1"),
        ("once a year", "1"),
        ("monthly", "12"),
        ("twice a year", "2"),
        ("elke 6 maanden", "2"),
        ("om de 3 maanden", "4"),
        ("iedere 2 jaar", "0.5"),
        ("jaarlijks vervangen", "1"),
        ("maandelijks", "12"),
        ("twee keer per jaar", "2"),
        ("1 keer per jaar", "1"),
        ("once every two years", "0.5"),
        ("elke drie maanden", "4"),
        ("$36 annual replacement heads", "1"),
        ("jaarlijkse vervanging", "1"),
        ("per year", "1"),
        ("a new bag each month", "12"),
        ("per jaar", "1"),
    ],
)
def test_an_interval_gives_the_replacements_a_year(quote: str, per_year: str) -> None:
    assert replacements_per_year(quote) == Decimal(per_year)


@pytest.mark.parametrize(
    "quote", ["every 6 to 12 months", "every 6-12 months", "elke 6 tot 12 maanden"]
)
def test_a_range_of_intervals_takes_its_long_end(quote: str) -> None:
    assert replacements_per_year(quote) == Decimal(1)


@pytest.mark.parametrize("quote", ["every 50 uses", "after heavy use", "regularly", ""])
def test_an_interval_in_uses_or_none_at_all_is_not_read(quote: str) -> None:
    assert replacements_per_year(quote) is None


def test_the_yearly_cost_is_the_amount_per_piece_times_the_replacements() -> None:
    assert recurring_cost_per_year(Decimal(12), Decimal(2), pack_count=3) == Decimal(8)


def test_a_single_piece_costs_its_amount_each_time() -> None:
    assert recurring_cost_per_year(Decimal("7.50"), Decimal(4)) == Decimal(30)


@pytest.mark.parametrize(
    ("quote", "count"),
    [("a pack of 3", 3), ("set of 2 filters", 2), ("verpakking met 4 stuks", 4), ("10", 10)],
)
def test_a_pack_count_quote_gives_its_one_whole_number(quote: str, count: int) -> None:
    assert pack_count(quote) == count


@pytest.mark.parametrize("quote", ["a pack of filters", "2 or 3 per pack", "0 pieces", ""])
def test_a_pack_count_quote_with_no_one_count_above_zero_is_not_read(quote: str) -> None:
    assert pack_count(quote) is None


@pytest.mark.parametrize(
    ("quote", "pack"),
    [("$15 for a pack", True), ("€12 per set of filters", True), ("€9,95 per stuks", True)],
)
def test_an_amount_for_a_pack_says_so(quote: str, pack: bool) -> None:
    assert is_a_pack(quote) is pack


def test_an_amount_for_one_piece_is_not_a_pack() -> None:
    assert is_a_pack("a replacement filter costs €12") is False


@pytest.mark.parametrize(
    ("quote", "per_year"),
    [
        ("€30 per year", "1"),
        ("costs $30 a year", "1"),
        ("£ 8 per month", "12"),
        ("€12.50 a month", "12"),
        ("€1,50 per maand", "12"),
        ("$15.99 each month", "12"),
        ("£8.40 per year", "1"),
        ("€30.00 per year", "1"),
        ("30 euro a year", "1"),
        ("€12.50 every 6 months", "2"),
        ("USD 36 a year", "1"),
        ("EUR 30 per year", "1"),
    ],
)
def test_an_amount_before_the_unit_is_no_count_of_replacements(quote: str, per_year: str) -> None:
    assert replacements_per_year(quote) == Decimal(per_year)
