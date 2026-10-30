"""The page fetch for a pasted link, against recorded responses in tests/fixtures/."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from fakes import Clock, counted, failing_search_service
from shopper.tools.fixtures import fixture_page_service
from shopper.tools.product_page import page_view
from shopper.tools.results import (
    FailureKind,
    ListedProduct,
    OfferKind,
    PageOffer,
    PageRequest,
    PageService,
    ProductPage,
    Service,
    StoredResponse,
)
from shopper.tools.sources import Sources

FIXTURES = Path(__file__).parent.parent / "fixtures"
PAN = "https://example.org/shop/de-buyer-mineral-b-28"
BLOCKED = "https://example.org/shop/blocked"
GONE = "https://example.org/shop/gone"
BROKEN = "https://example.org/shop/broken"
NOON = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def sources_with(tmp_path: Path, service: PageService, clock: Clock | None = None) -> Sources:
    return Sources(
        search=failing_search_service(FailureKind.UNAVAILABLE),
        fetch_page=service,
        cache_folder=tmp_path / "cache",
        clock=clock or Clock(NOON),
    )


def fetched(sources: Sources, max_calls: int, *urls: str) -> list[ProductPage]:
    view = page_view(sources, max_calls)

    async def run() -> list[ProductPage]:
        return [await view(url) for url in urls]

    return asyncio.run(run())


def test_a_fetched_product_page_gives_its_name_and_euro_price(tmp_path: Path) -> None:
    (page,) = fetched(sources_with(tmp_path, fixture_page_service(FIXTURES)), 1, PAN)

    assert page.name == "De Buyer Mineral B koekenpan 28 cm"
    assert page.price == Decimal("54.95")
    assert page.other_currency is None
    assert page.markdown.startswith("# De Buyer Mineral B")
    assert page.credits == 1
    assert page.failure is None


def test_a_fetched_product_page_gives_the_brand_its_product_data_names(tmp_path: Path) -> None:
    (page,) = fetched(sources_with(tmp_path, fixture_page_service(FIXTURES)), 1, PAN)

    assert page.brand == "De Buyer"


def test_a_second_fetch_of_the_same_link_makes_no_network_call(tmp_path: Path) -> None:
    service, calls = counted(fixture_page_service(FIXTURES))
    sources = sources_with(tmp_path, service)

    first, again = fetched(sources, 1, PAN, PAN)

    assert len(calls) == 1
    assert again.from_cache is True
    assert again.credits == 0
    assert (again.name, again.price) == (first.name, first.price)


def test_a_page_says_when_it_was_fetched_also_from_the_cache(tmp_path: Path) -> None:
    clock = Clock(NOON)
    sources = sources_with(tmp_path, fixture_page_service(FIXTURES), clock)

    (first,) = fetched(sources, 1, PAN)
    clock.now = NOON + timedelta(hours=5)
    (later,) = fetched(sources, 1, PAN)

    assert first.retrieved_at == NOON
    assert later.from_cache is True
    assert later.retrieved_at == NOON


def test_a_fetched_page_is_fetched_again_after_a_day(tmp_path: Path) -> None:
    service, calls = counted(fixture_page_service(FIXTURES))
    clock = Clock(NOON)
    sources = sources_with(tmp_path, service, clock)

    fetched(sources, 1, PAN)
    clock.now = NOON + timedelta(days=1, minutes=1)
    (later,) = fetched(sources, 1, PAN)

    assert later.from_cache is False
    assert len(calls) == 2


def test_a_blocked_page_gives_a_typed_failure_and_is_not_cached(tmp_path: Path) -> None:
    service, calls = counted(fixture_page_service(FIXTURES))
    sources = sources_with(tmp_path, service)

    first, again = fetched(sources, 2, BLOCKED, BLOCKED)

    assert first.failure is FailureKind.BLOCKED
    assert first.name is None
    assert again.from_cache is False
    assert len(calls) == 2


def test_a_page_that_answered_404_inside_a_200_is_not_found(tmp_path: Path) -> None:
    (page,) = fetched(sources_with(tmp_path, fixture_page_service(FIXTURES)), 1, GONE)

    assert page.failure is FailureKind.NOT_FOUND


def test_a_page_that_answered_another_error_inside_a_200_is_unavailable(tmp_path: Path) -> None:
    (page,) = fetched(sources_with(tmp_path, fixture_page_service(FIXTURES)), 1, BROKEN)

    assert page.failure is FailureKind.UNAVAILABLE


# --- The recorded price pages of task 1.8.5 ---

TRAMONTINA_BESLIST = (
    "https://www.beslist.nl/p/tramontina-professional-koekenpan-zwart-20-cm/165/7891112203860"
)
HARIO_KIESKEURIG = (
    "https://www.kieskeurig.nl/waterkoker/product/61373492-hario-buono-kettle-1l-gooseneck-kettle-"
    "for-coffee-and-tea-zwanenhals-opschenkketel-voor-koffie-en-thee"
)
GREENPAN_LISTING = (
    "https://www.beslist.nl/products/huis_tuin/huis_tuin_505129_505236/c/"
    "diameter_pan~7948043~~merk~1341799~~optie_pan~6425208"
)
PANS_LISTING = "https://www.beslist.nl/products/huis_tuin/huis_tuin_505129_505236"


def recorded(tmp_path: Path, url: str) -> ProductPage:
    (page,) = fetched(sources_with(tmp_path, fixture_page_service(FIXTURES)), 1, url)
    return page


def test_a_comparison_site_offers_its_cheapest_new_offer_in_stock_with_the_seller(
    tmp_path: Path,
) -> None:
    page = recorded(tmp_path, TRAMONTINA_BESLIST)

    assert page.name == "Tramontina - Professional - Koekenpan - Zwart - 20 cm"
    assert (page.offer, page.price, page.in_stock, page.seller) == (
        OfferKind.OFFER,
        Decimal("39.95"),
        True,
        "Kookexpert.nl",
    )


def test_an_offer_out_of_stock_says_so(tmp_path: Path) -> None:
    page = recorded(
        tmp_path, "https://www.fonq.nl/greenpan-stanley-tucci-pannenset-black-20-26-cm-2-delig"
    )

    assert (page.price, page.in_stock) == (Decimal("158.95"), False)


def test_a_product_group_offers_its_first_variant_with_a_price(tmp_path: Path) -> None:
    page = recorded(
        tmp_path, "https://vanpommeren.nl/products/hario-v60-drip-kettle-buono-opschenkkan-1-2-l"
    )

    assert page.name == "Hario V60 Drip Kettle Buono - Opschenkkan 1.2 L"
    assert (page.price, page.in_stock) == (Decimal("55.00"), True)


def test_a_price_may_stand_in_the_offers_price_specification(tmp_path: Path) -> None:
    page = recorded(
        tmp_path,
        "https://www.coffeefriend.nl/p/fellow-corvo-ekg-elektrische-waterkoker-0-9-l-matzwart",
    )

    assert (page.price, page.seller) == (Decimal("200.00"), "Coffee Friend")


def test_a_strikethrough_price_is_not_the_offers_price(tmp_path: Path) -> None:
    # kieskeurig.nl's cheapest offer is €44.26, struck through from €52.
    page = recorded(tmp_path, HARIO_KIESKEURIG)

    assert (page.price, page.seller) == (Decimal("44.26"), "bol.")


def test_a_listing_page_offers_no_product(tmp_path: Path) -> None:
    # beslist.nl's listing has an `ItemList` of products, none of them the page's own.
    page = recorded(tmp_path, GREENPAN_LISTING)

    assert (page.name, page.offer, page.failure) == (None, OfferKind.NONE, None)


def test_a_listing_page_lists_its_products_with_their_links_and_lowest_prices(
    tmp_path: Path,
) -> None:
    # beslist.nl links each product with a path on its own site (task 1.12).
    page = recorded(tmp_path, PANS_LISTING)

    assert len(page.listed) == 10
    assert page.listed[0] == ListedProduct(
        name="Demeyere Alu Pro 5 Ceraforce Hoge Bakpan",
        url="https://www.beslist.nl/p/demeyere-alu-pro-5-ceraforce-hoge-bakpan/165/5412191124246/?aff_id=908",
        lowest_price=Decimal("88.95"),
    )


# --- The recorded pages of task 1.12 ---

GREENCHEF_KIESKEURIG = (
    "https://www.kieskeurig.nl/pan/product/12123108-greenchef-diamond-inductie-koekenpan"
)
MIDEA_BESLIST = (
    "https://www.beslist.nl/p/midea-roestvrijstalen-waterkoker-wit-1-5-liter-2200-w-met-"
    "temperatuurinstelling-en-veiligheidsfuncties/12000/6936718325347/?aff_id=908"
)
KETTLES_KIESKEURIG = "https://www.kieskeurig.nl/waterkoker"


def test_a_comparison_sites_page_gives_every_offer_with_its_shipping_and_condition(
    tmp_path: Path,
) -> None:
    page = recorded(tmp_path, GREENCHEF_KIESKEURIG)

    assert page.offers == (
        PageOffer(
            price=Decimal("26.98"),
            shipping=Decimal("2.99"),
            in_stock=True,
            condition="NewCondition",
            seller="bol.",
        ),
        PageOffer(
            price=Decimal("26.98"),
            shipping=Decimal("2.99"),
            in_stock=True,
            condition="NewCondition",
            seller="Amazon",
        ),
        PageOffer(
            price=Decimal("52.94"),
            shipping=Decimal("6.95"),
            in_stock=True,
            condition="NewCondition",
            seller="Fietsweb.nl",
        ),
        PageOffer(
            price=Decimal("77.9"),
            shipping=Decimal("0"),
            in_stock=True,
            condition="NewCondition",
            seller="Kaufland",
        ),
    )


def test_an_offer_that_states_no_condition_has_none(tmp_path: Path) -> None:
    # beslist.nl states no `itemCondition` on its offers (docs/findings/task_1.12.md).
    page = recorded(tmp_path, MIDEA_BESLIST)

    assert {offer.condition for offer in page.offers} == {None}
    assert page.offers[2] == PageOffer(
        price=Decimal("27.99"), shipping=Decimal("3.99"), in_stock=True, seller="Joybuy.nl"
    )


def test_a_listed_product_carries_the_brand_its_listing_names(tmp_path: Path) -> None:
    # kieskeurig.nl names each listed product's brand; beslist.nl names none.
    kieskeurig = recorded(tmp_path, KETTLES_KIESKEURIG)
    beslist = recorded(tmp_path, PANS_LISTING)

    assert kieskeurig.listed[0].brand == "Severin"
    assert {each.brand for each in beslist.listed} == {None}


def test_the_fetch_after_the_limit_returns_limit_reached(tmp_path: Path) -> None:
    service, calls = counted(fixture_page_service(FIXTURES))

    first, second = fetched(sources_with(tmp_path, service), 1, PAN, GONE)

    assert first.failure is None
    assert second.failure is FailureKind.LIMIT_REACHED
    assert len(calls) == 1


# --- The product data embedded in the page ---


def page_with(*blocks: str) -> PageService:
    """A page service whose one page holds these JSON-LD blocks, as Firecrawl returns it."""
    scripts = "".join(f'<script type="application/ld+json">{block}</script>' for block in blocks)

    async def fetch(request: PageRequest) -> StoredResponse:
        return StoredResponse(
            service=Service.FIRECRAWL,
            request={"url": request.url, "parameters": dict(request.parameters)},
            retrieved_at=NOON,
            response={
                "success": True,
                "data": {
                    "markdown": "",
                    "rawHtml": f"<html><head>{scripts}</head><body></body></html>",
                    "metadata": {"statusCode": 200},
                },
            },
        )

    return fetch


def product(offers: Any, name: str = "Kettle 1.7 l") -> str:
    return json.dumps(
        {"@context": "https://schema.org", "@type": "Product", "name": name, "offers": offers}
    )


def read(tmp_path: Path, *blocks: str) -> ProductPage:
    (page,) = fetched(sources_with(tmp_path, page_with(*blocks)), 1, PAN)
    return page


@pytest.mark.parametrize(
    ("offers", "price"),
    [
        ({"@type": "Offer", "price": "39.99", "priceCurrency": "EUR"}, "39.99"),
        ({"@type": "Offer", "price": "1.299,00", "priceCurrency": "EUR"}, "1299.00"),
        ({"@type": "Offer", "price": 39.99, "priceCurrency": "EUR"}, "39.99"),
        ([{"@type": "Offer", "price": "39,99", "priceCurrency": "EUR"}], "39.99"),
    ],
)
def test_the_euro_price_is_read_from_one_offer_or_a_list(
    tmp_path: Path, offers: Any, price: str
) -> None:
    assert read(tmp_path, product(offers)).price == Decimal(price)


def test_an_aggregate_offer_with_only_a_lowest_price_is_no_offer_and_no_price(
    tmp_path: Path,
) -> None:
    aggregate = {
        "@type": "AggregateOffer",
        "lowPrice": "34,50",
        "highPrice": "41",
        "priceCurrency": "EUR",
    }

    page = read(tmp_path, product(aggregate))

    assert (page.offer, page.price) == (OfferKind.LOWEST_PRICE_ONLY, None)


def test_a_used_offer_is_passed_over_for_the_first_new_one_with_a_price(tmp_path: Path) -> None:
    offers = [
        {
            "price": "19",
            "priceCurrency": "EUR",
            "itemCondition": "https://schema.org/UsedCondition",
        },
        {"priceCurrency": "EUR", "itemCondition": "https://schema.org/NewCondition"},
        {"price": "29", "priceCurrency": "EUR", "itemCondition": "https://schema.org/NewCondition"},
    ]

    assert read(tmp_path, product(offers)).price == Decimal("29")


def test_nested_offers_none_in_stock_give_the_cheapest_new_one_saying_so(tmp_path: Path) -> None:
    aggregate = {
        "@type": "AggregateOffer",
        "priceCurrency": "EUR",
        "offers": [
            {"price": 52, "availability": "https://schema.org/OutOfStock"},
            {"price": 48, "availability": "https://schema.org/SoldOut"},
        ],
    }

    page = read(tmp_path, product(aggregate))

    assert (page.price, page.in_stock) == (Decimal("48"), False)


def test_a_block_that_is_not_valid_json_is_skipped(tmp_path: Path) -> None:
    page = read(tmp_path, "{not json", product({"price": "20", "priceCurrency": "EUR"}))

    assert (page.name, page.price) == ("Kettle 1.7 l", Decimal("20"))


def test_a_product_inside_a_graph_with_a_list_of_types_is_found(tmp_path: Path) -> None:
    block = json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebPage", "name": "Shop"},
                {
                    "@type": ["Product", "Thing"],
                    "name": "Cordless drill 18 V",
                    "offers": {"price": "89", "priceCurrency": "EUR"},
                },
            ],
        }
    )

    page = read(tmp_path, block)

    assert (page.name, page.price) == ("Cordless drill 18 V", Decimal("89"))


def test_a_price_in_another_currency_is_unknown_and_names_the_currency(tmp_path: Path) -> None:
    page = read(tmp_path, product({"price": "45.00", "priceCurrency": "GBP"}))

    assert page.name == "Kettle 1.7 l"
    assert page.price is None
    assert page.other_currency == "GBP"


@pytest.mark.parametrize(
    "offers",
    [
        {"price": "45.00"},
        {"price": "about 45", "priceCurrency": "EUR"},
        {"priceCurrency": "EUR"},
    ],
)
def test_a_price_with_no_currency_or_no_readable_amount_is_unknown(
    tmp_path: Path, offers: Any
) -> None:
    page = read(tmp_path, product(offers))

    assert page.name == "Kettle 1.7 l"
    assert page.price is None
    assert page.other_currency is None


def test_a_page_with_no_product_data_gives_no_name_and_no_failure(tmp_path: Path) -> None:
    page = read(tmp_path)

    assert (page.name, page.price, page.failure) == (None, None, None)


def test_a_name_or_currency_that_is_not_text_counts_as_missing(tmp_path: Path) -> None:
    block = json.dumps(
        {
            "@type": "Product",
            "name": ["Kettle", "1.7 l"],
            "offers": {"price": "20", "priceCurrency": {"code": "EUR"}},
        }
    )

    page = read(tmp_path, block)

    assert (page.name, page.price, page.failure) == (None, None, None)
