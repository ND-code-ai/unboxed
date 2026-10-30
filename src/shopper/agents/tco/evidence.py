"""Step 6 of option research: one evidence search per product option and one read of its
results, for its lifespan, its durability evidence, its recurring cost and its factor values.

Code accepts what the read returns only by the rules in docs/architecture/option_evidence.md
("Evidence"): the lifespan and the durability evidence in `durability.py`, the recurring cost
in `recurring_cost.py`, the factor values in `answers.py`. This module searches, reads and puts
the result on the option.
"""

from collections.abc import Sequence
from typing import NamedTuple

from shopper import wording
from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.research import distinct_results, full_text, numbered
from shopper.agents.tco.answers import Fits, answers_input, factor_values
from shopper.agents.tco.checks import search_name
from shopper.agents.tco.durability import durability_evidence, estimated_lifespan, lifespans
from shopper.agents.tco.models import (
    AnsweredFactor,
    EvidenceContext,
    EvidenceReading,
    FailedAnswer,
    RecurringCost,
)
from shopper.agents.tco.prompt import EVIDENCE_INPUT, EVIDENCE_PROMPT
from shopper.agents.tco.recurring_cost import recurring_cost
from shopper.agents.tco.trail import by_model, counted, entry, left_out, searched
from shopper.config import (
    EVIDENCE_MAX_TOKENS,
    EVIDENCE_TEMPLATE,
    EVIDENCE_TIMEOUT_SECONDS,
    RAW_CONTENT_MAX_CHARACTERS,
    SearchPurpose,
    Tier,
)
from shopper.llm import ChatModel, Completion, LlmFailure, complete_structured
from shopper.state import FactorKind, ProductOption, RecurringCostState, TrailEntry, TrailKind
from shopper.tools.results import PageFetch, ProductPage, SearchResult, WebSearch

EVIDENCE_TIER: Tier = "medium"
# The read reasons in full: it weighs who is speaking and what a quote is about.
EVIDENCE_LOW_EFFORT = False
COULD_NOT_BE_READ = "durability evidence could not be read"


class Subject(NamedTuple):
    """A product option, its own page when there is one, and whether it is the linked product,
    which is never removed."""

    option: ProductOption
    page: SearchResult | None = None
    linked: bool = False


class Evidenced(NamedTuple):
    """The option with its evidence; `removed` when it fails an answer and is not the linked
    product."""

    option: ProductOption
    trail: tuple[TrailEntry, ...]
    removed: bool = False


async def with_page(subject: Subject, fetch: PageFetch) -> Subject:
    """The linked product with its own page as one more result; the page was read before, so
    the fetch is a cache hit."""
    link = subject.option.link
    if link is None:
        return subject
    return subject._replace(page=own_page(await fetch(link)))


def own_page(page: ProductPage) -> SearchResult | None:
    """A product page as one more result of the read, cut to the text limit; missing when it
    could not be read or has no text."""
    if page.failure is not None or not page.markdown.strip():
        return None
    text = page.markdown[:RAW_CONTENT_MAX_CHARACTERS]
    return SearchResult(url=page.url, title=page.name or "", content=text)


async def option_evidence(
    subject: Subject,
    category: str | None,
    look_for_recurring: bool,
    chat: ChatModel,
    search: WebSearch,
    *,
    answered: Sequence[AnsweredFactor] = (),
    template: str = EVIDENCE_TEMPLATE,
) -> Evidenced:
    """The option with its lifespan, its durability evidence, its recurring cost and a value per
    answered factor.

    The search query holds a name a model or a page wrote, so it is searched as a model's query.
    A failed search still gets a read of what is left, so the option still gets an estimate.
    `template` is the config's; the live check of task 1.8.3 passes the ones it compares.
    """
    option = subject.option
    outcome = await search(
        template.format(product=search_name(option.name, option.brand)),
        SearchPurpose.EVIDENCE,
        follow_up=True,
    )
    found = outcome.results if outcome.failure is None else ()
    own = () if subject.page is None else (subject.page,)
    results = tuple(full_text(result) for result in distinct_results((*found, *own)))
    context = EvidenceContext(option, option.brand, category or "", results)
    reply = await _read(option, category, look_for_recurring, answered, results, chat)
    if isinstance(reply, LlmFailure):
        missing = entry(
            TrailKind.EXCLUDED, f'No lifespan for "{option.name}"', reason=COULD_NOT_BE_READ
        )
        state = (
            RecurringCostState.NOT_FOUND
            if look_for_recurring
            else RecurringCostState.NOT_LOOKED_FOR
        )
        fits = factor_values(context, answered, None, not_read=COULD_NOT_BE_READ)
        update = {"recurring_cost_state": state, "factor_values": fits.values}
        return Evidenced(
            option.model_copy(update=update),
            (searched(outcome), by_model(missing, reply), *fits.trail),
        )
    evidenced = _evidenced(context, look_for_recurring, reply, answered, linked=subject.linked)
    read = entry(
        TrailKind.FOUND,
        f'Read the evidence for "{option.name}": '
        f"{counted(_cited(reply.value), 'result')} cited of {len(results)} shown",
    )
    return evidenced._replace(trail=(searched(outcome), by_model(read, reply), *evidenced.trail))


async def _read(
    option: ProductOption,
    category: str | None,
    look_for_recurring: bool,
    answered: Sequence[AnsweredFactor],
    results: Sequence[SearchResult],
    chat: ChatModel,
) -> Completion[EvidenceReading] | LlmFailure:
    return await complete_structured(
        chat,
        EVIDENCE_TIER,
        EVIDENCE_INPUT.format(
            name=option.name,
            brand=option.brand or "not known",
            category=category or "not known",
            consumables="yes" if look_for_recurring else "no",
            answers=answers_input(answered),
            results=numbered(results) or "None.",
        ),
        EvidenceReading,
        system=EVIDENCE_PROMPT,
        max_tokens=EVIDENCE_MAX_TOKENS,
        timeout=EVIDENCE_TIMEOUT_SECONDS,
        low_effort=EVIDENCE_LOW_EFFORT,
    )


def _cited(reading: EvidenceReading) -> int:
    items = (reading.warranty, reading.repairability, reading.wear_material, reading.care)
    numbers = {each.result for each in (*reading.lifespans, *items) if each is not None}
    if reading.consumable is not None:
        numbers.add(reading.consumable.result)
    return len(numbers)


def _evidenced(
    context: EvidenceContext,
    look_for_recurring: bool,
    reply: Completion[EvidenceReading],
    answered: Sequence[AnsweredFactor],
    *,
    linked: bool,
) -> Evidenced:
    """The option with what passed the checks, and the trail of the rest; removed when it fails
    an answer that is not about care and is not the linked product."""
    option, reading = context.option, reply.value
    no_brand = () if context.brand is not None else (_no_brand(option.name),)
    found = lifespans(context, reading)
    evidence, evidence_trail = durability_evidence(context, reading, found.typical)
    estimate_trail: tuple[TrailEntry, ...] = ()
    lifespan = found.sourced
    if lifespan is None:
        lifespan, estimated = estimated_lifespan(option.name, reading, evidence, reply.model)
        estimate_trail = (estimated,)
    cost, cost_trail = (
        recurring_cost(context, reading)
        if look_for_recurring
        else (RecurringCost(state=RecurringCostState.NOT_LOOKED_FOR), ())
    )
    fits = factor_values(context, answered, reading)
    updated = option.model_copy(
        update={
            "lifespan_years": lifespan.years,
            "lifespan_source": lifespan.source,
            "durability_evidence": evidence,
            **_recurring_fields(cost),
            "factor_values": fits.values,
        }
    )
    removed = () if linked else _removed(option.name, fits)
    trail = (
        *no_brand,
        *found.trail,
        *evidence_trail,
        *estimate_trail,
        *cost_trail,
        *fits.trail,
        *removed,
        *_gaps(option.name, reading),
    )
    return Evidenced(updated, tuple(by_model(each, reply) for each in trail), bool(removed))


def _removed(name: str, fits: Fits) -> tuple[TrailEntry, ...]:
    """The excluded entry of an option that fails an answer; a care factor removes nothing."""
    failed = [each for each in fits.failed if each.factor.kind is not FactorKind.CARE]
    if not failed:
        return ()
    return (left_out(name, "; ".join(_does_not_meet(each) for each in failed)),)


def _does_not_meet(failed: FailedAnswer) -> str:
    site = wording.site_name(failed.url)
    return f'it does not meet your answer about {failed.factor.name}: "{failed.quote}" ({site})'


def _recurring_fields(cost: RecurringCost) -> dict[str, object]:
    return {
        "recurring_cost_state": cost.state,
        "recurring_cost_per_year": cost.per_year,
        "recurring_cost_source": cost.source,
        "recurring_cost_converted_from": cost.converted_from,
        "other_consumables_left_out": cost.others_left_out,
    }


def _no_brand(name: str) -> TrailEntry:
    return entry(
        TrailKind.DECIDED,
        f'No sourced lifespan, warranty or recurring cost for "{name}"',
        reason="its product page names no brand, so no result can be checked to name it",
    )


def _gaps(name: str, reading: EvidenceReading) -> tuple[TrailEntry, ...]:
    """A trail entry per gap the read reported; a gap never becomes a value."""
    return tuple(
        entry(
            TrailKind.DECIDED,
            f'Not covered for "{name}": {gap.what.strip()}',
            reason=gap.reason.strip(),
        )
        for gap in reading.gaps
        if gap.what.strip()
        and gap.reason.strip()
        and fault_in(gap.what) is None
        and fault_in(gap.reason) is None
    )
