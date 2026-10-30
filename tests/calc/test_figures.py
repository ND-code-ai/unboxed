from decimal import Decimal

from shopper.calc.figures import (
    cost_per_use,
    cost_per_year,
    horizon_co2e,
    horizon_cost,
    purchases_over_horizon,
)

CENT = Decimal("0.01")


def test_cost_per_year_of_the_non_stick_pan() -> None:
    assert cost_per_year(Decimal("20"), Decimal("2")) == Decimal("10.00")


def test_cost_per_year_of_the_carbon_steel_pan_is_not_rounded() -> None:
    result = cost_per_year(Decimal("40"), Decimal("30"))

    assert result != Decimal("1.33")
    assert result.quantize(CENT) == Decimal("1.33")


def test_cost_per_year_includes_recurring_costs() -> None:
    assert cost_per_year(Decimal("80"), Decimal("4"), Decimal("25")) == Decimal("45.00")
    assert cost_per_year(Decimal("200"), Decimal("10"), Decimal("10")) == Decimal("30.00")


def test_cost_per_use_of_the_vacuum_cleaners() -> None:
    assert cost_per_use(Decimal("45"), 50) == Decimal("0.90")
    assert cost_per_use(Decimal("30"), 50) == Decimal("0.60")


def test_purchases_over_the_horizon() -> None:
    assert purchases_over_horizon(10, Decimal("2")) == 5
    assert purchases_over_horizon(10, Decimal("4")) == 3
    assert purchases_over_horizon(10, Decimal("10")) == 1


def test_a_lifespan_longer_than_the_horizon_means_one_purchase() -> None:
    assert purchases_over_horizon(10, Decimal("30")) == 1


def test_horizon_cost_of_the_frying_pans() -> None:
    assert horizon_cost(Decimal("20"), 5, 10) == Decimal("100")
    assert horizon_cost(Decimal("40"), 1, 10) == Decimal("40")


def test_horizon_cost_includes_recurring_costs_for_every_year() -> None:
    assert horizon_cost(Decimal("80"), 3, 10, Decimal("25")) == Decimal("490")
    assert horizon_cost(Decimal("200"), 1, 10, Decimal("10")) == Decimal("300")


def test_horizon_co2e_stays_a_range() -> None:
    assert horizon_co2e(Decimal("4"), Decimal("6"), 5) == (Decimal("20"), Decimal("30"))
