"""Option research from the comparison sites' listing pages: which pages are read, in which order,
and what is said when there is nothing to show (option_research.md, "Listing pages", "Product
pages", "Warnings")."""

from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from tco_replies import Ran, Shop, decided, left_out, run, warnings

from fakes import failing_search_service, finding, recording, sold_as
from pages import listed, listing_page, lowest_price_page, offer, product_page, results
from shopper.llm import ChatTimeoutError
from shopper.state import Request, Scope, TrailEntry, TrailKind, WarningCode
from shopper.tools.results import FailureKind, StoredResponse

KETTLE = Request(
    original_text="a kettle, budget 60 euro",
    category="kettle",
    scope=Scope.TUNED,
    budget=Decimal("60"),
)
TERM = "waterkoker"
SEARCH_QUERY = "waterkoker kopen"
BESLIST = "https://www.beslist.nl/products/huishoudelijke_apparatuur/waterkokers"
BESLIST_BRAND = "https://www.beslist.nl/products/huishoudelijke_apparatuur/waterkokers/r/alessi"
KIESKEURIG = "https://www.kieskeurig.nl/waterkoker"
KIESKEURIG_INFO = "https://www.kieskeurig.nl/waterkoker/informatie"


def beslist(name: str) -> str:
    return f"https://www.beslist.nl/p/{name.lower().replace(' ', '-')}/12000/1"


def kieskeurig(name: str) -> str:
    return f"https://www.kieskeurig.nl/waterkoker/product/1-{name.lower().replace(' ', '-')}"


def kettle(
    url: str, name: str, brand: str, price: str, shipping: str = "0"
) -> tuple[str, StoredResponse]:
    return url, product_page(url, name, brand, offer(price, shipping))


# Two kettles listed on beslist.nl, which names no brand, and three on kieskeurig.nl, whose price
# includes its shipping. The Epsilon is over the budget.
KETTLE_PAGES: dict[str, StoredResponse | FailureKind] = {
    BESLIST: listing_page(
        BESLIST,
        listed("Alpha Waterkoker 1.7L", beslist("Alpha Waterkoker"), "25"),
        listed("Beta Waterkoker 1L", beslist("Beta Waterkoker"), "40"),
    ),
    KIESKEURIG: listing_page(
        KIESKEURIG,
        listed("Gamma Waterkoker 1.5L", kieskeurig("Gamma Waterkoker"), "32.99", "Gamma"),
        listed("Delta Waterkoker 1.7L", kieskeurig("Delta Waterkoker"), "55", "Delta"),
        listed("Epsilon Waterkoker 1.7L", kieskeurig("Epsilon Waterkoker"), "90", "Epsilon"),
    ),
    **dict(
        (
            kettle(beslist("Alpha Waterkoker"), "Alpha Waterkoker 1.7L", "Alpha", "25"),
            kettle(beslist("Beta Waterkoker"), "Beta Waterkoker 1L", "Beta", "40"),
            kettle(
                kieskeurig("Gamma Waterkoker"), "Gamma Waterkoker 1.5L", "Gamma", "32.99", "2.99"
            ),
            kettle(kieskeurig("Delta Waterkoker"), "Delta Waterkoker 1.7L", "Delta", "55", "2.99"),
            kettle(kieskeurig("Epsilon Waterkoker"), "Epsilon Waterkoker 1.7L", "Epsilon", "90"),
        )
    ),
}
KETTLE_SHOP = Shop(finding({SEARCH_QUERY: results(BESLIST, KIESKEURIG)}), KETTLE_PAGES)


def kettles(tmp_path: Path, shop: Shop = KETTLE_SHOP, **given: Any) -> Ran:
    """The kettle request, with its local term, on the shop."""
    return run(tmp_path, shop=shop, request=KETTLE, local_term=TERM, **given)


def read_names(trail: Sequence[TrailEntry]) -> list[str]:
    """The candidates whose product page was read and offered them, in trail order."""
    return [
        entry.summary.split('"')[1]
        for entry in trail
        if entry.kind is TrailKind.FOUND and entry.summary.startswith('Read "')
    ]


# --- The listing pages ---


def test_the_products_within_the_budget_are_read_from_both_lists_taken_in_turn(
    tmp_path: Path,
) -> None:
    ran = kettles(tmp_path)

    assert read_names(ran.output.trail) == [
        "Alpha Waterkoker 1.7L",
        "Gamma Waterkoker 1.5L",
        "Beta Waterkoker 1L",
        "Delta Waterkoker 1.7L",
    ]
    assert kieskeurig("Epsilon Waterkoker") not in ran.fetched


def test_a_listing_search_nobody_recorded_is_not_recorded_and_the_search_did_not_work(
    tmp_path: Path,
) -> None:
    # The term and the category were written by a model, so the fixture twin answers them only
    # when they were recorded; here neither was.
    unrecorded = Shop(recording({}), KETTLE_PAGES)

    ran = run(tmp_path, shop=unrecorded, request=KETTLE, local_term="snelkoker")

    assert ('Could not search for "snelkoker kopen"', "not_recorded") in [
        (entry.summary, entry.reason) for entry in ran.output.trail
    ]
    assert "didn't work just now" in warnings(ran.output)[0][1]


def test_a_result_that_is_no_listing_page_of_the_whole_category_is_not_read(
    tmp_path: Path,
) -> None:
    # beslist.nl's "/r/" pages filter on a search word, kieskeurig.nl's "/informatie" informs.
    shop = Shop(
        finding({SEARCH_QUERY: results(BESLIST_BRAND, KIESKEURIG_INFO, BESLIST, KIESKEURIG)}),
        KETTLE_PAGES,
    )

    ran = kettles(tmp_path, shop)

    assert BESLIST_BRAND not in ran.fetched
    assert KIESKEURIG_INFO not in ran.fetched
    assert ran.fetched[:2] in ([BESLIST, KIESKEURIG], [KIESKEURIG, BESLIST])


def test_a_list_filtered_on_a_search_word_stands_for_the_listing_of_its_category(
    tmp_path: Path,
) -> None:
    # Task 1.15's live kettle search found only lists filtered on a search word or a brand.
    shop = Shop(finding({SEARCH_QUERY: results(BESLIST_BRAND, KIESKEURIG)}), KETTLE_PAGES)

    ran = kettles(tmp_path, shop)

    assert ran.fetched[:2] in ([BESLIST, KIESKEURIG], [KIESKEURIG, BESLIST])
    assert "Alpha Waterkoker 1.7L" in read_names(ran.output.trail)


def test_a_result_whose_page_lists_no_products_gives_way_to_the_next_on_that_site(
    tmp_path: Path,
) -> None:
    empty = "https://www.beslist.nl/products/huishoudelijke_apparatuur/waterkokers/c/kleur~1"
    pages = {**KETTLE_PAGES, empty: listing_page(empty)}
    shop = Shop(finding({SEARCH_QUERY: results(empty, BESLIST, KIESKEURIG)}), pages)

    ran = kettles(tmp_path, shop)

    assert "Alpha Waterkoker 1.7L" in read_names(ran.output.trail)
    assert any(
        entry.summary == "Read no listing page" and entry.reason == "it lists no products"
        for entry in ran.output.trail
    )


def test_the_listing_pages_tried_stay_within_the_twelve_pages_of_an_analysis(
    tmp_path: Path,
) -> None:
    # Eight results per site whose pages list nothing: each site may try half of the twelve.
    beslist_empty = [f"{BESLIST}/c/kleur~{number}" for number in range(8)]
    kieskeurig_empty = [f"{KIESKEURIG}/kleur-{number}" for number in range(8)]
    empty = [*beslist_empty, *kieskeurig_empty]
    pages = {**KETTLE_PAGES, **{url: listing_page(url) for url in empty}}
    shop = Shop(finding({SEARCH_QUERY: results(*empty), "kettle kopen": results(*empty)}), pages)

    ran = kettles(tmp_path, shop)

    assert len(ran.fetched) == 12
    assert set(ran.fetched) == {*beslist_empty[:6], *kieskeurig_empty[:6]}


def test_a_product_both_sites_list_is_read_once(tmp_path: Path) -> None:
    pages = {
        **KETTLE_PAGES,
        KIESKEURIG: listing_page(
            KIESKEURIG,
            listed("Alpha AW-1700 Waterkoker", kieskeurig("Alpha AW-1700"), "26", "Alpha"),
            listed("Gamma Waterkoker 1.5L", kieskeurig("Gamma Waterkoker"), "32.99", "Gamma"),
        ),
        BESLIST: listing_page(
            BESLIST,
            listed("Alpha AW-1700 Waterkoker 1.7L", beslist("Alpha Waterkoker"), "25"),
            listed("Beta Waterkoker 1L", beslist("Beta Waterkoker"), "40"),
        ),
    }
    shop = Shop(finding({SEARCH_QUERY: results(BESLIST, KIESKEURIG)}), pages)

    ran = kettles(tmp_path, shop)

    assert kieskeurig("Alpha AW-1700") not in ran.fetched
    assert (
        'Kept "Alpha AW-1700 Waterkoker 1.7L" once',
        '"Alpha AW-1700 Waterkoker" on another site names the same product',
    ) in decided(ran.output)


def test_two_models_whose_numbers_are_written_in_parts_are_two_products(tmp_path: Path) -> None:
    # "Makita DHP 490 Z" matched "Makita DHP 482 Z" on its other words in task 1.12.
    drill = Request(original_text="a drill", category="drill", scope=Scope.TUNED)
    one, other = "Makita DHP 490 Z Accuboormachine Solo", "Makita DHP 482 Z Accuboormachine Solo"
    beslist_listing_page = "https://www.beslist.nl/products/klussen/boormachines"
    kieskeurig_listing_page = "https://www.kieskeurig.nl/boormachine"
    pages = {
        beslist_listing_page: listing_page(beslist_listing_page, listed(one, beslist(one), "90")),
        kieskeurig_listing_page: listing_page(
            kieskeurig_listing_page, listed(other, kieskeurig(other), "95", "Makita")
        ),
        beslist(one): product_page(beslist(one), one, "Makita", offer("90")),
        kieskeurig(other): product_page(kieskeurig(other), other, "Makita", offer("95", "0")),
    }
    shop = Shop(
        finding({"drill kopen": results(beslist_listing_page, kieskeurig_listing_page)}), pages
    )

    ran = run(tmp_path, shop=shop, request=drill)

    assert kieskeurig(other) in ran.fetched
    assert beslist(one) in ran.fetched


def test_two_products_of_one_brand_that_share_only_a_size_are_two_products(
    tmp_path: Path,
) -> None:
    # The recorded lists of task 1.12 hold a Demeyere Proline 7 and a Demeyere Apollo 7.
    proline, apollo = "Demeyere Proline 7 Waterkoker 1.7 L", "Demeyere Apollo 7 Waterkoker 1.7 L"
    pages = {
        BESLIST: listing_page(BESLIST, listed(proline, beslist(proline), "50")),
        KIESKEURIG: listing_page(KIESKEURIG, listed(apollo, kieskeurig(apollo), "55", "Demeyere")),
        beslist(proline): product_page(beslist(proline), proline, "Demeyere", offer("50")),
        kieskeurig(apollo): product_page(kieskeurig(apollo), apollo, "Demeyere", offer("55", "0")),
    }
    # Two names hold the term, so the category is searched again; the term names no product.
    found = results(BESLIST, KIESKEURIG)
    shop = Shop(finding({SEARCH_QUERY: found, "kettle kopen": found}), pages)

    ran = run(tmp_path, shop=shop, request=KETTLE, local_term=TERM)

    assert kieskeurig(apollo) in ran.fetched
    assert beslist(proline) in ran.fetched


def test_two_products_of_one_brand_that_share_only_a_colour_are_two_products(
    tmp_path: Path,
) -> None:
    # Kept once in task 1.15's live run, by "zwart".
    pan = Request(original_text="a frying pan", category="frying pan", scope=Scope.TUNED)
    braadpan = "Tefal Trattoria Braadpan - 24 cm - Zwart - Inductie"
    koekenpan = "Tefal - So Expert - Koekenpan - Zwart - Aluminium - Antiaanbaklaag"
    beslist_listing_page = "https://www.beslist.nl/products/huis_tuin/koekenpannen"
    kieskeurig_listing_page = "https://www.kieskeurig.nl/pan"
    pages = {
        beslist_listing_page: listing_page(
            beslist_listing_page, listed(braadpan, beslist(braadpan), "40")
        ),
        kieskeurig_listing_page: listing_page(
            kieskeurig_listing_page, listed(koekenpan, kieskeurig(koekenpan), "35", "Tefal")
        ),
        beslist(braadpan): product_page(beslist(braadpan), braadpan, "Tefal", offer("40")),
        kieskeurig(koekenpan): product_page(
            kieskeurig(koekenpan), koekenpan, "Tefal", offer("35", "0")
        ),
    }
    found = results(beslist_listing_page, kieskeurig_listing_page)
    shop = Shop(finding({"frying pan kopen": found}), pages)

    ran = run(tmp_path, shop=shop, request=pan)

    assert kieskeurig(koekenpan) in ran.fetched
    assert beslist(braadpan) in ran.fetched


def test_a_local_term_in_too_few_listed_names_searches_again_with_the_category(
    tmp_path: Path,
) -> None:
    # Only one listed name holds "snelkoker"; the search with "kettle" finds the same pages.
    shop = Shop(
        finding(
            {"snelkoker kopen": results(BESLIST), "kettle kopen": results(BESLIST, KIESKEURIG)}
        ),
        KETTLE_PAGES,
    )

    ran = run(tmp_path, shop=shop, request=KETTLE, local_term="snelkoker")

    assert (
        'Searched the listing pages with the category "kettle"; product names are not checked '
        "for the local term",
        '"snelkoker" stands in 0 listed product names, fewer than 3',
    ) in decided(ran.output)
    assert ran.fetched.count(BESLIST) == 1
    assert len(ran.output.options) == 3


def test_when_the_search_with_the_category_names_no_product_the_terms_candidates_stand(
    tmp_path: Path,
) -> None:
    shop = Shop(
        finding({"snelkoker kopen": results(BESLIST, KIESKEURIG), "kettle kopen": results()}),
        KETTLE_PAGES,
    )

    ran = run(tmp_path, shop=shop, request=KETTLE, local_term="snelkoker")

    assert (
        "The candidates of the first listing search stand",
        'the search with "kettle" named no product',
    ) in decided(ran.output)
    assert len(ran.output.options) == 3


def test_with_no_local_term_the_category_is_searched(tmp_path: Path) -> None:
    shop = Shop(finding({"kettle kopen": results(BESLIST, KIESKEURIG)}), KETTLE_PAGES)

    ran = run(tmp_path, shop=shop, request=KETTLE, local_term=None)

    assert len(ran.output.options) == 3
    assert any(
        reason == "category research found no local category term"
        for _, reason in decided(ran.output)
    )


# --- The product pages ---


def ten_kettles() -> Shop:
    """Ten kettles within the budget on one beslist.nl listing page."""
    named = [f"Kettle {letter} Waterkoker" for letter in "ABCDEFGHIJ"]
    pages: dict[str, StoredResponse | FailureKind] = {
        BESLIST: listing_page(
            BESLIST, *(listed(name, beslist(name), str(20 + n)) for n, name in enumerate(named))
        ),
        **{
            beslist(name): product_page(beslist(name), name, "Kettle", offer(str(20 + n)))
            for n, name in enumerate(named)
        },
    }
    return Shop(finding({SEARCH_QUERY: results(BESLIST)}), pages)


def test_the_reads_stop_at_five_buyable_candidates(tmp_path: Path) -> None:
    ran = kettles(tmp_path, ten_kettles())

    assert len(ran.fetched) == 1 + 5
    assert ("Left 5 listed products unread", "5 buyable candidates found") in decided(ran.output)


def test_a_page_that_does_not_sell_the_item_is_not_counted_and_the_next_is_read(
    tmp_path: Path,
) -> None:
    lid = "Kettle B Waterkoker"
    ran = kettles(
        tmp_path,
        ten_kettles(),
        page_reads={lid: sold_as(lid, "part_or_accessory", "Kettle B")},
    )

    assert len(ran.fetched) == 1 + 6
    assert left_out(ran.output)[lid] == "the page sells a part or accessory, not the item itself"


def test_the_reads_stop_at_twelve_pages_with_the_listing_page_among_them(tmp_path: Path) -> None:
    shop = ten_kettles()
    named = [f"Kettle {letter} Waterkoker" for letter in "ABCDEFGHIJ"]
    reads = {name: sold_as(name, "other_kind", name) for name in named}
    more = {
        **shop.pages,
        BESLIST: listing_page(
            BESLIST,
            *(listed(name, beslist(name), "30") for name in named),
            *(listed(f"Extra {n} Waterkoker", beslist(f"Extra {n}"), "30") for n in range(3)),
        ),
        **{
            beslist(f"Extra {n}"): product_page(
                beslist(f"Extra {n}"), f"Extra {n} Waterkoker", "Extra", offer("30")
            )
            for n in range(3)
        },
    }

    ran = kettles(tmp_path, Shop(shop.search, more), page_reads=reads)

    assert len(ran.fetched) == 12
    assert (
        "Left 2 listed products unread",
        "12 pages were read, the listing pages among them",
    ) in decided(ran.output)


def test_with_no_budget_every_listed_product_counts_as_within_it(tmp_path: Path) -> None:
    no_budget = KETTLE.model_copy(update={"budget": None})

    ran = run(tmp_path, shop=KETTLE_SHOP, request=no_budget, local_term=TERM)

    assert kieskeurig("Epsilon Waterkoker") in ran.fetched


def test_a_page_with_only_a_lowest_price_drops_its_candidate(tmp_path: Path) -> None:
    pages = {
        **KETTLE_PAGES,
        beslist("Alpha Waterkoker"): lowest_price_page(
            beslist("Alpha Waterkoker"), "Alpha Waterkoker 1.7L", "25"
        ),
    }

    ran = kettles(tmp_path, Shop(KETTLE_SHOP.search, pages))

    assert left_out(ran.output)["Alpha Waterkoker 1.7L"] == (
        "its page at beslist.nl gives only a lowest price"
    )


def test_a_page_rate_limited_twice_is_skipped_and_counted(tmp_path: Path) -> None:
    pages = {**KETTLE_PAGES, beslist("Alpha Waterkoker"): FailureKind.RATE_LIMITED}

    ran = kettles(tmp_path, Shop(KETTLE_SHOP.search, pages))

    assert left_out(ran.output)["Alpha Waterkoker 1.7L"] == (
        "its page was skipped after Firecrawl's second rate limit (rate_limited)"
    )
    assert len(ran.output.options) == 3


# --- Warnings ---


def test_exactly_one_option_is_a_warning(tmp_path: Path) -> None:
    pages = {
        BESLIST: listing_page(BESLIST, listed("Alpha Waterkoker 1.7L", beslist("Alpha"), "25")),
        beslist("Alpha"): product_page(
            beslist("Alpha"), "Alpha Waterkoker 1.7L", "Alpha", offer("25")
        ),
    }

    ran = run(
        tmp_path, shop=Shop(finding({"kettle kopen": results(BESLIST)}), pages), request=KETTLE
    )

    assert [code for code, _ in warnings(ran.output)] == [WarningCode.ONE_OPTION_ONLY]


def test_a_failed_listing_search_says_the_search_did_not_work(tmp_path: Path) -> None:
    shop = Shop(failing_search_service(FailureKind.UNAVAILABLE), KETTLE_PAGES)

    ran = kettles(tmp_path, shop)

    assert warnings(ran.output) == [
        (
            WarningCode.NO_OPTIONS_FOUND,
            "The search for kettle options didn't work just now, so there are no options to "
            "compare. Try again in a moment.",
        )
    ]


def test_every_product_page_failing_says_the_search_did_not_work(tmp_path: Path) -> None:
    pages = {
        url: (page if url in (BESLIST, KIESKEURIG) else FailureKind.UNAVAILABLE)
        for url, page in KETTLE_PAGES.items()
    }

    ran = kettles(tmp_path, Shop(KETTLE_SHOP.search, pages))

    assert [code for code, _ in warnings(ran.output)] == [WarningCode.NO_OPTIONS_FOUND]
    assert "didn't work just now" in warnings(ran.output)[0][1]


def test_no_page_selling_the_item_says_nothing_with_a_euro_price_was_found(tmp_path: Path) -> None:
    reads = {
        name: sold_as(name, "other_kind", name)
        for name in (
            "Alpha Waterkoker 1.7L",
            "Beta Waterkoker 1L",
            "Gamma Waterkoker 1.5L",
            "Delta Waterkoker 1.7L",
        )
    }

    ran = kettles(tmp_path, page_reads=reads)

    assert warnings(ran.output) == [
        (
            WarningCode.NO_OPTIONS_FOUND,
            "We couldn't find a kettle with a price in euro, so there are no options to compare.",
        )
    ]


def test_a_failed_judgement_by_name_leaves_every_judgement_unknown_and_reads_on(
    tmp_path: Path,
) -> None:
    ran = kettles(tmp_path, by_name=ChatTimeoutError("no answer"))

    assert len(ran.output.options) == 3
    assert any(
        entry.summary == "Could not judge the candidates by their names"
        for entry in ran.output.trail
    )
