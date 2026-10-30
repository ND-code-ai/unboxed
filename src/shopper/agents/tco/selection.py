"""Which candidates read become product options: pure code, the same on every run.

Rules: docs/architecture/option_research.md ("Selection") and docs/findings/task_1.12.md
("Decided", item 13). At most three options in all, filled slot by slot, each slot choosing only
from candidates no earlier slot took. A buyable candidate comes first in every slot; one sold
incomplete only when none is left, and one out of stock last. The slot names are internal: they
appear in trail entries, never as a label on the report.
"""

from collections.abc import Sequence
from decimal import Decimal

from shopper.agents.tco.models import JUDGEMENT_ORDER, Offered, Slot
from shopper.calc.budget import with_shipping, within_budget
from shopper.calc.display import euros

CHEAPEST = "the cheapest"
DURABLE = "the durable pick"
DURABLE_WITHIN = "the durable pick within budget"
LONG = "long"


def select(offered: Sequence[Offered], budget: Decimal | None, *, linked: bool) -> tuple[Slot, ...]:
    """The slots in order: the cheapest (unless the linked product holds the first place), the
    durable pick, over the budget only when judged long, and the durable pick within budget. The
    durable picks go by the judgement by page, `long` first; ties go to the lower price, counted
    with its shipping, then the earlier in the listing."""
    slots: list[Slot] = []
    taken: list[Offered] = []
    for name in (DURABLE, DURABLE_WITHIN) if linked else (CHEAPEST, DURABLE, DURABLE_WITHIN):
        slot = _filled(name, [each for each in offered if each not in taken], budget)
        slots.append(slot)
        if slot.taken is not None:
            taken.append(slot.taken)
    return tuple(slots)


def refill(name: str, left: Sequence[Offered], budget: Decimal | None) -> Offered | None:
    """The buyable candidate left that the slot's own rule ranks first, for a slot whose option
    an answer removed; missing when none is left."""
    return _filled(name, [each for each in left if _standing(each) == 0], budget).taken


def _filled(name: str, left: Sequence[Offered], budget: Decimal | None) -> Slot:
    """The slot taken by the candidate its rule ranks first among these, or left empty."""
    pool = [each for each in left if _eligible(name, each, budget)]
    if not pool:
        return Slot(name, None, _empty(name, budget))
    if name == CHEAPEST:
        return Slot(name, min(pool, key=_price_key))
    chosen = min(pool, key=_judged_key)
    return Slot(name, chosen, by_price=not _judged_above_another(chosen, pool))


def _judged_above_another(chosen: Offered, pool: Sequence[Offered]) -> bool:
    """Whether the judgement ranks the pick above another candidate of its standing; when it
    ranks none lower, the price alone chose it."""
    rank = JUDGEMENT_ORDER.index(chosen.judgement.value)
    return any(
        _standing(each) == _standing(chosen) and JUDGEMENT_ORDER.index(each.judgement.value) > rank
        for each in pool
    )


def _eligible(name: str, each: Offered, budget: Decimal | None) -> bool:
    """Whether the slot may take the candidate: the durable pick over the budget only when
    judged long, the durable pick within budget never over it."""
    if name == CHEAPEST:
        return True
    if name == DURABLE:
        return is_within(each, budget) or each.judgement.value == LONG
    return is_within(each, budget)


def _empty(name: str, budget: Decimal | None) -> str:
    """Why the slot's own rule found no candidate."""
    if name == CHEAPEST:
        return "no candidate was read"
    if budget is None:
        return "no candidate is left"
    besides = " or judged long" if name == DURABLE else ""
    return f"no candidate is left within {euros(budget)}{besides}"


def is_within(each: Offered, budget: Decimal | None) -> bool:
    """Within the budget, the price counted with its stated shipping; with no budget, always."""
    return within_budget(each.price, budget, each.shipping) is not False


def why_not_selected(each: Offered, budget: Decimal | None) -> str:
    """Why a candidate read took no slot, by the step that decided it (task 1.10)."""
    if budget is not None and not is_within(each, budget) and each.judgement.value != LONG:
        return f"it is over {euros(budget)} and not judged long by the model"
    if each.out_of_stock:
        return "no shop has it in stock, and buyable candidates filled the slots"
    if each.incomplete:
        return "it is sold without a part it needs to work, and buyable candidates filled the slots"
    return "each slot went to a cheaper candidate or to one the model judged to last longer"


def _standing(each: Offered) -> int:
    """Buyable first, then sold incomplete, then out of stock."""
    if each.out_of_stock:
        return 2
    return 1 if each.incomplete else 0


def _cost(each: Offered) -> Decimal:
    return with_shipping(each.price, each.shipping)


def _price_key(each: Offered) -> tuple[int, Decimal, int]:
    return _standing(each), _cost(each), each.candidate.number


def _judged_key(each: Offered) -> tuple[int, int, Decimal, int]:
    return (
        _standing(each),
        JUDGEMENT_ORDER.index(each.judgement.value),
        _cost(each),
        each.candidate.number,
    )
