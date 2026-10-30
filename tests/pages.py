"""Listing pages and product pages for the tests, as Firecrawl returns them, built from JSON-LD
the test writes; and a page service that serves them."""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from shopper.tools.results import FailureKind, PageRequest, PageService, Service, StoredResponse

READ_AT = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
NEW = "https://schema.org/NewCondition"
IN_STOCK = "https://schema.org/InStock"
OUT_OF_STOCK = "https://schema.org/OutOfStock"


def stored_page(url: str, *blocks: Mapping[str, Any], markdown: str = "") -> StoredResponse:
    scripts = "".join(
        f'<script type="application/ld+json">{json.dumps(block)}</script>' for block in blocks
    )
    return StoredResponse(
        service=Service.FIRECRAWL,
        request={"url": url, "parameters": {"formats": ["markdown", "rawHtml"]}},
        retrieved_at=READ_AT,
        response={
            "success": True,
            "data": {
                "markdown": markdown,
                "rawHtml": f"<html><head>{scripts}</head><body></body></html>",
                "metadata": {"statusCode": 200, "creditsUsed": 1},
            },
        },
    )


def listed(name: str, url: str, lowest: str | None, brand: str | None = None) -> dict[str, Any]:
    """A product as a listing page's `ItemList` names it."""
    item: dict[str, Any] = {"@type": "Product", "name": name, "url": url}
    if lowest is not None:
        item["offers"] = {"@type": "AggregateOffer", "lowPrice": lowest, "priceCurrency": "EUR"}
    if brand is not None:
        item["brand"] = {"@type": "Brand", "name": brand}
    return item


def listing_page(url: str, *products: Mapping[str, Any]) -> StoredResponse:
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": number, "item": product}
            for number, product in enumerate(products, start=1)
        ],
    }
    return stored_page(url, item_list, markdown="# Listing")


def offer(
    price: str,
    shipping: str | None = "0",
    *,
    availability: str = IN_STOCK,
    condition: str | None = NEW,
    seller: str = "Shop.nl",
) -> dict[str, Any]:
    made: dict[str, Any] = {
        "@type": "Offer",
        "price": price,
        "priceCurrency": "EUR",
        "availability": availability,
        "seller": {"@type": "Organization", "name": seller},
    }
    if condition is not None:
        made["itemCondition"] = condition
    if shipping is not None:
        made["shippingDetails"] = {
            "@type": "OfferShippingDetails",
            "shippingRate": {"@type": "MonetaryAmount", "value": shipping, "currency": "EUR"},
        }
    return made


def product_page(
    url: str,
    name: str,
    brand: str | None,
    *offers: Mapping[str, Any],
    markdown: str | None = None,
) -> StoredResponse:
    """A product page whose product holds these offers in an `AggregateOffer`."""
    product: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "offers": {"@type": "AggregateOffer", "priceCurrency": "EUR", "offers": list(offers)},
    }
    if brand is not None:
        product["brand"] = {"@type": "Brand", "name": brand}
    return stored_page(url, product, markdown=f"# {name}" if markdown is None else markdown)


def lowest_price_page(url: str, name: str, lowest: str) -> StoredResponse:
    product = {
        "@type": "Product",
        "name": name,
        "offers": {"@type": "AggregateOffer", "lowPrice": lowest, "priceCurrency": "EUR"},
    }
    return stored_page(url, product, markdown=f"# {name}")


def serving(
    pages: Mapping[str, StoredResponse | FailureKind], seen: list[str] | None = None
) -> PageService:
    """A page service that serves these pages by URL, noting each URL asked for in `seen`; any
    other page fails the test."""

    async def fetch(request: PageRequest) -> StoredResponse | FailureKind:
        if seen is not None:
            seen.append(request.url)
        assert request.url in pages, f"no page expected at {request.url}"
        return pages[request.url]

    return fetch


def results(*urls: str) -> Sequence[Mapping[str, str]]:
    """Search results at these URLs, each with a title and a line of text."""
    return tuple({"url": url, "title": url, "content": "Kopen"} for url in urls)
