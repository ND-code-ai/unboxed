"""The TCO analyzer, the steps of option research: the listing pages, the judgement by name,
the product pages, the judgement by page, selection, and evidence with findings at the same
time.

Code runs the loop: it searches, reads the pages, gives the model what it judges and checks what
comes back. Rules: docs/architecture/option_research.md and docs/architecture/data_sources.md
("Research rules"). This module knows nothing of the graph.
"""

import asyncio
from collections.abc import Sequence
from decimal import Decimal
from typing import NamedTuple

from shopper import wording
from shopper.agents.bundle import TcoOutput
from shopper.agents.tco.answers import answered_factors
from shopper.agents.tco.checks import same_product
from shopper.agents.tco.evidence import Evidenced, Subject, option_evidence, own_page, with_page
from shopper.agents.tco.findings import option_findings, with_findings
from shopper.agents.tco.judgement import judged_by_name, judged_by_page, judgement_words
from shopper.agents.tco.listing_pages import listed_candidates
from shopper.agents.tco.models import AnsweredFactor, Candidate, Offered, PageContext, Slot
from shopper.agents.tco.page_read import names_a_size
from shopper.agents.tco.product_pages import read_order, read_product_pages
from shopper.agents.tco.selection import CHEAPEST, refill, select, why_not_selected
from shopper.agents.tco.trail import entry, left_out
from shopper.calc.budget import with_shipping
from shopper.calc.display import euros
from shopper.llm import ChatModel
from shopper.state import (
    Answer,
    DecisionFactor,
    FactorKind,
    ProductOption,
    Question,
    Request,
    Source,
    SourceKind,
    TrailEntry,
    TrailKind,
    Warning,
    WarningCode,
)
from shopper.tools.results import PageFetch, WebSearch

OPTION_ID = "option-{number}"


class Picked(NamedTuple):
    """A product option made from a slot's candidate, with the slot it took."""

    slot: str
    offered: Offered
    option: ProductOption


async def research_options(
    request: Request,
    linked_product: ProductOption | None,
    local_term: str | None,
    factors: Sequence[DecisionFactor],
    questions: Sequence[Question],
    answers: Sequence[Answer],
    chat: ChatModel,
    search: WebSearch,
    fetch: PageFetch,
) -> TcoOutput:
    """Up to three product options with their prices, the linked product first among them.

    The listing pages of the comparison sites name the candidates; each is judged by its name,
    the product pages are read in order and judged again, and selection keeps the cheapest, the
    durable pick and the durable pick within budget; with a linked product it holds the first
    place. Each option then gets its evidence and its findings, both at once, and a slot whose
    option fails an answer is refilled once.
    """
    category = request.category
    to_judge = answered_factors(factors, questions, answers)
    if category is None:
        return await _without_category(linked_product, to_judge, chat, search, fetch)
    listed = await listed_candidates(category, local_term, search, fetch)
    candidates, linked_trail = _without_linked(listed.candidates, linked_product, category)
    by_name = await judged_by_name(category, candidates, chat)
    order, order_trail = read_order(by_name.candidates, request.budget)
    context = PageContext(category, listed.name_term, by_name.set_requested, _sized(candidates))
    reads = await read_product_pages(order, context, chat, fetch, pages_read=listed.pages_read)
    by_page = await judged_by_page(category, reads.offered, chat)
    slots = select(by_page.offered, request.budget, linked=linked_product is not None)
    taken = tuple((slot.name, slot.taken) for slot in slots if slot.taken is not None)
    picked = tuple(
        Picked(name, offered, _option(offered, number))
        for number, (name, offered) in enumerate(taken, start=1)
    )
    look_for = looks_for_recurring(factors)
    linked = await _linked_evidence(
        linked_product, category, look_for, to_judge, chat, search, fetch
    )
    evidenced = await asyncio.gather(
        *(
            _evidence_and_findings(
                _subject(each.offered, each.option), category, look_for, to_judge, chat, search
            )
            for each in picked
        )
    )
    refilled = await _refilled(
        picked,
        evidenced,
        by_page.offered,
        request.budget,
        category,
        look_for,
        to_judge,
        chat,
        search,
    )
    kept = tuple(each.option for each in (*linked, *refilled.evidenced) if not each.removed)
    return TcoOutput(
        options=kept,
        trail=(
            *listed.trail,
            *linked_trail,
            *by_name.trail,
            *order_trail,
            *reads.trail,
            *by_page.trail,
            *_linked_entries(linked_product),
            *_slot_entries(slots),
            *_not_selected(by_page.offered, slots, request.budget),
            *(each for option in (*linked, *evidenced) for each in option.trail),
            *refilled.trail,
        ),
        warnings=_warnings(
            category,
            kept,
            failed=listed.failed or reads.failed,
            removed_by_answers=any(each.removed for each in (*evidenced, *refilled.evidenced)),
            read=len(by_page.offered),
        ),
    )


def looks_for_recurring(factors: Sequence[DecisionFactor]) -> bool:
    """A recurring cost is looked for when the brief has a factor of kind recurring cost, or no
    researched factor at all, so nothing says the category has none."""
    researched = [
        factor
        for factor in factors
        if factor.source is not None and factor.source.kind is SourceKind.URL
    ]
    return not researched or any(f.kind is FactorKind.RECURRING_COST for f in researched)


async def _without_category(
    linked_product: ProductOption | None,
    answered: Sequence[AnsweredFactor],
    chat: ChatModel,
    search: WebSearch,
    fetch: PageFetch,
) -> TcoOutput:
    """With no category there is nothing to search for; the linked product stays, with its
    evidence searched by its name alone and no recurring cost looked for."""
    decided = entry(
        TrailKind.DECIDED,
        "Searched for no other options",
        reason="the request names no category to search",
    )
    if linked_product is None:
        return TcoOutput(trail=(decided,))
    subject = await with_page(Subject(linked_product, linked=True), fetch)
    evidenced = await _evidence_and_findings(subject, None, False, answered, chat, search)
    return TcoOutput(
        options=(evidenced.option,),
        trail=(decided, *evidenced.trail),
        warnings=(_warning(WarningCode.ONE_OPTION_ONLY, wording.one_option_only()),),
    )


async def _linked_evidence(
    linked_product: ProductOption | None,
    category: str,
    look_for_recurring: bool,
    answered: Sequence[AnsweredFactor],
    chat: ChatModel,
    search: WebSearch,
    fetch: PageFetch,
) -> tuple[Evidenced, ...]:
    if linked_product is None:
        return ()
    subject = await with_page(Subject(linked_product, linked=True), fetch)
    return (
        await _evidence_and_findings(subject, category, look_for_recurring, answered, chat, search),
    )


async def _evidence_and_findings(
    subject: Subject,
    category: str | None,
    look_for_recurring: bool,
    answered: Sequence[AnsweredFactor],
    chat: ChatModel,
    search: WebSearch,
) -> Evidenced:
    """The evidence and the findings at the same time; findings are merged in after both
    finish."""
    evidenced, found = await asyncio.gather(
        option_evidence(subject, category, look_for_recurring, chat, search, answered=answered),
        option_findings(subject, category, chat, search),
    )
    return with_findings(evidenced, found)


class Refilled(NamedTuple):
    """Each picked option after its evidence, a slot refilled in place of one an answer removed,
    and the trail of the refills."""

    evidenced: tuple[Evidenced, ...]
    trail: tuple[TrailEntry, ...]


async def _refilled(
    picked: Sequence[Picked],
    evidenced: Sequence[Evidenced],
    offered: Sequence[Offered],
    budget: Decimal | None,
    category: str,
    look_for_recurring: bool,
    answered: Sequence[AnsweredFactor],
    chat: ChatModel,
    search: WebSearch,
) -> Refilled:
    """The options with each slot an answer emptied refilled once from the buyable candidates
    left, with their own evidence and findings; a refill an answer removes too stays removed."""
    used = [each.offered for each in picked]
    replacements: list[tuple[int, Picked]] = []
    trail: list[TrailEntry] = []
    for position, (each, result) in enumerate(zip(picked, evidenced, strict=True)):
        if not result.removed:
            continue
        chosen = refill(each.slot, [o for o in offered if o not in used], budget)
        if chosen is None:
            trail.append(
                entry(
                    TrailKind.DECIDED,
                    f"Left {each.slot} empty",
                    reason=f'"{each.option.name}" did not meet an answer, and no buyable '
                    "candidate is left to take its place",
                )
            )
            continue
        used.append(chosen)
        number = len(picked) + len(replacements) + 1
        replacements.append((position, Picked(each.slot, chosen, _option(chosen, number))))
        trail.append(
            entry(
                TrailKind.DECIDED,
                f'Chose "{chosen.name}" as {each.slot} in place of "{each.option.name}"',
                reason="its option did not meet an answer; a slot is refilled once",
            )
        )
    found = await asyncio.gather(
        *(
            _evidence_and_findings(
                _subject(each.offered, each.option),
                category,
                look_for_recurring,
                answered,
                chat,
                search,
            )
            for _, each in replacements
        )
    )
    by_position = {
        position: result for (position, _), result in zip(replacements, found, strict=True)
    }
    in_order = tuple(by_position.get(position, result) for position, result in enumerate(evidenced))
    refill_trail = tuple(each for result in found for each in result.trail)
    return Refilled(in_order, (*trail, *refill_trail))


def _subject(offered: Offered, option: ProductOption) -> Subject:
    return Subject(option, own_page(offered.page))


def _option(offered: Offered, number: int) -> ProductOption:
    """The product option at the offer that stands on its product page, seen the day the page
    was read; the comparison site speaks for no one, and the source's label names the shop."""
    page = offered.page
    assert page.retrieved_at is not None, "a page that was read says when"
    return ProductOption(
        id=OPTION_ID.format(number=number),
        name=offered.name,
        brand=offered.brand,
        price=offered.price,
        price_source=Source(kind=SourceKind.URL, reference=page.url, label=offered.seller),
        price_seen_on=page.retrieved_at.date(),
        shipping=offered.shipping,
        out_of_stock=offered.out_of_stock,
        incomplete=offered.incomplete,
        link=page.url,
        piece_count=offered.piece_count,
    )


def _without_linked(
    candidates: Sequence[Candidate], linked_product: ProductOption | None, category: str
) -> tuple[tuple[Candidate, ...], tuple[TrailEntry, ...]]:
    """The candidates without the product at the link, which holds the first place."""
    if linked_product is None:
        return tuple(candidates), ()
    kept: list[Candidate] = []
    trail: list[TrailEntry] = []
    for each in candidates:
        brand = each.listed.brand or linked_product.brand
        if same_product(each.listed.name, linked_product.name, brand, category):
            trail.append(left_out(each.listed.name, "it is the product at your link"))
        else:
            kept.append(each)
    return tuple(kept), tuple(trail)


def _sized(candidates: Sequence[Candidate]) -> bool:
    """Whether at least half of the products listed name a size."""
    sized = sum(names_a_size(each.listed.name) for each in candidates)
    return bool(candidates) and 2 * sized >= len(candidates)


def _linked_entries(linked_product: ProductOption | None) -> tuple[TrailEntry, ...]:
    if linked_product is None:
        return ()
    reason = (
        "it is the product at your link; its page states no price in euro, so it has no price"
        if linked_product.price is None
        else "it is the product at your link"
    )
    return (
        entry(TrailKind.DECIDED, f'"{linked_product.name}" holds the first place', reason=reason),
    )


def _slot_entries(slots: Sequence[Slot]) -> tuple[TrailEntry, ...]:
    """One entry per slot, and one when no durability judgement decided a pick."""
    entries = tuple(_slot_entry(slot) for slot in slots)
    durable = [slot for slot in slots if slot.name != CHEAPEST and slot.taken is not None]
    if durable and all(slot.by_price for slot in durable):
        by_price = entry(
            TrailKind.DECIDED,
            wording.FILLED_BY_PRICE,
            reason=wording.FILLED_BY_PRICE_WHY,
        )
        return (*entries, by_price)
    return entries


def _slot_entry(slot: Slot) -> TrailEntry:
    if slot.taken is None:
        return entry(TrailKind.DECIDED, f"Left {slot.name} empty", reason=slot.reason)
    taken = slot.taken
    chose = f'Chose "{taken.name}" as {slot.name}'
    if taken.out_of_stock or taken.incomplete:
        mark = "out of stock" if taken.out_of_stock else "sold without a part it needs to work"
        return entry(
            TrailKind.DECIDED, chose, reason=f"it is {mark}, and no buyable candidate was left"
        )
    if slot.name == CHEAPEST or slot.by_price:
        cost = euros(with_shipping(taken.price, taken.shipping))
        return entry(TrailKind.DECIDED, chose, reason=f"{cost} with its stated shipping")
    pick = wording.DURABLE_PICK.format(judgement=judgement_words(taken.judgement))
    return entry(TrailKind.DECIDED, chose, reason=pick)


def _not_selected(
    offered: Sequence[Offered], slots: Sequence[Slot], budget: Decimal | None
) -> tuple[TrailEntry, ...]:
    taken = [slot.taken for slot in slots if slot.taken is not None]
    return tuple(
        left_out(each.name, why_not_selected(each, budget)) for each in offered if each not in taken
    )


def _warnings(
    category: str,
    options: Sequence[ProductOption],
    *,
    failed: bool,
    removed_by_answers: bool,
    read: int,
) -> tuple[Warning, ...]:
    """One option is a warning, none is another; its wording says why, in a fixed order. They
    are worked out after "Evidence", which can remove an option for an answer."""
    if len(options) == 1:
        return (_warning(WarningCode.ONE_OPTION_ONLY, wording.one_option_only()),)
    if options:
        return ()
    if failed:
        message = wording.no_options_found("searches_failed", category)
    elif removed_by_answers:
        message = wording.no_options_found("none_met_the_answers", category, read)
    else:
        message = wording.no_options_found("nothing_found", category)
    return (_warning(WarningCode.NO_OPTIONS_FOUND, message),)


def _warning(code: WarningCode, message: str) -> Warning:
    return Warning(code=code, message=message)
