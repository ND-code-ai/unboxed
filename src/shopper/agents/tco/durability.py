"""What an evidence read says about how long a product option lasts: its sourced or estimated
lifespan, and its durability evidence.

Rules: docs/architecture/option_evidence.md ("Evidence": "What must name the product",
"Sourced lifespan", "Estimated lifespan", "Durability evidence").
"""

import re
from decimal import Decimal
from typing import NamedTuple

from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.phrases import find_phrase
from shopper.agents.tco.checks import promises_a_lifetime, years_in
from shopper.agents.tco.evidence_checks import (
    brand_fault,
    cited_source,
    quote_fault,
    value_fault,
)
from shopper.agents.tco.models import (
    EvidenceContext,
    EvidenceKind,
    EvidenceReading,
    Lifespan,
    ReadEvidenceItem,
    ReadLifespan,
    ReadWarranty,
)
from shopper.agents.tco.trail import entry, left_out_of
from shopper.calc.lifespans import QuotedLifespan, quoted_lifespan
from shopper.config import LEGAL_GUARANTEE_YEARS, LIFESPAN_ESTIMATE_YEARS
from shopper.state import (
    DurabilityEvidence,
    Source,
    Sourced,
    SourceKind,
    StatedBy,
    TrailEntry,
    TrailKind,
    TypicalLifespan,
    WarrantyTerm,
)

ROUGH_ESTIMATE_LABEL = "rough estimate"
ONE_NUMBER_FOR_THE_TYPE = (
    "a lifespan typical for the type is a range of years, and its quote states one number"
)
_TESTERS_AND_OWNERS = frozenset({StatedBy.TESTER, StatedBy.OWNER})
# A warranty that covers defects and not wear says so: "limited lifetime warranty".
_LIMITED = re.compile(r"\b(?:limited|beperkte?)\b", re.IGNORECASE)


class Lifespans(NamedTuple):
    """The sourced lifespan, if one stands; the type-level lifespan, if one stands; the trail."""

    sourced: Lifespan | None
    typical: Sourced[TypicalLifespan] | None
    trail: tuple[TrailEntry, ...]


def lifespans(context: EvidenceContext, reading: EvidenceReading) -> Lifespans:
    """Of the lifespans that pass, a tester's or owner's wins over a manufacturer's or seller's,
    then the lowest; one about the type is never sourced, and becomes the typical range."""
    kept: list[tuple[ReadLifespan, QuotedLifespan]] = []
    typical: Sourced[TypicalLifespan] | None = None
    trail: list[TrailEntry] = []
    name = context.option.name
    for read in reading.lifespans:
        quoted, fault = _lifespan_fault(context, read)
        if fault is not None or quoted is None:
            trail.append(left_out_of(name, "a lifespan", fault or "it states no years"))
        elif read.about != "type":
            kept.append((read, quoted))
        elif quoted.low is None or quoted.high is None:
            trail.append(left_out_of(name, "a lifespan", ONE_NUMBER_FOR_THE_TYPE))
        elif typical is None:
            source = cited_source(read, context.results)
            value = TypicalLifespan(low=quoted.low, high=quoted.high, type=_type_named(read))
            typical = Sourced(value=value, source=source)
    if not kept:
        return Lifespans(None, typical, tuple(trail))
    read, quoted = min(
        kept, key=lambda pair: (pair[0].stated_by not in _TESTERS_AND_OWNERS, pair[1].years)
    )
    source = cited_source(read, context.results)
    found = entry(
        TrailKind.FOUND,
        f'Lifespan of "{name}": {quoted.years:f} {"year" if quoted.years == 1 else "years"}',
        reason=f"stated about the {read.about} by {read.stated_by}",
        source=source,
    )
    return Lifespans(Lifespan(quoted.years, source), typical, (*trail, found))


def _type_named(read: ReadLifespan) -> str | None:
    """The type a quote about the type names, when it stands in the quote as the read wrote it."""
    named = (read.type or "").strip()
    if not named or fault_in(named) is not None or find_phrase(named, read.quote) is None:
        return None
    return named


def _lifespan_fault(
    context: EvidenceContext, read: ReadLifespan
) -> tuple[QuotedLifespan | None, str | None]:
    fault = quote_fault(read.result, read.quote, context.results, holds_a_number=True)
    if fault is not None:
        return None, fault
    quoted = quoted_lifespan(read.quote)
    if quoted is None:
        return None, "its quote states no years or months"
    if read.about == "type":
        return quoted, None
    if quoted.up_to:
        return None, "an upper bound is not a lifespan"
    fault = brand_fault(context, read.result, read.quote, about=read.about)
    return (None, fault) if fault is not None else (quoted, None)


def estimated_lifespan(
    name: str, reading: EvidenceReading, evidence: DurabilityEvidence, model: str
) -> tuple[Lifespan, TrailEntry]:
    """The read's estimate in whole years, kept between the limits and inside the type's range,
    with the evidence it rests on that passed the checks."""
    low, high = LIFESPAN_ESTIMATE_YEARS
    years = Decimal(min(max(reading.estimated_years, low), high))
    typical = evidence.typical_lifespan
    if typical is not None:
        years = min(max(years, typical.value.low), typical.value.high)
    estimated = entry(
        TrailKind.DECIDED,
        f'Estimated the lifespan of "{name}" at {years:f} {"year" if years == 1 else "years"}',
        reason=_rests_on(reading, evidence),
    )
    source = Source(kind=SourceKind.MODEL_ESTIMATE, reference=model, label=ROUGH_ESTIMATE_LABEL)
    return Lifespan(years, source), estimated


def _rests_on(reading: EvidenceReading, evidence: DurabilityEvidence) -> str:
    """What the estimate rests on, of the kinds the read named, only those that passed."""
    kept: dict[EvidenceKind, object] = {
        "lifespan": evidence.typical_lifespan,
        "warranty": evidence.warranty,
        "repairability": evidence.repairability,
        "wear_material": evidence.wear_material,
        "care": evidence.care,
    }
    standing = [kind for kind in dict.fromkeys(reading.estimate_rests_on) if kept[kind]]
    if standing:
        return "rests on: " + ", ".join(_words(kind) for kind in standing)
    if reading.estimate_rests_on:
        return "none of the evidence it rests on passed the checks"
    if any(kept.values()):
        return "the read named no evidence it rests on"
    return "no durability evidence was found"


def durability_evidence(
    context: EvidenceContext, reading: EvidenceReading, typical: Sourced[TypicalLifespan] | None
) -> tuple[DurabilityEvidence, tuple[TrailEntry, ...]]:
    """One item per kind that passes its checks, and the type-level lifespan."""
    warranty, warranty_trail = _warranty(context, reading.warranty)
    repairability, repairability_trail = _item(context, "repairability", reading.repairability)
    wear_material, wear_trail = _item(context, "wear_material", reading.wear_material)
    care, care_trail = _item(context, "care", reading.care)
    evidence = DurabilityEvidence(
        warranty=warranty,
        repairability=repairability,
        wear_material=wear_material,
        care=care,
        typical_lifespan=typical,
    )
    return evidence, (*warranty_trail, *repairability_trail, *wear_trail, *care_trail)


def _warranty(
    context: EvidenceContext, read: ReadWarranty | None
) -> tuple[Sourced[WarrantyTerm] | None, tuple[TrailEntry, ...]]:
    """A warranty of a lifetime or longer than the legal guarantee, from a result naming it."""
    if read is None:
        return None, ()
    lifetime = promises_a_lifetime(read.quote)
    years = None if lifetime else years_in(read.quote)
    fault = quote_fault(read.result, read.quote, context.results, holds_a_number=True)
    fault = fault or brand_fault(context, read.result, read.quote)
    if fault is None and not lifetime and years is None:
        fault = "its quote states no length"
    if fault is None and years is not None and years <= LEGAL_GUARANTEE_YEARS:
        fault = "it is no longer than the EU legal guarantee, which says nothing about this product"
    if fault is not None:
        return None, (left_out_of(context.option.name, "a warranty", fault),)
    limited = _LIMITED.search(read.quote) is not None
    term = (
        WarrantyTerm(lifetime=True, limited=limited)
        if lifetime
        else WarrantyTerm(years=years, limited=limited)
    )
    return Sourced(value=term, source=cited_source(read, context.results)), ()


def _item(
    context: EvidenceContext, kind: EvidenceKind, read: ReadEvidenceItem | None
) -> tuple[Sourced[str] | None, tuple[TrailEntry, ...]]:
    """A text item, accepted from any cited result."""
    if read is None:
        return None, ()
    fault = quote_fault(
        read.result, read.quote, context.results, holds_a_number=False
    ) or value_fault(read.value, read.quote)
    if fault is not None:
        return None, (left_out_of(context.option.name, _words(kind), fault),)
    return Sourced(value=read.value.strip(), source=cited_source(read, context.results)), ()


def _words(kind: EvidenceKind) -> str:
    return kind.replace("_", " ")
