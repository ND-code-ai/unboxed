"""Reading the product at a pasted link, with a fake page fetch and hand-written model replies.

The four outcomes are the table in docs/architecture/data_sources.md ("An unreadable link").
"""

import asyncio
import json
from datetime import UTC, date, datetime
from decimal import Decimal

from fakes import extraction, fake_chat
from shopper.agents.linked_product.agent import LINKED_OPTION_ID, LinkOutput, read_link
from shopper.llm import ChatError, ChatRequest
from shopper.state import (
    Material,
    Request,
    Scope,
    Source,
    SourceKind,
    StatedBy,
    TrailKind,
    Warning,
    WarningCode,
)
from shopper.tools.results import FailureKind, PageFetch, ProductPage

LINK = "https://shop.example/p/123"
PAGE_SOURCE = Source(kind=SourceKind.URL, reference=LINK)
# The shop is speaking about its own price.
SELLER_PAGE = PAGE_SOURCE.model_copy(update={"stated_by": StatedBy.SELLER})
PAN_PAGE = ProductPage(
    url=LINK,
    name="De Buyer Mineral B koekenpan 28 cm",
    brand="De Buyer",
    price=Decimal("54.95"),
    markdown="# De Buyer Mineral B koekenpan 28 cm\n\nCarbon steel, 2.1 kg.",
    credits=1,
    retrieved_at=datetime(2026, 10, 17, 9, 30, tzinfo=UTC),
)
WITH_CATEGORY = Request(
    original_text=f"{LINK} frying pan", product_url=LINK, category="frying pan", scope=Scope.TUNED
)
LINK_ONLY = Request(original_text=LINK, product_url=LINK, scope=Scope.GENERAL)


def details(
    materials: list[dict[str, str | None]] | None = None,
    weight_amount: float | None = None,
    weight_unit: str | None = None,
) -> str:
    """The model's read of the page text, written by hand."""
    return json.dumps(
        {"materials": materials or [], "weight_amount": weight_amount, "weight_unit": weight_unit}
    )


CARBON_STEEL = details([{"name": "carbon steel", "form": None}], 2.1, "kg")


def fetching(page: ProductPage) -> tuple[PageFetch, list[str]]:
    urls: list[str] = []

    async def fetch(url: str) -> ProductPage:
        urls.append(url)
        return page

    return fetch, urls


def read(
    request: Request, page: ProductPage, *replies: str | Exception
) -> tuple[LinkOutput, list[ChatRequest]]:
    chat, requests = fake_chat(replies)
    fetch, _ = fetching(page)
    return asyncio.run(read_link(request, chat, fetch)), requests


# --- Category known, product read: the pasted-link path ---


def test_a_read_page_becomes_the_linked_product_option() -> None:
    output, requests = read(WITH_CATEGORY, PAN_PAGE, CARBON_STEEL)

    assert output.request == WITH_CATEGORY
    assert output.product is not None
    assert output.product.id == LINKED_OPTION_ID
    assert output.product.name == "De Buyer Mineral B koekenpan 28 cm"
    assert output.product.brand == "De Buyer"
    assert output.product.price == Decimal("54.95")
    assert output.product.price_source == SELLER_PAGE
    assert output.product.price_seen_on == date(2026, 10, 17)
    assert output.product.link == LINK
    assert output.product.materials == (Material(name="carbon steel", source=PAGE_SOURCE),)
    assert output.product.weight_kg == Decimal("2.1")
    assert output.product.weight_source == PAGE_SOURCE
    assert output.warnings == ()
    assert len(requests) == 1
    assert "Carbon steel, 2.1 kg." in requests[0].messages[-1]["content"]


def test_a_product_its_page_says_is_out_of_stock_is_marked_so() -> None:
    gone = PAN_PAGE.model_copy(update={"in_stock": False})

    output, _ = read(WITH_CATEGORY, gone, CARBON_STEEL)
    in_stock, _ = read(WITH_CATEGORY, PAN_PAGE.model_copy(update={"in_stock": True}), CARBON_STEEL)
    unstated, _ = read(WITH_CATEGORY, PAN_PAGE, CARBON_STEEL)

    assert output.product is not None and output.product.out_of_stock is True
    assert in_stock.product is not None and in_stock.product.out_of_stock is False
    assert unstated.product is not None and unstated.product.out_of_stock is False


def test_the_link_is_fetched_once() -> None:
    chat, _ = fake_chat([CARBON_STEEL])
    fetch, urls = fetching(PAN_PAGE)

    asyncio.run(read_link(WITH_CATEGORY, chat, fetch))

    assert urls == [LINK]


def test_a_weight_in_grams_is_held_in_kilograms() -> None:
    output, _ = read(WITH_CATEGORY, PAN_PAGE, details(weight_amount=950, weight_unit="g"))

    assert output.product is not None
    assert output.product.weight_kg == Decimal("0.95")


def test_the_trail_names_the_product_read_and_whether_it_came_from_the_cache() -> None:
    fresh, _ = read(WITH_CATEGORY, PAN_PAGE, CARBON_STEEL)
    cached, _ = read(
        WITH_CATEGORY, PAN_PAGE.model_copy(update={"from_cache": True, "credits": 0}), CARBON_STEEL
    )

    assert fresh.trail[0].kind is TrailKind.FOUND
    assert fresh.trail[0].summary == (
        'Read the product at the link: "De Buyer Mineral B koekenpan 28 cm", €54.95'
    )
    assert fresh.trail[0].source == PAGE_SOURCE
    assert cached.trail[0].summary == (
        'Read the product at the link from the cache: "De Buyer Mineral B koekenpan 28 cm", €54.95'
    )
    assert fresh.trail[1].summary == "Read from the page: materials carbon steel; weight 2.1 kg"
    assert fresh.trail[1].model_tier == "small"


def test_the_model_reads_the_page_only_when_it_has_text() -> None:
    output, requests = read(WITH_CATEGORY, PAN_PAGE.model_copy(update={"markdown": " "}))

    assert output.product is not None
    assert output.product.materials == ()
    assert requests == []


def test_a_failed_read_of_the_page_text_leaves_materials_and_weight_unknown() -> None:
    output, _ = read(WITH_CATEGORY, PAN_PAGE, ChatError("down"))

    assert output.product is not None
    assert output.product.materials == ()
    assert output.product.weight_kg is None
    assert output.trail[-1].kind is TrailKind.EXCLUDED
    assert output.trail[-1].summary == "Materials and weight not read from the page"


def test_a_price_in_another_currency_is_left_out_with_its_warning() -> None:
    page = PAN_PAGE.model_copy(update={"price": None, "other_currency": "GBP"})

    output, _ = read(WITH_CATEGORY, page, CARBON_STEEL)

    assert output.product is not None
    assert output.product.price is None
    assert output.warnings == (
        Warning(
            code=WarningCode.LINK_PRICE_OTHER_CURRENCY,
            message=(
                "The price at your link is in GBP. This app works in euro only, so that price "
                "is not used and the figures that depend on it are not shown."
            ),
            option_id=LINKED_OPTION_ID,
        ),
    )


# --- No category, product read: the category comes from the product name ---


def test_with_no_category_the_product_name_gives_it() -> None:
    output, requests = read(LINK_ONLY, PAN_PAGE, extraction("frying pan", "tuned"), CARBON_STEEL)

    assert output.request.category == "frying pan"
    assert output.request.scope is Scope.TUNED
    assert requests[0].messages[-1]["content"] == "De Buyer Mineral B koekenpan 28 cm"
    assert output.product is not None


def test_a_product_name_that_is_declined_reads_nothing_more() -> None:
    output, requests = read(LINK_ONLY, PAN_PAGE, extraction("car", "not_a_product"))

    assert output.request.scope is Scope.NOT_A_PRODUCT
    assert len(requests) == 1


def test_a_product_name_the_model_cannot_place_runs_without_a_category() -> None:
    output, _ = read(LINK_ONLY, PAN_PAGE, extraction(None, "unclear"), CARBON_STEEL)

    assert output.request.scope is Scope.GENERAL
    assert output.request.category is None
    assert output.product is not None
    assert output.trail[-2].summary == "Changed the scope from unclear to general"


# --- Category known, product not read: the session continues with a warning ---


def test_an_unreadable_link_with_a_category_continues_with_its_warning() -> None:
    output, requests = read(WITH_CATEGORY, ProductPage(url=LINK, failure=FailureKind.BLOCKED))

    assert output.request == WITH_CATEGORY
    assert output.product is None
    assert output.warnings == (
        Warning(
            code=WarningCode.LINK_UNREADABLE,
            message=(
                "We couldn't read the product at your link, so it is not among the options "
                "below. These are options for frying pan."
            ),
        ),
    )
    assert output.trail[0].kind is TrailKind.EXCLUDED
    assert output.trail[0].reason == "blocked"
    assert requests == []


def test_a_page_with_no_product_name_is_unreadable() -> None:
    output, _ = read(WITH_CATEGORY, PAN_PAGE.model_copy(update={"name": None}))

    assert output.product is None
    assert output.trail[0].reason == "the page names no product"
    assert [warning.code for warning in output.warnings] == [WarningCode.LINK_UNREADABLE]


# --- No category, product not read: the session ends ---


def test_an_unreadable_link_with_no_category_makes_the_request_unclear() -> None:
    output, requests = read(LINK_ONLY, ProductPage(url=LINK, failure=FailureKind.NOT_FOUND))

    assert output.request.scope is Scope.UNCLEAR
    assert output.request.product_url == LINK
    assert output.product is None
    assert output.warnings == ()
    assert requests == []
