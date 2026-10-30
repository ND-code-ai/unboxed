"""The product at a pasted link: fetch the page, read it, and decide how the session goes on.

The supervisor's work after parsing. Code takes the name and euro price from the page's JSON-LD
(tools/product_page.py); the small model reads only the materials and weight from its text, and
never a price. The four outcomes are the table in docs/architecture/data_sources.md ("An
unreadable link"). This module knows nothing of the graph.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from shopper import wording
from shopper.agents.linked_product.prompt import PAGE_DETAILS_PROMPT
from shopper.agents.supervisor.agent import ParsedRequest, read_product_name
from shopper.calc.display import euros
from shopper.config import PAGE_TEXT_MAX_CHARACTERS, Tier
from shopper.llm import ChatModel, LlmFailure, complete_structured
from shopper.state import (
    SCOPES_THAT_DO_NOT_RUN,
    Agent,
    DomainModel,
    Material,
    ProductOption,
    Request,
    Scope,
    Source,
    SourceKind,
    StatedBy,
    TrailEntry,
    TrailKind,
    Warning,
    WarningCode,
)
from shopper.tools.results import PageFetch, ProductPage

LINKED_OPTION_ID = "option-link"
GRAMS_PER_KILOGRAM = Decimal(1000)
NO_PRODUCT_NAMED = "the page names no product"


class PageMaterial(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    form: str | None


class PageDetails(BaseModel):
    """The fields the model fills from the page text, and nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    materials: list[PageMaterial]
    weight_amount: float | None
    weight_unit: Literal["g", "kg"] | None


class LinkOutput(DomainModel):
    """The request as it now stands, the linked product when it was read, and what was noted."""

    request: Request
    product: ProductOption | None = None
    trail: tuple[TrailEntry, ...] = ()
    warnings: tuple[Warning, ...] = ()


async def read_link(
    request: Request, chat: ChatModel, fetch: PageFetch, tier: Tier = "small"
) -> LinkOutput:
    """Fetch the request's link and turn the page into the linked product option.

    With no category, the product name gives it, and the scope with it. A link that gives no
    product name is unreadable: with a category the session goes on with a warning, without
    one the request becomes unclear and the session ends. Raises ModelCallError when the call
    for the product name fails, as the supervisor's parsing does.
    """
    url = request.product_url
    if url is None:
        raise ValueError("a request with no product link has nothing to read")
    page = await fetch(url)
    if page.name is None:
        return _unreadable(request, page)
    found = _entry(TrailKind.FOUND, _read_summary(page, page.name), source=_page_source(url))
    trail: tuple[TrailEntry, ...] = (found,)
    if request.category is None:
        request, named_trail = _placed(await read_product_name(request, page.name, chat, tier))
        trail = (*trail, *named_trail)
        if request.scope in SCOPES_THAT_DO_NOT_RUN:
            return LinkOutput(request=request, trail=trail)
    product, details_trail = await _product(page, page.name, chat, tier)
    currency_warnings, currency_trail = _other_currency(page)
    return LinkOutput(
        request=request,
        product=product,
        trail=(*trail, *details_trail, *currency_trail),
        warnings=currency_warnings,
    )


def _placed(named: ParsedRequest) -> tuple[Request, tuple[TrailEntry, ...]]:
    """The request the product name gave; one the model found unclear runs as general.

    The page named a product, so the session goes on without a category rather than ending with
    words that say the link could not be read.
    """
    if named.request.scope is not Scope.UNCLEAR:
        return named.request, named.trail
    changed = _entry(
        TrailKind.DECIDED,
        "Changed the scope from unclear to general",
        reason="the page names a product the model could not place",
    )
    return named.request.model_copy(update={"scope": Scope.GENERAL}), (*named.trail, changed)


def _unreadable(request: Request, page: ProductPage) -> LinkOutput:
    reason = NO_PRODUCT_NAMED if page.failure is None else str(page.failure)
    excluded = _entry(
        TrailKind.EXCLUDED,
        "Could not read the product at the link",
        reason=reason,
        source=_page_source(page.url),
    )
    if request.category is not None:
        warning = Warning(
            code=WarningCode.LINK_UNREADABLE, message=wording.link_unreadable(request.category)
        )
        return LinkOutput(request=request, trail=(excluded,), warnings=(warning,))
    unclear = request.model_copy(update={"scope": Scope.UNCLEAR})
    changed = _entry(
        TrailKind.DECIDED,
        f"Changed the scope from {request.scope} to unclear",
        reason="the link could not be read and the request names no product",
    )
    return LinkOutput(request=unclear, trail=(excluded, changed))


async def _product(
    page: ProductPage, name: str, chat: ChatModel, tier: Tier
) -> tuple[ProductOption, tuple[TrailEntry, ...]]:
    """The linked product option, with what the model read from the page text when it could; it
    is marked out of stock when its page's offer says so."""
    product = ProductOption(
        id=LINKED_OPTION_ID,
        name=name,
        brand=page.brand,
        link=page.url,
        out_of_stock=page.in_stock is False,
        **_price_seen(page),
    )
    if not page.markdown.strip():
        return product, ()
    result = await complete_structured(
        chat,
        tier,
        page.markdown[:PAGE_TEXT_MAX_CHARACTERS],
        PageDetails,
        system=PAGE_DETAILS_PROMPT,
    )
    if isinstance(result, LlmFailure):
        excluded = _entry(
            TrailKind.EXCLUDED,
            "Materials and weight not read from the page",
            reason=f"the model call failed ({result.kind})",
        )
        return product, (_by_model(excluded, result.tier, result.model),)
    materials = _materials(result.value, page.url)
    weight = _weight_kg(result.value)
    read = _entry(
        TrailKind.FOUND, _details_summary(materials, weight), source=_page_source(page.url)
    )
    weight_source = None if weight is None else _page_source(page.url)
    read_with = product.model_copy(
        update={"materials": materials, "weight_kg": weight, "weight_source": weight_source}
    )
    return read_with, (_by_model(read, result.tier, result.model),)


def _price_seen(page: ProductPage) -> dict[str, object]:
    """The page's euro price with the page as its source, the shop speaking, and the day it was
    fetched; nothing when the page states no euro price."""
    if page.price is None or page.retrieved_at is None:
        return {}
    source = _page_source(page.url).model_copy(update={"stated_by": StatedBy.SELLER})
    return {
        "price": page.price,
        "price_source": source,
        "price_seen_on": page.retrieved_at.date(),
    }


def _materials(details: PageDetails, url: str) -> tuple[Material, ...]:
    named = ((material.name.strip().lower(), material.form) for material in details.materials)
    return tuple(
        Material(name=name, form=form or None, source=_page_source(url))
        for name, form in named
        if name
    )


def _weight_kg(details: PageDetails) -> Decimal | None:
    """The stated weight in kilograms; missing when none or not above zero was stated."""
    if details.weight_amount is None or details.weight_unit is None or details.weight_amount <= 0:
        return None
    amount = Decimal(str(details.weight_amount))
    return amount / GRAMS_PER_KILOGRAM if details.weight_unit == "g" else amount


def _other_currency(page: ProductPage) -> tuple[tuple[Warning, ...], tuple[TrailEntry, ...]]:
    """The warning and trail entry for a price the page states in a currency other than euro."""
    if page.other_currency is None:
        return (), ()
    message = wording.link_price_other_currency(page.other_currency)
    warning = Warning(
        code=WarningCode.LINK_PRICE_OTHER_CURRENCY, message=message, option_id=LINKED_OPTION_ID
    )
    excluded = _entry(
        TrailKind.EXCLUDED,
        "Left out the price at the link",
        reason=f"it is stated in {page.other_currency}, and the app works in euro only",
    )
    return (warning,), (excluded,)


def _read_summary(page: ProductPage, name: str) -> str:
    where = " from the cache" if page.from_cache else ""
    price = "price not stated in euro" if page.price is None else euros(page.price)
    return f'Read the product at the link{where}: "{name}", {price}'


def _details_summary(materials: tuple[Material, ...], weight: Decimal | None) -> str:
    named = ", ".join(material.name for material in materials) or "none stated"
    stated_weight = "not stated" if weight is None else f"{weight} kg"
    return f"Read from the page: materials {named}; weight {stated_weight}"


def _by_model(entry: TrailEntry, tier: Tier, model: str) -> TrailEntry:
    return entry.model_copy(update={"model_tier": tier, "model": model})


def _page_source(url: str) -> Source:
    return Source(kind=SourceKind.URL, reference=url)


def _entry(
    kind: TrailKind, summary: str, *, reason: str | None = None, source: Source | None = None
) -> TrailEntry:
    return TrailEntry(
        agent=Agent.SUPERVISOR, kind=kind, summary=summary, reason=reason, source=source
    )
