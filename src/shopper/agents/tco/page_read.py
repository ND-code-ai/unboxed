"""One candidate's product page: its offer read in code, what it sells read by the model.

Code reads the page's JSON-LD offers and chooses the one that stands (`calc/offers.py`). The
model reads the page with the price read measured in task 1.12 and trimmed in task 1.14 (every
euro amount, those for the page's own product first, with what its page sells against the
category); code uses only what the page sells and a set's piece
count, once they pass the checks in `checks.py`, never an amount as the price. Rules:
docs/architecture/option_research.md ("The offer on a product page", "What a product page
sells") and docs/findings/task_1.12.md ("Decided", items 7 to 12).
"""

import re
from collections.abc import Sequence

from shopper import wording
from shopper.agents.shared.research import numbered
from shopper.agents.tco.checks import page_sells
from shopper.agents.tco.models import Candidate, Offered, PageContext, PageRead, PageReading
from shopper.agents.tco.prompt import PAGE_INPUT, PAGE_PROMPT
from shopper.agents.tco.trail import by_model, entry, left_out
from shopper.calc.display import euros
from shopper.calc.offers import ChosenOffer, SeenOffer, chosen_offer
from shopper.config import (
    COMPARISON_SITES,
    MIN_OTHER_OFFERS,
    OPTION_RESEARCH_MAX_TOKENS,
    OPTION_RESEARCH_TIMEOUT_SECONDS,
    PAGE_TEXT_MAX_CHARACTERS,
    PRICE_OUTLIER_SHARE,
    SIZE_UNITS,
    ComparisonSite,
    Tier,
)
from shopper.llm import ChatModel, Completion, LlmFailure, complete_structured
from shopper.state import Source, SourceKind, TrailEntry, TrailKind
from shopper.tools.results import FailureKind, OfferKind, PageFetch, ProductPage, SearchResult
from shopper.tools.search import on_domain

PAGE_TIER: Tier = "medium"
# The read reasons little, as the price read it was measured as did (docs/findings/task_1.12.md).
PAGE_LOW_EFFORT = True
# A site no rule is recorded for: its price is the item's, and an offer must state it is new.
OTHER_SITE = ComparisonSite(not_listing=(), price_includes_shipping=False, new_only=False)
# A diameter sign before the number is no letter: "Ø24 cm" is a size (the GreenChef of task
# 1.15's live run).
_SIZE = re.compile(
    r"(?:\b|(?<=ø))\d+(?:[.,]\d+)?\s?(?:" + "|".join(SIZE_UNITS) + r")\b", re.IGNORECASE
)


def names_a_size(name: str) -> bool:
    """Whether a product name states a size, a capacity or a power ("24 cm", "1.7L", "18V")."""
    return _SIZE.search(name) is not None


async def read_page(
    candidate: Candidate, context: PageContext, chat: ChatModel, fetch: PageFetch
) -> PageRead:
    """The candidate as its product page offers it, or why it is left out."""
    listed = candidate.listed
    page = await fetch(listed.url)
    if page.failure is not None:
        return PageRead(None, (left_out(listed.name, _not_fetched(page)),), fetched=False)
    site = wording.site_name(page.url)
    if page.offer is OfferKind.NONE or page.name is None:
        return _dropped(listed.name, f"its page at {site} holds no product offer")
    if page.offer is OfferKind.LOWEST_PRICE_ONLY:
        return _dropped(listed.name, f"its page at {site} gives only a lowest price")
    rules = _rules(page.url)
    choice = chosen_offer(
        [
            SeenOffer(
                price=offer.price,
                shipping=offer.shipping,
                in_stock=offer.in_stock,
                condition=offer.condition,
            )
            for offer in page.offers
        ],
        price_includes_shipping=rules.price_includes_shipping,
        no_condition_is_new=rules.new_only,
        outlier_share=PRICE_OUTLIER_SHARE,
        min_others=MIN_OTHER_OFFERS,
    )
    outliers = tuple(_outlier(listed.name, page, index) for index in choice.outliers)
    if choice.chosen is None:
        return _dropped(listed.name, f"its page at {site} has no new offer in euro", outliers)
    as_result = SearchResult(
        url=page.url, title=page.name, content=page.markdown[:PAGE_TEXT_MAX_CHARACTERS]
    )
    reply = await _read(context, page, as_result, chat)
    if isinstance(reply, LlmFailure):
        failed = left_out(listed.name, f"its page at {site} could not be read ({reply.kind})")
        return PageRead(None, (*outliers, by_model(failed, reply)), fetched=True)
    sold = page_sells(
        reply.value, as_result, context.name_term, set_requested=context.set_requested
    )
    if sold.sells is None:
        excluded = by_model(left_out(listed.name, sold.reason or ""), reply)
        return PageRead(None, (*outliers, excluded), fetched=True)
    offered = _offered(candidate, page, choice.chosen, sold.sells == "incomplete", sold.piece_count)
    found = by_model(_found(offered), reply)
    return PageRead(offered, (*outliers, found, *_no_size(offered, context)), fetched=True)


async def _read(
    context: PageContext, page: ProductPage, as_result: SearchResult, chat: ChatModel
) -> Completion[PageReading] | LlmFailure:
    return await complete_structured(
        chat,
        PAGE_TIER,
        PAGE_INPUT.format(
            category=context.category,
            brand=page.brand or "",
            set_requested="yes" if context.set_requested else "no",
            results=numbered([as_result]),
        ),
        PageReading,
        system=PAGE_PROMPT,
        max_tokens=OPTION_RESEARCH_MAX_TOKENS,
        timeout=OPTION_RESEARCH_TIMEOUT_SECONDS,
        low_effort=PAGE_LOW_EFFORT,
    )


def _rules(url: str) -> ComparisonSite:
    return next(
        (site for domain, site in COMPARISON_SITES.items() if on_domain(url, (domain,))),
        OTHER_SITE,
    )


def _offered(
    candidate: Candidate,
    page: ProductPage,
    chosen: ChosenOffer,
    incomplete: bool,
    piece_count: int | None,
) -> Offered:
    """The candidate at the offer that stands; its name and brand are the page's, else the
    listing's, and a sub-brand is cut to the words that stand in the name."""
    name = page.name or candidate.listed.name
    assert page.retrieved_at is not None, "a page that was read says when"
    return Offered(
        candidate=candidate,
        name=name,
        brand=_brand(page.brand or candidate.listed.brand, name),
        page=page,
        price=chosen.item_price,
        shipping=chosen.shipping,
        seller=page.offers[chosen.index].seller,
        out_of_stock=chosen.in_stock is False,
        incomplete=incomplete,
        piece_count=piece_count,
        judgement=candidate.judgement,
    )


def _brand(brand: str | None, name: str) -> str | None:
    """The brand cut to its words that stand in the name ("Bosch Home and Garden" for a "Bosch
    EasyDrill" is "Bosch"); a brand none of whose words stand there is kept whole."""
    if brand is None:
        return None
    in_name = set(re.findall(r"\w+", name.casefold()))
    kept = [word for word in brand.split() if word.casefold() in in_name]
    return " ".join(kept) or brand


def _not_fetched(page: ProductPage) -> str:
    if page.failure is FailureKind.RATE_LIMITED:
        return "its page was skipped after Firecrawl's second rate limit (rate_limited)"
    return f"its page could not be read ({page.failure})"


def _dropped(name: str, reason: str, before: Sequence[TrailEntry] = ()) -> PageRead:
    return PageRead(None, (*before, left_out(name, reason)), fetched=True)


def _outlier(name: str, page: ProductPage, index: int) -> TrailEntry:
    offer = page.offers[index]
    seller = "" if offer.seller is None else f" of {offer.seller}"
    price = "" if offer.price is None else f" at {euros(offer.price)}"
    return entry(
        TrailKind.EXCLUDED,
        f'Left out the offer{seller}{price} on the page of "{name}"',
        reason=f"it costs under {PRICE_OUTLIER_SHARE:.0%} of the median of the page's offers",
        source=_page_source(page.url),
    )


def _found(offered: Offered) -> TrailEntry:
    shipping = (
        "shipping not stated"
        if offered.shipping is None
        else f"plus {euros(offered.shipping)} shipping"
    )
    seller = "" if offered.seller is None else f", sold by {offered.seller}"
    stock = "out of stock" if offered.out_of_stock else "in stock"
    marks = ", sold without a part it needs to work" if offered.incomplete else ""
    pieces = "" if offered.piece_count is None else f", {offered.piece_count} pieces"
    return entry(
        TrailKind.FOUND,
        f'Read "{offered.name}" at {wording.site_name(offered.page.url)}: '
        f"{euros(offered.price)} {shipping}{seller}, {stock}{marks}{pieces}",
        source=_page_source(offered.page.url),
    )


def _no_size(offered: Offered, context: PageContext) -> tuple[TrailEntry, ...]:
    """A note when the page names no size or variant while most listed products do."""
    if not context.sized or names_a_size(offered.name):
        return ()
    return (
        entry(
            TrailKind.DECIDED,
            f'The page of "{offered.name}" states no size or variant',
            reason="most products listed for the category name one",
        ),
    )


def _page_source(url: str) -> Source:
    return Source(kind=SourceKind.URL, reference=url)
