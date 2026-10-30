"""Step 3 of option research: the candidates' product pages, read in order until enough are
buyable or the pages run out.

Up to one product over the budget that is judged long by its name comes first, then the products
within the budget in listing order. At most three pages are read at once; their results are taken
in listing order, not as they finish, so a run reads the same pages each time. Rules:
docs/architecture/option_research.md ("Product pages") and docs/findings/task_1.12.md
("Decided", items 5 and 6).
"""

import asyncio
from collections.abc import Sequence
from decimal import Decimal

from shopper.agents.tco.models import Candidate, Offered, PageContext, PageRead, Reads
from shopper.agents.tco.page_read import read_page
from shopper.agents.tco.trail import counted, entry
from shopper.calc.display import euros
from shopper.config import ENOUGH_BUYABLE, MAX_READS_AT_ONCE, MAX_TIMES_THE_BUDGET, TCO_FETCH_LIMIT
from shopper.llm import ChatModel
from shopper.state import TrailEntry, TrailKind
from shopper.tools.results import PageFetch


def read_order(
    candidates: Sequence[Candidate], budget: Decimal | None
) -> tuple[tuple[Candidate, ...], tuple[TrailEntry, ...]]:
    """The candidates to read, in the order they are read, and the entry that says which.

    With no budget every candidate counts as within it, in listing order. With one, a candidate
    over it is read only when judged long by its name and listed at most three times the budget,
    and only the first such one; a candidate the listing gives no price for is not read.
    """
    if budget is None:
        return tuple(candidates), ()
    over = next(
        (
            each
            for each in candidates
            if each.judgement.value == "long"
            and each.listed.lowest_price is not None
            and budget < each.listed.lowest_price <= MAX_TIMES_THE_BUDGET * budget
        ),
        None,
    )
    within = tuple(
        each
        for each in candidates
        if each.listed.lowest_price is not None and each.listed.lowest_price <= budget
    )
    order = within if over is None else (over, *within)
    over_words = "" if over is None else f', and "{over.listed.name}" over it, judged long'
    decided = entry(
        TrailKind.DECIDED,
        f"To read: {counted(len(within), 'listed product')} within {euros(budget)}{over_words}",
        reason=f"{counted(len(candidates), 'product')} listed; the rest are over the budget",
    )
    return order, (decided,)


def is_buyable(offered: Offered | None) -> bool:
    """In stock and sold with every part it needs (GLOSSARY.md, "Buyable candidate")."""
    return offered is not None and not offered.out_of_stock and not offered.incomplete


async def read_product_pages(
    order: Sequence[Candidate],
    context: PageContext,
    chat: ChatModel,
    fetch: PageFetch,
    *,
    pages_read: int,
) -> Reads:
    """The candidates the product pages offer, in listing order.

    The reads stop once the buyable candidates reach five, or the pages read, the listing pages
    among them and cached ones too, reach twelve. No read starts once the reads in flight and
    the buyable candidates together reach five.
    """
    pending = list(order)
    left = TCO_FETCH_LIMIT - pages_read
    in_flight: list[asyncio.Task[PageRead]] = []
    reads: list[PageRead] = []
    buyable = 0
    while True:
        while (
            pending
            and left > 0
            and len(in_flight) < MAX_READS_AT_ONCE
            and buyable + len(in_flight) < ENOUGH_BUYABLE
        ):
            candidate = pending.pop(0)
            in_flight.append(asyncio.create_task(read_page(candidate, context, chat, fetch)))
            left -= 1
        if not in_flight:
            break
        read = await in_flight.pop(0)
        reads.append(read)
        buyable += is_buyable(read.offered)
    fetched = sum(read.fetched for read in reads)
    return Reads(
        offered=tuple(read.offered for read in reads if read.offered is not None),
        trail=(
            *(each for read in reads for each in read.trail),
            *_stopped(buyable, len(pending)),
        ),
        fetched=fetched,
        failed=bool(reads) and fetched == 0,
    )


def _stopped(buyable: int, unread: int) -> tuple[TrailEntry, ...]:
    """Why products listed for reading were left unread, when any were: the reads stop only at
    enough buyable candidates or at the last page."""
    if not unread:
        return ()
    reason = (
        f"{counted(buyable, 'buyable candidate')} found"
        if buyable >= ENOUGH_BUYABLE
        else f"{TCO_FETCH_LIMIT} pages were read, the listing pages among them"
    )
    return (
        entry(TrailKind.DECIDED, f"Left {counted(unread, 'listed product')} unread", reason=reason),
    )
