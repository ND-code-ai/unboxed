"""Which candidates read become product options: the slots, the durability judgements that order
them, and the marks that put a candidate last (option_research.md, "Selection", "Durability
judgement")."""

from pathlib import Path
from typing import Any

from tco_replies import (
    BUDGET_PAN,
    PAN_TERM,
    Ran,
    Shop,
    at_kieskeurig,
    decided,
    kieskeurig_pans,
    left_out,
    names,
    run,
)

from fakes import judged, sold_as
from pages import OUT_OF_STOCK, offer, product_page
from shopper.llm import ChatTimeoutError
from shopper.state import ProductOption

CHEAP = "Cheapo Koekenpan 24 cm"
SOLID = "Solido Koekenpan 28 cm"
PLAIN = "Plaino Koekenpan 24 cm"
FANCY = "Fancy Koekenpan 28 cm"
# Listed in this order, every price €2.99 shipping included: three within €50, one over it.
FOUR_PANS = kieskeurig_pans(
    (CHEAP, "22.99", None), (SOLID, "45.99", None), (PLAIN, "32.99", None), (FANCY, "99.99", None)
)
LONG = "multi-ply stainless steel, no coating to wear out"
MEDIUM = "stainless body, standard coating"
SHORT = "PTFE coating that wears"


def pans(tmp_path: Path, shop: Shop = FOUR_PANS, **given: Any) -> Ran:
    return run(tmp_path, shop=shop, request=BUDGET_PAN, local_term=PAN_TERM, **given)


def chose(ran: Ran) -> list[tuple[str, str | None]]:
    return [(summary, reason) for summary, reason in decided(ran.output) if "Chose " in summary]


# --- The slots ---


def test_the_cheapest_the_durable_pick_and_the_durable_pick_within_budget_become_the_options(
    tmp_path: Path,
) -> None:
    ran = pans(
        tmp_path, by_page=judged((2, "long", LONG), (3, "medium", MEDIUM), (1, "short", SHORT))
    )

    assert names(ran.output) == [CHEAP, SOLID, PLAIN]
    assert chose(ran) == [
        (f'Chose "{CHEAP}" as the cheapest', "€22.99 with its stated shipping"),
        (
            f'Chose "{SOLID}" as the durable pick',
            f"ordered by the model's judgement: long ({LONG}), not a sourced figure",
        ),
        # The one candidate left: no judgement decided it.
        (f'Chose "{PLAIN}" as the durable pick within budget', "€32.99 with its stated shipping"),
    ]


def test_a_product_over_the_budget_judged_long_by_name_is_read_first_and_may_be_the_durable_pick(
    tmp_path: Path,
) -> None:
    ran = pans(
        tmp_path,
        by_name=judged((4, "long", LONG), set_requested=False),
        by_page=judged((1, "long", LONG)),
    )

    assert ran.fetched[1] == at_kieskeurig(FANCY)
    assert names(ran.output)[1] == FANCY


def test_a_product_over_the_budget_is_no_durable_pick_unless_its_page_is_judged_long(
    tmp_path: Path,
) -> None:
    ran = pans(
        tmp_path,
        by_name=judged((4, "long", LONG), set_requested=False),
        by_page=judged((1, "medium", MEDIUM), (2, "medium", MEDIUM)),
    )

    assert FANCY not in names(ran.output)
    assert left_out(ran.output)[FANCY] == "it is over €50 and not judged long by the model"


def test_a_product_over_three_times_the_budget_is_not_read_even_judged_long(
    tmp_path: Path,
) -> None:
    shop = kieskeurig_pans((CHEAP, "22.99", None), (PLAIN, "32.99", None), (FANCY, "150.99", None))

    ran = pans(tmp_path, shop, by_name=judged((3, "long", LONG), set_requested=False))

    assert at_kieskeurig(FANCY) not in ran.fetched


def test_the_judgement_by_page_decides_and_not_the_judgement_by_name(tmp_path: Path) -> None:
    ran = pans(
        tmp_path,
        by_name=judged((2, "long", LONG), (3, "short", SHORT), set_requested=False),
        by_page=judged((2, "short", SHORT), (3, "long", LONG)),
    )

    assert names(ran.output)[1] == PLAIN


def test_ties_go_to_the_lower_price_with_its_shipping_then_the_earlier_listed(
    tmp_path: Path,
) -> None:
    # Both cost €35 to buy; the Plaino is listed first.
    shop = kieskeurig_pans(
        (CHEAP, "22.99", None),
        (
            PLAIN,
            "35",
            product_page(at_kieskeurig(PLAIN), PLAIN, "Plaino", offer("35", "5")),
        ),
        (SOLID, "35", product_page(at_kieskeurig(SOLID), SOLID, "Solido", offer("35", "0"))),
    )

    ran = pans(tmp_path, shop)

    assert names(ran.output) == [CHEAP, PLAIN, SOLID]


def test_when_no_judgement_tells_the_candidates_apart_the_slots_are_filled_by_price(
    tmp_path: Path,
) -> None:
    ran = pans(tmp_path, by_page=ChatTimeoutError("no answer"))

    assert names(ran.output) == [CHEAP, PLAIN, SOLID]
    assert (
        "Filled the slots by price",
        "the durability judgement did not tell the candidates apart",
    ) in decided(ran.output)
    assert "Could not judge the candidates by their product pages" in [
        entry.summary for entry in ran.output.trail
    ]


def test_a_pick_judged_above_the_others_is_decided_by_the_judgement_even_when_it_is_cheapest(
    tmp_path: Path,
) -> None:
    # The Plaino is both the cheaper of the two left and the one judged long.
    ran = pans(tmp_path, by_page=judged((2, "short", SHORT), (3, "long", LONG)))

    assert names(ran.output) == [CHEAP, PLAIN, SOLID]
    assert chose(ran)[1] == (
        f'Chose "{PLAIN}" as the durable pick',
        f"ordered by the model's judgement: long ({LONG}), not a sourced figure",
    )
    assert "Filled the slots by price" not in [summary for summary, _ in decided(ran.output)]


def test_a_judgement_whose_reason_holds_a_number_counts_as_unknown(tmp_path: Path) -> None:
    ran = pans(tmp_path, by_page=judged((2, "long", "lasts 30 years")))

    assert names(ran.output) == [CHEAP, PLAIN, SOLID]
    assert any(
        entry.reason == "the reason for its durability judgement holds a digit"
        for entry in ran.output.trail
    )


# --- The marks ---


def test_a_candidate_sold_incomplete_takes_a_slot_only_when_no_buyable_one_is_left(
    tmp_path: Path,
) -> None:
    bare = "Bare Koekenpan 24 cm zonder deksel"
    shop = kieskeurig_pans((bare, "15.99", None), (CHEAP, "22.99", None), (PLAIN, "32.99", None))

    ran = pans(tmp_path, shop, page_reads={bare: sold_as(bare, "incomplete", "zonder deksel")})

    assert names(ran.output) == [CHEAP, PLAIN, bare]
    assert (
        f'Chose "{bare}" as the durable pick within budget',
        "it is sold without a part it needs to work, and no buyable candidate was left",
    ) in chose(ran)


def test_an_out_of_stock_candidate_is_never_the_cheapest_while_a_buyable_one_is_left(
    tmp_path: Path,
) -> None:
    gone = "Gone Koekenpan 24 cm"
    shop = kieskeurig_pans(
        (
            gone,
            "12.99",
            product_page(
                at_kieskeurig(gone), gone, "Gone", offer("12.99", "2.99", availability=OUT_OF_STOCK)
            ),
        ),
        (CHEAP, "22.99", None),
    )

    ran = pans(tmp_path, shop)

    assert names(ran.output) == [CHEAP, gone]


def test_a_candidate_that_took_no_slot_says_what_decided_it(tmp_path: Path) -> None:
    # The bare Makitas of task 1.10's live drill run read "another candidate ranked above it".
    bare = "Bare Koekenpan 24 cm zonder deksel"
    shop = kieskeurig_pans(
        (bare, "15.99", None),
        (CHEAP, "22.99", None),
        (SOLID, "45.99", None),
        (PLAIN, "32.99", None),
        ("Fourth Koekenpan 24 cm", "39.99", None),
    )

    ran = pans(
        tmp_path,
        shop,
        page_reads={bare: sold_as(bare, "incomplete", "zonder deksel")},
        by_page=judged((3, "long", LONG), (4, "medium", MEDIUM)),
    )

    assert left_out(ran.output)[bare] == (
        "it is sold without a part it needs to work, and buyable candidates filled the slots"
    )
    assert left_out(ran.output)["Fourth Koekenpan 24 cm"] == (
        "each slot went to a cheaper candidate or to one the model judged to last longer"
    )


def test_an_out_of_stock_candidate_that_took_no_slot_says_so(tmp_path: Path) -> None:
    gone = "Gone Koekenpan 24 cm"
    shop = kieskeurig_pans(
        (
            gone,
            "12.99",
            product_page(
                at_kieskeurig(gone), gone, "Gone", offer("12.99", "2.99", availability=OUT_OF_STOCK)
            ),
        ),
        (CHEAP, "22.99", None),
        (SOLID, "45.99", None),
        (PLAIN, "32.99", None),
    )

    ran = pans(tmp_path, shop)

    assert left_out(ran.output)[gone] == (
        "no shop has it in stock, and buyable candidates filled the slots"
    )


# --- The linked product ---


def test_the_linked_product_holds_the_first_place_and_is_not_read_again_from_a_listing(
    tmp_path: Path,
) -> None:
    linked = ProductOption(id="option-link", name="Solido Koekenpan 28 cm", brand="Solido")

    ran = pans(tmp_path, linked=linked)

    assert names(ran.output)[0] == "Solido Koekenpan 28 cm"
    assert at_kieskeurig(SOLID) not in ran.fetched
    assert left_out(ran.output)[SOLID] == "it is the product at your link"
    assert len(ran.output.options) == 3
