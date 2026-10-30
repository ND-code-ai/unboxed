"""The CO2e of a model estimate, by the worked examples in docs/architecture/calculations.md
("CO2e of a model estimate")."""

from decimal import Decimal

import pytest

from samples import MODEL_ESTIMATE as ESTIMATE
from shopper.calc.co2e import WeightScaling, estimated_co2e, scaled_to_weight
from shopper.state import LcaInput, Source, SourceKind

PAGE = Source(kind=SourceKind.URL, reference="https://www.example.com/shop/pan")
SPREAD = Decimal(2)
WINDOW = (Decimal("0.5"), Decimal(2))


def material(
    mass: str,
    low: str = "1",
    high: str = "2",
    name: str = "steel",
    mass_source: Source = ESTIMATE,
    component: bool = False,
) -> LcaInput:
    return LcaInput(
        name=name,
        material_source=ESTIMATE,
        component=component,
        mass_kg=Decimal(mass),
        mass_source=mass_source,
        factor_low=Decimal(low),
        factor_high=Decimal(high),
        factor_source=ESTIMATE,
    )


def kettle(body: str, housing: str) -> tuple[LcaInput, ...]:
    """The kettle of the weight scaling example: two assumed bulk materials and a component."""
    return (
        material(body, name="stainless steel"),
        material(housing, name="polypropylene"),
        material("0.2", name="heating element", component=True),
    )


@pytest.mark.parametrize(
    "inputs, manufacturing, expected",
    [
        pytest.param((material("1.5", "2", "4"),), ("1", "2"), ("4", "8"), id="at 2x"),
        pytest.param((material("1", "1.5", "4"),), ("0.5", "1"), ("2", "5"), id="above 2x"),
        pytest.param((material("2", "3.5", "4"),), ("1", "1"), ("6", "12"), id="below 2x"),
        pytest.param(
            (material("0.5", "1", "3"), material("0.25", "2", "6")),
            ("11.5", "13"),
            ("10", "20"),
            id="materials over 2x, total under",
        ),
    ],
)
def test_the_range_is_the_sum_widened_to_at_least_the_spread(
    inputs: tuple[LcaInput, ...], manufacturing: tuple[str, str], expected: tuple[str, str]
) -> None:
    low, high = manufacturing

    assert estimated_co2e(inputs, Decimal(low), Decimal(high), SPREAD) == (
        Decimal(expected[0]),
        Decimal(expected[1]),
    )


@pytest.mark.parametrize(
    "weight, scale, body, housing",
    [
        pytest.param("1.4", "1.5", "0.9", "0.3", id="inside the window"),
        pytest.param("1.8", "2", "1.2", "0.4", id="at its top"),
        pytest.param("0.6", "0.5", "0.3", "0.1", id="at its bottom"),
    ],
)
def test_assumed_bulk_masses_are_scaled_to_the_stated_weight(
    weight: str, scale: str, body: str, housing: str
) -> None:
    assert scaled_to_weight(kettle("0.6", "0.2"), Decimal(weight), WINDOW) == WeightScaling(
        inputs=kettle(body, housing), scale=Decimal(scale), scaled=True
    )


@pytest.mark.parametrize(
    "weight, scale",
    [pytest.param("2.2", "2.5", id="above"), pytest.param("0.5", "0.375", id="below")],
)
def test_a_scale_outside_the_window_keeps_every_mass(weight: str, scale: str) -> None:
    assert scaled_to_weight(kettle("0.6", "0.2"), Decimal(weight), WINDOW) == WeightScaling(
        inputs=kettle("0.6", "0.2"), scale=Decimal(scale), scaled=False
    )


def test_a_sourced_mass_is_left_untouched() -> None:
    body = material("1", name="carbon steel", mass_source=PAGE)

    scaling = scaled_to_weight((body, material("0.2", name="beech")), Decimal("1.3"), WINDOW)

    assert scaling == WeightScaling(
        inputs=(body, material("0.3", name="beech")), scale=Decimal("1.5"), scaled=True
    )


def test_with_no_assumed_bulk_mass_there_is_nothing_to_scale() -> None:
    inputs = (
        material("1", mass_source=PAGE),
        material("0.2", name="heating element", component=True),
    )

    assert scaled_to_weight(inputs, Decimal("1.5"), WINDOW) == WeightScaling(
        inputs=inputs, scale=None, scaled=False
    )
