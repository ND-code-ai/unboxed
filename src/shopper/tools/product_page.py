"""The page fetch: the cache first, then its call limit, then Firecrawl. It reads a URL the user
pasted, a comparison site's listing page and a candidate's product page.

The name and offer come from the page's JSON-LD, read in code (`tools/json_ld.py`); the model
never supplies a price (data_sources.md, "Firecrawl").
"""

from decimal import Decimal
from urllib.parse import urljoin

from shopper.config import FIRECRAWL_PARAMETERS, PAGE_CACHE_MAX_AGE
from shopper.tools.cache import read_cached, write_cached
from shopper.tools.json_ld import Listed, Offer, in_stock, listed_products, product_data
from shopper.tools.results import (
    FailureKind,
    ListedProduct,
    PageFetch,
    PageOffer,
    PageRequest,
    ProductPage,
    Service,
    StoredResponse,
)
from shopper.tools.sources import Sources

EURO_CODE = "EUR"


def page_request(url: str) -> PageRequest:
    return PageRequest(url=url.strip(), parameters=FIRECRAWL_PARAMETERS)


def page_view(sources: Sources, max_calls: int) -> PageFetch:
    """A page fetch that makes at most `max_calls` calls to the service."""
    calls_made = 0

    async def fetch(url: str) -> ProductPage:
        nonlocal calls_made
        request = page_request(url)
        cached = read_cached(
            sources.cache_folder,
            Service.FIRECRAWL,
            request.url,
            PAGE_CACHE_MAX_AGE,
            sources.clock(),
        )
        if cached is not None:
            return product_page(request, cached, from_cache=True)
        if calls_made >= max_calls:
            return ProductPage(url=request.url, failure=FailureKind.LIMIT_REACHED)
        calls_made += 1
        fetched = await sources.fetch_page(request)
        if isinstance(fetched, FailureKind):
            return ProductPage(url=request.url, failure=fetched)
        # Stamped with the clock, as a search is, so a later cache hit says the same time.
        stamped = fetched.model_copy(update={"retrieved_at": sources.clock()})
        page = product_page(request, stamped, from_cache=False)
        if page.failure is None:
            write_cached(sources.cache_folder, request.url, stamped)
        return page

    return fetch


def product_page(request: PageRequest, stored: StoredResponse, *, from_cache: bool) -> ProductPage:
    """The page's product data, or the failure its own status stands for.

    Firecrawl answers 200 for a page that itself answered 403 or 404; the status is inside.
    """
    data = stored.response.get("data", {})
    metadata = data.get("metadata", {})
    credits = 0 if from_cache else int(metadata.get("creditsUsed", 1))
    failure = _page_failure(metadata.get("statusCode", 200))
    if failure is not None:
        return ProductPage(url=request.url, credits=credits, failure=failure)
    raw_html = data.get("rawHtml", "")
    product = product_data(raw_html)
    offer = product.offer
    price, other_currency = _euro_price(offer)
    return ProductPage(
        url=request.url,
        name=product.name,
        brand=product.brand,
        offer=offer.kind,
        price=price,
        other_currency=other_currency,
        in_stock=_stock(offer),
        seller=offer.seller,
        offers=tuple(_page_offer(each) for each in product.offers),
        listed=tuple(_listed(request.url, each) for each in listed_products(raw_html)),
        markdown=data.get("markdown", ""),
        retrieved_at=stored.retrieved_at,
        from_cache=from_cache,
        credits=credits,
    )


def _listed(page_url: str, listed: Listed) -> ListedProduct:
    """A listed product with its link made whole: a listing page may link with a path of its own
    site."""
    lowest_price, _ = _euro_price(listed.lowest)
    return ListedProduct(
        name=listed.name,
        url=urljoin(page_url, listed.url),
        brand=listed.brand,
        lowest_price=lowest_price,
    )


def _page_offer(offer: Offer) -> PageOffer:
    """An offer with its price and shipping in euro; an amount in another currency is missing."""
    price, _ = _euro_price(offer)
    shipping = _euro(offer.shipping, offer.shipping_currency or offer.currency)
    return PageOffer(
        price=price,
        shipping=shipping,
        in_stock=_stock(offer),
        condition=offer.condition,
        seller=offer.seller,
    )


def _stock(offer: Offer) -> bool | None:
    return None if offer.availability is None else in_stock(offer.availability)


def _page_failure(status: int) -> FailureKind | None:
    if status == 403:
        return FailureKind.BLOCKED
    if status == 404:
        return FailureKind.NOT_FOUND
    if status >= 400:
        return FailureKind.UNAVAILABLE
    return None


def _euro_price(offer: Offer) -> tuple[Decimal | None, str | None]:
    """The offer's price when it is in euro, and any other currency it states; that one is never
    read as euros, and a price with no currency stays unknown."""
    if offer.amount is None or offer.currency is None:
        return None, None
    if offer.currency.upper() != EURO_CODE:
        return None, offer.currency
    return offer.amount, None


def _euro(amount: Decimal | None, currency: str | None) -> Decimal | None:
    """The amount when it is stated in euro; missing otherwise."""
    if amount is None or currency is None or currency.upper() != EURO_CODE:
        return None
    return amount
