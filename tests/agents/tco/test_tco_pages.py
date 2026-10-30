"""A candidate's product page: the offer that stands, what the page sells, and the marks it gives
the option (option_research.md, "The offer on a product page", "What a product page sells")."""

import asyncio
import json
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from tco_replies import (
    BUDGET_PAN,
    KIESKEURIG_PANS,
    PAN_TERM,
    Ran,
    Shop,
    at_kieskeurig,
    decided,
    kieskeurig_pans,
    left_out,
    option,
    prices,
    run,
)

from fakes import finding, sold_as
from pages import OUT_OF_STOCK, listed, listing_page, offer, product_page, results
from shopper.agents.tco.prompt import PAGE_PROMPT
from shopper.state import Request, Scope, Source, SourceKind
from shopper.tools.product_page import page_request
from shopper.tools.product_page import product_page as product_page_read
from shopper.tools.results import FailureKind, PageRequest, StoredResponse

BESLIST = "https://www.beslist.nl/products/huis_tuin/huis_tuin_505129_505236"


def at_beslist(name: str) -> str:
    return f"https://www.beslist.nl/p/{name.lower().replace(' ', '-')}/165/1"


def pans(tmp_path: Path, shop: Shop, **given: Any) -> Ran:
    return run(tmp_path, shop=shop, request=BUDGET_PAN, local_term=PAN_TERM, **given)


GREENCHEF = "GreenChef Diamond Koekenpan 24 cm"
TEFAL = "Tefal Renew ON Koekenpan 24 cm"
WMF = "WMF Profi Resist Koekenpan 28 cm"
THREE_PANS = ((GREENCHEF, "26.98", None), (TEFAL, "38.98", None), (WMF, "44.99", None))


# --- The offer that stands ---


def test_kieskeurigs_price_has_its_shipping_taken_off_and_the_option_keeps_the_shipping(
    tmp_path: Path,
) -> None:
    # GreenChef at bol.: €26.98 on kieskeurig.nl is €23.99 plus €2.99 shipping.
    ran = pans(tmp_path, kieskeurig_pans(*THREE_PANS))

    greenchef = option(ran.output, GREENCHEF)
    assert (greenchef.price, greenchef.shipping) == (Decimal("23.99"), Decimal("2.99"))
    assert greenchef.link == at_kieskeurig(GREENCHEF)


def test_the_price_source_is_the_product_page_labelled_with_the_shop_that_sells_it(
    tmp_path: Path,
) -> None:
    ran = pans(tmp_path, kieskeurig_pans(*THREE_PANS))

    assert option(ran.output, GREENCHEF).price_source == Source(
        kind=SourceKind.URL,
        reference=at_kieskeurig(GREENCHEF),
        label="Shop.nl",
    )


def test_an_offer_far_under_the_pages_other_offers_is_left_out(tmp_path: Path) -> None:
    # The Metabo SBE 650's €32.95 against €63.27 to €114.94 in task 1.12.
    page = product_page(
        at_kieskeurig(WMF),
        WMF,
        "WMF",
        offer("20.00", "0", seller="Cheap.nl"),
        offer("44.99", "0", seller="A.nl"),
        offer("46.00", "0", seller="B.nl"),
        offer("48.00", "0", seller="C.nl"),
    )

    ran = pans(tmp_path, kieskeurig_pans((WMF, "44.99", page)))

    assert option(ran.output, WMF).price == Decimal("44.99")
    assert any(
        entry.summary == f'Left out the offer of Cheap.nl at €20 on the page of "{WMF}"'
        for entry in ran.output.trail
    )


def test_a_sale_at_more_than_half_of_the_median_stands(tmp_path: Path) -> None:
    # The WMF Profi Resist on beslist.nl, live in task 1.15: bol.com and Joybuy.nl at €44.99, nine
    # shops at €76.95 to €95.90, under one EAN; 58% of the median.
    others = ("76.95",) * 4 + ("79.99", "82.99", "82.99", "91.81", "95.90")
    page = product_page(
        at_kieskeurig(WMF),
        WMF,
        "WMF",
        offer("44.99", "0", seller="bol.com"),
        offer("44.99", "0", seller="Joybuy.nl"),
        *(offer(price, "0", seller=f"Shop{number}.nl") for number, price in enumerate(others)),
    )

    ran = pans(tmp_path, kieskeurig_pans((WMF, "44.99", page)))

    assert option(ran.output, WMF).price == Decimal("44.99")


def test_a_kieskeurig_offer_with_no_shipping_stated_gives_way_to_one_that_states_it(
    tmp_path: Path,
) -> None:
    page = product_page(
        at_kieskeurig(WMF),
        WMF,
        "WMF",
        offer("30.00", None, seller="NoShipping.nl"),
        offer("44.99", "0", seller="A.nl"),
    )

    ran = pans(tmp_path, kieskeurig_pans((WMF, "30", page)))

    assert option(ran.output, WMF).price == Decimal("44.99")


def test_a_beslist_offer_states_no_condition_and_counts_as_new(tmp_path: Path) -> None:
    pages = {
        BESLIST: listing_page(BESLIST, listed(WMF, at_beslist(WMF), "44.99")),
        at_beslist(WMF): product_page(
            at_beslist(WMF), WMF, "WMF", offer("44.99", "3.99", condition=None)
        ),
    }

    ran = run(
        tmp_path,
        shop=Shop(finding({"frying pan kopen": results(BESLIST)}), pages),
        request=BUDGET_PAN,
    )

    wmf = option(ran.output, WMF)
    assert (wmf.price, wmf.shipping) == (Decimal("44.99"), Decimal("3.99"))


def test_with_no_offer_in_stock_the_cheapest_stands_and_the_option_is_out_of_stock(
    tmp_path: Path,
) -> None:
    page = product_page(
        at_kieskeurig(WMF), WMF, "WMF", offer("42.99", "2.99", availability=OUT_OF_STOCK)
    )

    ran = pans(tmp_path, kieskeurig_pans((GREENCHEF, "26.98", None), (WMF, "42.99", page)))

    wmf = option(ran.output, WMF)
    assert (wmf.price, wmf.out_of_stock) == (Decimal("40.00"), True)
    assert ran.output.options[-1] == wmf


def test_a_page_that_names_no_size_while_most_listed_products_do_says_so(tmp_path: Path) -> None:
    page = product_page(
        at_kieskeurig("WMF Profi"), "WMF Profi Resist Koekenpan", "WMF", offer("44.99", "0")
    )

    ran = pans(
        tmp_path,
        kieskeurig_pans(
            (GREENCHEF, "26.98", None), (TEFAL, "38.98", None), ("WMF Profi", "44.99", page)
        ),
    )

    assert (
        'The page of "WMF Profi Resist Koekenpan" states no size or variant',
        "most products listed for the category name one",
    ) in decided(ran.output)


def test_a_diameter_written_after_its_sign_is_a_size(tmp_path: Path) -> None:
    # The GreenChef's page of task 1.15's live run.
    greenchef = "GreenChef Diamond Inductie Koekenpan Ø24 cm"
    page = product_page(at_kieskeurig("GreenChef"), greenchef, "GreenChef", offer("26.98", "0"))

    ran = pans(
        tmp_path,
        kieskeurig_pans(("GreenChef", "26.98", page), (TEFAL, "38.98", None), (WMF, "44.99", None)),
    )

    assert not any(
        summary.startswith(f'The page of "{greenchef}"') for summary, _ in decided(ran.output)
    )


# --- What the page sells ---


def test_a_page_whose_name_lacks_the_local_term_needs_it_in_what_the_page_sells(
    tmp_path: Path,
) -> None:
    # The Tefal Trattoria braadpan was read as the item in task 1.12.
    braadpan = "Tefal Trattoria Braadpan 24 cm"
    hapjespan = "Tefal Renew Hapjespan 24 cm"
    hapjespan_page = product_page(
        at_kieskeurig(hapjespan),
        hapjespan,
        "Tefal",
        offer("45", "2.99"),
        markdown=f"# {hapjespan}\nOok te gebruiken als koekenpan",
    )

    ran = pans(
        tmp_path,
        kieskeurig_pans((braadpan, "41.99", None), (hapjespan, "45", hapjespan_page), *THREE_PANS),
        page_reads={
            braadpan: sold_as(braadpan, "the_item", "Braadpan"),
            hapjespan: sold_as(hapjespan, "the_item", "te gebruiken als koekenpan"),
        },
    )

    assert left_out(ran.output)[braadpan] == (
        'neither its name nor what the page sells holds the local term "koekenpan"'
    )
    assert any(
        entry.summary.startswith(f'Read "{hapjespan}" at kieskeurig.nl')
        for entry in ran.output.trail
    )


def test_the_local_term_in_the_plural_as_a_part_of_its_own_is_the_shops_category_not_the_name(
    tmp_path: Path,
) -> None:
    # Task 1.14 read this travel immersion heater as the item in 1 or 2 of 5 reads.
    heater = "Rommelsbacher - Reisdompelaar Type 343 - Waterkokers - 350 Watt - Met Glas"
    kettle = "Inventum HW817D Waterkoker - 1.7L - RVS/Zwart - 2200W"
    listing = "https://www.beslist.nl/products/huishoudelijke_apparatuur/waterkokers"
    shop = Shop(
        finding({"waterkoker kopen": results(listing)}),
        {
            listing: listing_page(
                listing,
                *(
                    listed(name, at_beslist(name), "25")
                    for name in (heater, kettle, kettle, kettle)
                ),
            ),
            at_beslist(heater): product_page(
                at_beslist(heater), heater, "Rommelsbacher", offer("25")
            ),
            at_beslist(kettle): product_page(at_beslist(kettle), kettle, "Inventum", offer("25")),
        },
    )
    kettle_request = Request(original_text="a kettle", category="kettle", scope=Scope.TUNED)

    ran = run(
        tmp_path,
        shop=shop,
        request=kettle_request,
        local_term="waterkoker",
        page_reads={heater: sold_as(heater, "the_item", heater)},
    )

    assert left_out(ran.output)[heater] == (
        'neither its name nor what the page sells holds the local term "waterkoker"'
    )


def test_the_local_term_stands_in_a_name_that_writes_it_apart_or_shares_its_last_word(
    tmp_path: Path,
) -> None:
    # Names of task 1.15's live drill run; "Bosch PSB Boormachine" is corded.
    listing = "https://www.kieskeurig.nl/boormachine/beste"
    drills = (
        "Bosch EasyDrill 18V-38 Accu-boormachine",
        "Makita DHP 490 Z Accu Klopboormachine",
        "Einhell TE-CD 18 Accu klopboor-/schroefmachine",
        "Bosch PSB 1800 Boormachine",
    )

    def at(name: str) -> str:
        return f"https://www.kieskeurig.nl/boormachine/product/{drills.index(name)}"

    shop = Shop(
        finding({"accuboormachine kopen": results(listing)}),
        {
            listing: listing_page(
                listing, *(listed(name, at(name), "60", name.split()[0]) for name in drills)
            ),
            **{
                at(name): product_page(at(name), name, name.split()[0], offer("60"))
                for name in drills
            },
        },
    )
    cordless = Request(
        original_text="a cordless drill", category="cordless drill", scope=Scope.TUNED
    )

    ran = run(tmp_path, shop=shop, request=cordless, local_term="accuboormachine")

    assert left_out(ran.output) == {
        "Bosch PSB 1800 Boormachine": (
            'neither its name nor what the page sells holds the local term "accuboormachine"'
        )
    }


def test_an_item_sold_without_a_part_is_a_candidate_marked_incomplete(tmp_path: Path) -> None:
    bare = "WMF Profi Koekenpan 28 cm zonder deksel"

    ran = pans(
        tmp_path,
        kieskeurig_pans((bare, "30", None), (GREENCHEF, "26.98", None)),
        page_reads={bare: sold_as(bare, "incomplete", "zonder deksel")},
    )

    assert option(ran.output, bare).incomplete is True


@pytest.mark.parametrize(
    ("name", "incomplete"),
    [
        # Read as the item itself in task 1.10's live drill run.
        ("WMF Profi Koekenpan 28 cm (Body)", True),
        ("WMF Profi Koekenpan 28 cm - Zonder deksel", True),
        ("WMF Profi Koekenpan 28 cm met soft-touch body", False),
    ],
)
def test_an_item_whose_own_name_says_it_lacks_a_part_is_marked_incomplete(
    tmp_path: Path, name: str, incomplete: bool
) -> None:
    ran = pans(
        tmp_path,
        kieskeurig_pans((name, "30", None), (GREENCHEF, "26.98", None)),
        page_reads={name: sold_as(name, "the_item", name)},
    )

    assert option(ran.output, name).incomplete is incomplete


def test_an_item_called_incomplete_by_no_quote_that_names_a_missing_part_is_left_out(
    tmp_path: Path,
) -> None:
    ran = pans(
        tmp_path,
        kieskeurig_pans(*THREE_PANS),
        page_reads={WMF: sold_as(WMF, "incomplete", "WMF Profi Resist")},
    )

    assert left_out(ran.output)[WMF] == (
        "the page read says it lacks a part, but its quote names no missing part"
    )


def test_what_the_pages_own_product_sells_decides_over_the_products_shown_beside_it(
    tmp_path: Path,
) -> None:
    # The Makita DF330DWE was turned away by the similar products below it in task 1.12.
    beside = {
        "results": [
            {
                "result": 1,
                "amounts": [
                    {
                        "quote": "€ 1",
                        "name": name,
                        "sells": sells,
                        "sells_quote": quote,
                        "piece_count": None,
                        "piece_count_quote": None,
                    }
                    for name, sells, quote in (
                        (WMF, "the_item", WMF),
                        ("WMF Wok", "other_kind", "WMF"),
                        ("WMF Pannenset", "set_or_bundle", "WMF"),
                    )
                ],
            }
        ]
    }

    ran = pans(tmp_path, kieskeurig_pans(*THREE_PANS), page_reads={WMF: json.dumps(beside)})

    assert option(ran.output, WMF).name == WMF


def test_a_set_request_takes_the_piece_count_its_page_quotes(tmp_path: Path) -> None:
    pan_set = Request(
        original_text="a pan set", category="pan set", scope=Scope.TUNED, budget=Decimal("200")
    )
    name = "Tefal Ingenio Pannenset 3-delig"
    pages = {
        BESLIST: listing_page(BESLIST, listed(name, at_beslist(name), "99")),
        at_beslist(name): product_page(
            at_beslist(name), name, "Tefal", offer("99"), markdown=f"# {name}\n3-delig"
        ),
    }

    ran = run(
        tmp_path,
        shop=Shop(finding({"pan set kopen": results(BESLIST)}), pages),
        request=pan_set,
        by_name='{"set_requested": true, "candidates": []}',
        page_reads={
            name: sold_as(name, "set_or_bundle", name, piece_count=3, piece_count_quote="3-delig")
        },
    )

    assert option(ran.output, name).piece_count == 3


def test_a_set_with_no_quoted_piece_count_is_left_out(tmp_path: Path) -> None:
    pan_set = Request(
        original_text="a pan set", category="pan set", scope=Scope.TUNED, budget=Decimal("200")
    )
    name = "Tefal Ingenio Pannenset"
    pages = {
        BESLIST: listing_page(BESLIST, listed(name, at_beslist(name), "99")),
        at_beslist(name): product_page(at_beslist(name), name, "Tefal", offer("99")),
    }

    ran = run(
        tmp_path,
        shop=Shop(finding({"pan set kopen": results(BESLIST)}), pages),
        request=pan_set,
        by_name='{"set_requested": true, "candidates": []}',
        page_reads={name: sold_as(name, "set_or_bundle", name)},
    )

    assert left_out(ran.output)[name] == "a set is asked for and it has no quoted piece count"


# --- Names ---


def test_the_name_and_brand_come_from_the_page_and_a_sub_brand_is_cut_to_its_words_in_the_name(
    tmp_path: Path,
) -> None:
    listed_name = "Bosch EasyDrill 18V-38 accu"
    page_name = "Bosch - EasyDrill 18V-38 - Accu-schroefboormachine"
    url = at_beslist("bosch-easydrill")
    drill = Request(original_text="a drill", category="drill", scope=Scope.TUNED)
    pages = {
        BESLIST: listing_page(BESLIST, listed(listed_name, url, "49.99")),
        url: product_page(url, page_name, "Bosch Home and Garden", offer("49.99")),
    }

    ran = run(tmp_path, shop=Shop(finding({"drill kopen": results(BESLIST)}), pages), request=drill)

    (easydrill,) = ran.output.options
    assert (easydrill.name, easydrill.brand) == (page_name, "Bosch")


# --- How many at once ---


def test_at_most_three_pages_are_read_at_once(tmp_path: Path) -> None:
    shop = kieskeurig_pans(*((f"Pan {letter} Koekenpan 24 cm", "30", None) for letter in "ABCDEFG"))
    reading = 0
    most = 0

    async def slow(request: PageRequest) -> StoredResponse | FailureKind:
        nonlocal reading, most
        reading += 1
        most = max(most, reading)
        await asyncio.sleep(0.01)
        reading -= 1
        return shop.pages[request.url]

    ran = pans(tmp_path, shop, page_service=slow)

    assert len(ran.output.options) == 3
    assert most == 3


# --- The recorded page reads of task 1.14, replayed ---

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"
# Real frying pan pages, with their text as far as the read sees it, and the real model's read of
# each with the trimmed prompt (docs/findings/task_1.14.md). The WMF was left out as "not quoted"
# by the prompt before it.
RECORDED_PAGES = (
    "03-beslist-wmf-profi-resist-koekenpan-roestvrij-sta",
    "04-kieskeurig-tefal-trattoria-braadpan-24-cm-zwart-ind",
    "05-kieskeurig-greenchef-diamond-inductie-koekenpan-24",
    "08-kieskeurig-tefal-renew-black-on-keramische-hapjespa",
    "10-kieskeurig-tefal-xl-force-wokpan-28-cm-zwart",
)

# A third name with "koekenpan", over the budget and so never read, has the names checked for the
# local term, as they were when the replies were recorded.
DEMEYERE = "Demeyere Industry 5 Koekenpan 28 cm"


class Recorded(NamedTuple):
    page: StoredResponse
    name: str
    system: str
    input: str
    reply: str


def recorded(fixture: str) -> Recorded:
    """A recorded page, its product's name, and the recorded read of it with its prompt and
    input."""
    page_file = FIXTURES / "firecrawl" / f"frying-pan-{fixture}-page.json"
    page = StoredResponse.model_validate_json(page_file.read_text(encoding="utf-8"))
    name = product_page_read(page_request(page.request["url"]), page, from_cache=True).name
    assert name is not None
    read_file = FIXTURES / "nebius" / f"page-read-frying-pan-{fixture}.json"
    read = json.loads(read_file.read_text(encoding="utf-8"))
    return Recorded(page, name, read["system"], read["input"], read["reply"])


@cache
def recorded_pages() -> dict[str, Recorded]:
    return {fixture: recorded(fixture) for fixture in RECORDED_PAGES}


def replayed(tmp_path: Path) -> Ran:
    """The recorded pages on one listing page, each read by its recorded reply."""
    replays = recorded_pages()
    pages = {each.page.request["url"]: each.page for each in replays.values()}
    listing = listing_page(
        KIESKEURIG_PANS,
        *(listed(each.name, url, "40") for url, each in zip(pages, replays.values(), strict=True)),
        listed(DEMEYERE, at_kieskeurig(DEMEYERE), "150"),
    )
    shop = Shop(
        finding({"koekenpan kopen": results(KIESKEURIG_PANS)}), {KIESKEURIG_PANS: listing, **pages}
    )
    reads = {each.name: each.reply for each in replays.values()}
    return pans(tmp_path, shop, page_reads=reads)


def test_the_recorded_reads_are_replayed_over_the_prompt_and_input_they_were_recorded_on(
    tmp_path: Path,
) -> None:
    ran = replayed(tmp_path)

    replays = recorded_pages()
    sent = [
        (request.messages[0]["content"], request.messages[1]["content"])
        for request in ran.requests
        if request.messages[0]["content"] == PAGE_PROMPT
    ]
    assert sorted(sent) == sorted((each.system, each.input) for each in replays.values())


def test_the_recorded_reads_take_the_frying_pans_at_their_offers(tmp_path: Path) -> None:
    ran = replayed(tmp_path)

    replays = recorded_pages()
    assert prices(ran.output) == [
        (replays["05-kieskeurig-greenchef-diamond-inductie-koekenpan-24"].name, Decimal("23.99")),
        (replays["03-beslist-wmf-profi-resist-koekenpan-roestvrij-sta"].name, Decimal("44.99")),
    ]


def test_the_recorded_reads_leave_out_the_pans_that_are_no_frying_pan(tmp_path: Path) -> None:
    ran = replayed(tmp_path)

    no_frying_pan = 'neither its name nor what the page sells holds the local term "koekenpan"'
    assert left_out(ran.output) == {
        recorded_pages()[fixture].name: no_frying_pan
        for fixture in (
            "04-kieskeurig-tefal-trattoria-braadpan-24-cm-zwart-ind",
            "08-kieskeurig-tefal-renew-black-on-keramische-hapjespa",
            "10-kieskeurig-tefal-xl-force-wokpan-28-cm-zwart",
        )
    }
