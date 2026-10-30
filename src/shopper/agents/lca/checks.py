"""The checks on the model's estimate, and the inputs built from it. Pure.

Entries are matched to options by position; the name each echoes must be the option's. A
missing or duplicate entry, a decline, and inputs that fail a check each give the option no
result (docs/architecture/lca.md, "Rules").
"""

import math
import re
from collections import Counter
from collections.abc import Sequence
from decimal import Decimal

from shopper.agents.lca.models import (
    Declined,
    Estimate,
    EstimateReply,
    FactorRow,
    InputRow,
    OptionEstimate,
)
from shopper.config import LCA_FACTOR_BOUNDS, WEIGHT_TWICE_TIMES
from shopper.state import LcaInput, ProductOption, Source


def estimates(
    options: Sequence[ProductOption], reply: EstimateReply, estimated: Source
) -> tuple[Estimate | Declined, ...]:
    """One outcome per option, in the options' order."""
    echoed = Counter(_name_key(entry.name) for entry in reply.options)
    given = Counter(_name_key(option.name) for option in options)
    return tuple(
        _outcome(option, _entry_at(reply.options, position), reply.factors, estimated)
        if echoed[_name_key(option.name)] <= given[_name_key(option.name)]
        else Declined(reason="the model's answer gives it more than once")
        for position, option in enumerate(options)
    )


def _entry_at(entries: Sequence[OptionEstimate], position: int) -> OptionEstimate | None:
    return entries[position] if position < len(entries) else None


def _outcome(
    option: ProductOption,
    entry: OptionEstimate | None,
    factors: Sequence[FactorRow],
    estimated: Source,
) -> Estimate | Declined:
    if entry is None or _name_key(entry.name) != _name_key(option.name):
        return Declined(reason="the model's answer has no entry for it in its place")
    if entry.declined_because is not None:
        return Declined(reason=f"the model declined it: {entry.declined_because.strip()}")
    cleaned = _pointing_at_materials_only(option, entry)
    problem = _problem(option, cleaned, factors) or _weight_twice_problem(option, entry, cleaned)
    if problem is not None:
        return Declined(reason=f"its inputs failed a check: {problem}")
    return _estimate(option, cleaned, factors, estimated)


def _weight_twice_problem(
    option: ProductOption, entry: OptionEstimate, cleaned: OptionEstimate
) -> str | None:
    """A dropped pointer may have been a row holding the page's whole weight, on top of the
    materials: masses far above that weight say so, and scaling would not always catch it."""
    if entry == cleaned or option.weight_kg is None:
        return None
    total = sum(row.mass_kg for row in cleaned.inputs)
    if total < WEIGHT_TWICE_TIMES * float(option.weight_kg):
        return None
    return f"a row may count the page's weight of {option.weight_kg} kg as a material"


def _pointing_at_materials_only(option: ProductOption, entry: OptionEstimate) -> OptionEstimate:
    """A row that points at no page material, such as the page's weight or a number the option
    does not list, is the model's own material: the pointer goes and its name, factor and mass stay
    checked and marked as estimated. A page material it should have named is still found missing.
    The live slip of 30 October (docs/architecture/lca.md, "Rules")."""
    pages = range(1, len(option.materials) + 1)
    return entry.model_copy(
        update={
            "inputs": [
                row
                if row.fixed_input is None or row.fixed_input in pages
                else row.model_copy(update={"fixed_input": None})
                for row in entry.inputs
            ]
        }
    )


def _name_key(name: str) -> str:
    """The name without case, spacing or punctuation, so an echo matches its option."""
    return re.sub(r"[\W_]+", "", name.casefold())


def _problem(
    option: ProductOption, entry: OptionEstimate, factors: Sequence[FactorRow]
) -> str | None:
    """What makes the entry unusable, the first problem found; none when it can be summed."""
    if not entry.inputs:
        return "no material was given"
    low, high = entry.manufacturing_low, entry.manufacturing_high
    if low is None or high is None:
        return "no manufacturing range was given"
    # Making a manufactured good takes energy: a zero is a gap, never summed as zero.
    if not _finite(low, high) or low <= 0 or low > high:
        return f"the manufacturing range {low} to {high} kg CO2e is not a range above 0"
    problems = (_input_problem(option, row, factors) for row in entry.inputs)
    found = next((problem for problem in problems if problem is not None), None)
    return found or _page_material_problem(option, entry)


def _page_material_problem(option: ProductOption, entry: OptionEstimate) -> str | None:
    """A page material left out, or given as two inputs, which would count its mass twice."""
    pointed = Counter(row.fixed_input for row in entry.inputs if row.fixed_input is not None)
    twice = next((number for number, count in pointed.items() if count > 1), None)
    if twice is not None:
        return f"the page's material {option.materials[twice - 1].name} is given twice"
    used = set(pointed)
    left_out = (
        material.name
        for number, material in enumerate(option.materials, start=1)
        if number not in used
    )
    name = next(left_out, None)
    return None if name is None else f"the page's material {name} was left out"


def _input_problem(
    option: ProductOption, row: InputRow, factors: Sequence[FactorRow]
) -> str | None:
    if not 1 <= row.factor <= len(factors):
        return f"{row.name} points at factor {row.factor}, which is not in the table"
    factor = factors[row.factor - 1]
    lowest, highest = LCA_FACTOR_BOUNDS
    if not _finite(factor.factor_low, factor.factor_high) or not (
        lowest <= factor.factor_low <= factor.factor_high <= highest
    ):
        return (
            f"the factor of {factor.material} is not a range within {lowest:g} to "
            f"{highest:g} kg CO2e per kg"
        )
    named = [_material_key(other) for other in factors].count(_material_key(factor))
    if named > 1:
        return f"the factor table gives {factor.material}, {factor.form} {named} times"
    if not _finite(row.mass_kg) or row.mass_kg <= 0:
        return f"the mass of {row.name} is not above 0"
    if (_key(row.name), _key(row.form)) != _material_key(factor):
        return f"{row.name}, {row.form} points at the factor of {factor.material}"
    if row.fixed_input is None:
        return None
    stated = option.materials[row.fixed_input - 1].form
    if stated and stated.strip().lower() != factor.form.strip().lower():
        return f"the page states {stated} {row.name}, but its factor is for {factor.form}"
    return None


def _material_key(factor: FactorRow) -> tuple[str, str]:
    return _key(factor.material), _key(factor.form)


def _key(text: str) -> str:
    return " ".join(text.split()).lower()


def _finite(*numbers: float) -> bool:
    return all(math.isfinite(number) for number in numbers)


def _estimate(
    option: ProductOption,
    entry: OptionEstimate,
    factors: Sequence[FactorRow],
    estimated: Source,
) -> Estimate:
    """The checked entry's inputs and manufacturing range, as decimals."""
    assert entry.manufacturing_low is not None and entry.manufacturing_high is not None
    return Estimate(
        inputs=tuple(_input(option, row, factors, estimated) for row in entry.inputs),
        manufacturing_low=_decimal(entry.manufacturing_low),
        manufacturing_high=_decimal(entry.manufacturing_high),
    )


def _input(
    option: ProductOption, row: InputRow, factors: Sequence[FactorRow], estimated: Source
) -> LcaInput:
    """The input with its factor copied from the table, and the page's material, form and mass
    in place of the model's when the row is a fixed input."""
    factor = factors[row.factor - 1]
    mass = _decimal(row.mass_kg)
    form = _key(factor.form) or None
    named = LcaInput(
        name=_key(factor.material),
        form=form,
        form_source=None if form is None else estimated,
        material_source=estimated,
        component=row.component,
        mass_kg=mass,
        mass_source=estimated,
        factor_low=_decimal(factor.factor_low),
        factor_high=_decimal(factor.factor_high),
        factor_source=estimated,
    )
    if row.fixed_input is None:
        return named
    material = option.materials[row.fixed_input - 1]
    mass_given = material.mass_kg is not None and material.mass_kg > 0
    form_stated = bool(material.form)
    return named.model_copy(
        update={
            "name": material.name,
            "form": material.form if form_stated else named.form,
            "form_source": material.source if form_stated else named.form_source,
            "material_source": material.source,
            "mass_kg": material.mass_kg if mass_given else mass,
            "mass_source": material.source if mass_given else estimated,
        }
    )


def _decimal(number: float) -> Decimal:
    return Decimal(str(number))
