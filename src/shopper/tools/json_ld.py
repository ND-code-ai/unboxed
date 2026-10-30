"""The product and its offer in a page's JSON-LD, and the products a listing page links to, read
in code: one reader for the pasted link, a candidate's product page and a listing page
(data_sources.md, "Firecrawl").

A model never supplies a price. A block that is not valid JSON is skipped, and a value that
should be text but is not counts as missing.
"""

import json
import re
from collections.abc import Iterator, Mapping
from decimal import Decimal
from typing import Any, NamedTuple

from shopper.calc.amounts import parse_amount
from shopper.calc.offers import NEW_CONDITION
from shopper.tools.results import OfferKind

_JSON_LD = re.compile(
    r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
PRODUCT_TYPES = frozenset({"Product", "ProductGroup"})
ITEM_LIST = "ItemList"
AGGREGATE_OFFER = "AggregateOffer"
# The schema.org availability values that mean the offer can be bought now
# (option_research.md, "The offer on a product page"); every other value means it cannot.
IN_STOCK = frozenset({"InStock", "LimitedAvailability", "OnlineOnly"})


class Offer(NamedTuple):
    """The offer read from a page; `currency` as the page states it, not yet checked, and so the
    currency of its shipping cost. `condition` is the schema.org value, such as "NewCondition"."""

    kind: OfferKind
    amount: Decimal | None = None
    currency: str | None = None
    availability: str | None = None
    seller: str | None = None
    condition: str | None = None
    shipping: Decimal | None = None
    shipping_currency: str | None = None


class ProductData(NamedTuple):
    """`offer` is the offer the page's product is read at; `offers` every offer it states, in the
    page's order, the used ones included."""

    name: str | None
    offer: Offer
    brand: str | None = None
    offers: tuple[Offer, ...] = ()


def product_data(raw_html: str) -> ProductData:
    """The name, offer and brand of the first `Product` or `ProductGroup` in the page's JSON-LD.

    The offer is the first that is new and has a price; in an `AggregateOffer` with nested
    offers, the cheapest new one in stock (else the cheapest new one, which says it is not in
    stock). A `ProductGroup` with no offer of its own offers its variants'. An `AggregateOffer`
    with no nested offers has only a lowest price, which is no offer.
    """
    product = next(_products(raw_html), None)
    if product is None:
        return ProductData(None, Offer(OfferKind.NONE))
    return ProductData(
        _text(product.get("name")),
        _offer(product),
        _name_of(product.get("brand")),
        _every_offer(product),
    )


class Listed(NamedTuple):
    """A product an `ItemList` links to; `url` as the page states it, maybe relative to it,
    `lowest` its lowest price, of the kind `lowest_price_only`, and the brand it names."""

    name: str
    url: str
    lowest: Offer
    brand: str | None = None


def listed_products(raw_html: str) -> tuple[Listed, ...]:
    """The products the page's `ItemList`s link to, in their order: each `Product` item with a
    name and a link, and the lowest price of its `AggregateOffer` (task 1.12)."""
    return tuple(
        listed
        for item_list in _item_lists(raw_html)
        for product in _list_items(item_list)
        if (listed := _listed(product)) is not None
    )


def in_stock(availability: str | None) -> bool:
    return availability in IN_STOCK


def _products(raw_html: str) -> Iterator[Mapping[str, Any]]:
    yield from (node for node in _page_nodes(raw_html) if _is_product(node))


def _item_lists(raw_html: str) -> Iterator[Mapping[str, Any]]:
    yield from (node for node in _page_nodes(raw_html) if ITEM_LIST in _types(node))


def _page_nodes(raw_html: str) -> Iterator[Mapping[str, Any]]:
    for block in _JSON_LD.findall(raw_html):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        yield from _nodes(parsed)


def _list_items(item_list: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """The products of an `ItemList`: each `ListItem`'s item, or the element itself."""
    for element in _as_list(item_list.get("itemListElement")):
        if not isinstance(element, dict):
            continue
        item = element.get("item", element)
        if isinstance(item, dict) and _is_product(item):
            yield item


def _listed(product: Mapping[str, Any]) -> Listed | None:
    name, url = _text(product.get("name")), _text(product.get("url"))
    if name is None or url is None:
        return None
    return Listed(name, url, _lowest(product.get("offers")), _name_of(product.get("brand")))


def _lowest(offers: Any) -> Offer:
    """The lowest price an `AggregateOffer` states: a listing page's price is no offer anyone can
    buy at."""
    if not _is_aggregate(offers):
        return Offer(OfferKind.NONE)
    return Offer(
        kind=OfferKind.LOWEST_PRICE_ONLY,
        amount=_amount(offers.get("lowPrice")),
        currency=_text(offers.get("priceCurrency")),
    )


def _nodes(parsed: Any) -> Iterator[Mapping[str, Any]]:
    """The nodes of a block: one object, a list of them, or an object with a `@graph`. The items
    of an `ItemList` are not nodes of the page: a listing page is no product's page."""
    if isinstance(parsed, list):
        for item in parsed:
            yield from _nodes(item)
    elif isinstance(parsed, dict):
        yield parsed
        yield from _nodes(parsed.get("@graph", []))


def _is_product(node: Mapping[str, Any]) -> bool:
    return bool(PRODUCT_TYPES & _types(node))


def _is_aggregate(offers: Any) -> bool:
    return isinstance(offers, dict) and AGGREGATE_OFFER in _types(offers)


def _types(node: Mapping[str, Any]) -> set[str]:
    """A node's types: its `@type` may be one or a list."""
    return {each for each in _as_list(node.get("@type")) if isinstance(each, str)}


def _as_list(value: Any) -> list[Any]:
    """A value that may be one item or a list of them, as a list; none is an empty list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _offers_of(product: Mapping[str, Any]) -> Any:
    """The product's own offers; a `ProductGroup` with none offers its variants'."""
    offers = product.get("offers")
    if offers is not None:
        return offers
    return [
        variant.get("offers")
        for variant in _as_list(product.get("hasVariant"))
        if isinstance(variant, dict)
    ]


def _every_offer(product: Mapping[str, Any]) -> tuple[Offer, ...]:
    """Every offer the product states, nested in an `AggregateOffer` or not, in page order."""
    offers = _offers_of(product)
    if _is_aggregate(offers):
        currency = _text(offers.get("priceCurrency"))
        return tuple(_read_offer(each, currency) for each in _offer_objects(offers.get("offers")))
    return tuple(_read_offer(each, None) for each in _offer_objects(offers))


def _offer(product: Mapping[str, Any]) -> Offer:
    offers = _offers_of(product)
    if _is_aggregate(offers):
        return _aggregate(offers)
    objects = list(_offer_objects(offers))
    if not objects:
        return Offer(OfferKind.NONE)
    new = [_read_offer(offer, None) for offer in objects if _is_new(offer)]
    priced = [offer for offer in new if offer.amount is not None]
    return (priced or new or [Offer(OfferKind.OFFER)])[0]


def _aggregate(aggregate: Mapping[str, Any]) -> Offer:
    currency = _text(aggregate.get("priceCurrency"))
    new = (each for each in _offer_objects(aggregate.get("offers")) if _is_new(each))
    nested = [
        offer for offer in (_read_offer(each, currency) for each in new) if offer.amount is not None
    ]
    if not nested:
        return Offer(OfferKind.LOWEST_PRICE_ONLY)
    available = [offer for offer in nested if in_stock(offer.availability)]
    return min(available or nested, key=lambda offer: offer.amount or Decimal(0))


def _offer_objects(offers: Any) -> Iterator[Mapping[str, Any]]:
    """Each offer object of one object or a list of them, in page order."""
    if isinstance(offers, list):
        for item in offers:
            yield from _offer_objects(item)
    elif isinstance(offers, dict):
        yield offers


def _is_new(offer: Mapping[str, Any]) -> bool:
    condition = _last_part(offer.get("itemCondition"))
    return condition is None or condition == NEW_CONDITION


def _read_offer(offer: Mapping[str, Any], currency: str | None) -> Offer:
    """One offer; its currency falls back on that of the aggregate it is nested in."""
    amount, specified_currency = _price(offer)
    shipping, shipping_currency = _shipping(offer)
    return Offer(
        kind=OfferKind.OFFER,
        amount=amount,
        currency=specified_currency or _text(offer.get("priceCurrency")) or currency,
        availability=_last_part(offer.get("availability")),
        seller=_seller(offer.get("seller")),
        condition=_last_part(offer.get("itemCondition")),
        shipping=shipping,
        shipping_currency=shipping_currency,
    )


def _shipping(offer: Mapping[str, Any]) -> tuple[Decimal | None, str | None]:
    """The shipping rate of the offer's first shipping details that state one, with its
    currency; missing when it states none."""
    for details in _as_list(offer.get("shippingDetails")):
        rate = details.get("shippingRate") if isinstance(details, dict) else None
        if isinstance(rate, dict) and "value" in rate:
            return _amount(rate["value"]), _text(rate.get("currency"))
    return None, None


def _price(offer: Mapping[str, Any]) -> tuple[Decimal | None, str | None]:
    """The offer's own price, else that of a price specification with no price type: a typed
    one, such as a strikethrough price, is not what the offer costs now."""
    if "price" in offer:
        return _amount(offer.get("price")), None
    for specification in _as_list(offer.get("priceSpecification")):
        if isinstance(specification, dict) and "priceType" not in specification:
            if "price" in specification:
                return _amount(specification["price"]), _text(specification.get("priceCurrency"))
    return None, None


def _amount(value: Any) -> Decimal | None:
    readable = isinstance(value, str | int | float) and not isinstance(value, bool)
    return parse_amount(str(value)) if readable else None


def _seller(value: Any) -> str | None:
    return _name_of(value)


def _name_of(value: Any) -> str | None:
    """A schema.org thing's name, such as a `Brand` or an `Organization`, or the text itself."""
    return _text(value.get("name")) if isinstance(value, dict) else _text(value)


def _last_part(value: Any) -> str | None:
    """A schema.org value without its prefix: "https://schema.org/InStock" is "InStock"."""
    text = _text(value)
    return None if text is None else re.split(r"[/:]", text)[-1] or None


def _text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None
