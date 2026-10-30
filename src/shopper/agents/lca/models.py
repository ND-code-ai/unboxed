"""What the LCA agent's tier 3 call returns: one factor table per report and, per option in the
order given, its inputs pointing at that table and a manufacturing range, or a decline; and what
the checks make of each option. Rules:
docs/architecture/lca.md and docs/adr/0006-tier-3-returns-factors-code-multiplies.md."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from shopper.state import DomainModel, LcaInput


class FactorRow(BaseModel):
    """One material and form, with its emission factor range in kg CO2e per kg."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    material: str
    form: str
    factor_low: float
    factor_high: float


class InputRow(BaseModel):
    """One material of an option. `factor` and `fixed_input` count from 1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    form: str
    factor: int
    mass_kg: float
    fixed_input: int | None
    component: bool


class OptionEstimate(BaseModel):
    """One option's inputs and manufacturing range, or why it was declined."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    inputs: list[InputRow]
    manufacturing_low: float | None
    manufacturing_high: float | None
    declined_because: str | None


class EstimateReply(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    factors: list[FactorRow]
    options: list[OptionEstimate]


class Estimate(DomainModel):
    """An option's checked inputs, factors copied in, and its manufacturing range."""

    inputs: tuple[LcaInput, ...]
    manufacturing_low: Decimal
    manufacturing_high: Decimal


class Declined(DomainModel):
    """No estimate for an option, and why."""

    reason: str
