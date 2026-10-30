"""Step 6 of option research, evidence: each product option's lifespan, durability evidence and
recurring cost, from one evidence search and one read (option_evidence.md, "Evidence")."""

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path

import pytest
from tco_replies import Ran, Shop, page_url, pan_shop, reading, run

from fakes import finding
from shopper.config import MODEL_IDS
from shopper.graph.report import assemble
from shopper.llm import ChatError
from shopper.state import (
    DecisionFactor,
    FactorKind,
    ProductOption,
    RecurringCostState,
    Request,
    Scope,
    Source,
    SourceKind,
    StatedBy,
    TrailKind,
    TypicalLifespan,
    WarrantyTerm,
)
from shopper.terminal.report_text import option_lines

TEST_SITE = "https://www.example-tests.org/alpha-cheapo-review"
REVIEW = {
    "url": TEST_SITE,
    "title": "Alpha Cheapo frying pan review",
    "content": (
        "We tested the Alpha Cheapo for a year. In our tests the Alpha Cheapo lasts 6 to 8 years "
        "with daily use. The Alpha Cheapo comes with a lifetime warranty. Its PTFE coating "
        "wears with metal utensils. Hand wash only to keep the coating."
    ),
}
MAKER = {
    "url": "https://www.alpha.example/cheapo",
    "title": "Alpha Cheapo",
    "content": "The Alpha Cheapo lasts up to 20 years. Alpha pans last at least 10 years.",
}
GUIDE = {
    "url": "https://www.example-guide.org/pans",
    "title": "How long do frying pans last",
    "content": "Non-stick pans last 2 to 5 years. Pans with a two-year warranty are common.",
}
# A researched factor that is not a recurring cost: the category is known to have none.
HOB = DecisionFactor(
    id="researched-1",
    name="Hob compatibility",
    kind=FactorKind.COMPATIBILITY,
    why="Not every pan works on induction.",
    source=Source(kind=SourceKind.URL, reference="https://www.example-guide.org/hobs"),
)


def lifespan(result: int, quote: str, about: str = "product", by: str = "tester") -> dict:
    return {"result": result, "quote": quote, "stated_by": by, "about": about, "type": None}


def item(result: int, value: str, quote: str, by: str = "tester") -> dict:
    return {"result": result, "value": value, "quote": quote, "stated_by": by}


def pans(
    tmp_path: Path,
    alpha: str | Exception | None = None,
    *,
    found: Sequence[Mapping[str, str]] = (REVIEW, MAKER, GUIDE),
    factors: Sequence[DecisionFactor] = (HOB,),
) -> Ran:
    """Two pans; the Alpha Cheapo's evidence search finds `found`, and its read gives `alpha`."""
    return run(
        tmp_path,
        factors=factors,
        evidence={"Alpha Cheapo": found},
        evidence_reads={} if alpha is None else {"Alpha Cheapo": alpha},
    )


def option(ran: Ran, name: str) -> ProductOption:
    return next(each for each in ran.output.options if each.name == name)


def excluded(ran: Ran) -> dict[str, str | None]:
    return {
        entry.summary: entry.reason
        for entry in ran.output.trail
        if entry.kind is TrailKind.EXCLUDED
    }


def evidence_input(ran: Ran, name: str) -> str:
    return next(
        request.messages[-1]["content"]
        for request in ran.requests
        if f"Product: {name}\n" in request.messages[-1]["content"]
        and "Look for consumables" in request.messages[-1]["content"]
    )


# --- The search ---


@pytest.mark.parametrize(
    "name",
    [
        # Task 1.13: a product page's name with sizes, colours and selling words found nothing.
        "Alpha Cheapo Koekenpan 24 cm - Zwart - PFAS-vrij",
        # The brand alone before the first dash says nothing, so the next part, after the brand.
        "Alpha - Cheapo Koekenpan - Wit",
    ],
)
def test_the_evidence_search_names_the_product_by_the_first_part_of_its_name(
    tmp_path: Path, name: str
) -> None:
    ran = run(
        tmp_path,
        shop=pan_shop((name, "20")),
        evidence={"Alpha Cheapo Koekenpan": (REVIEW,)},
    )

    summaries = [entry.summary for entry in ran.output.trail]
    assert 'Searched "Alpha Cheapo Koekenpan durability lifespan warranty": 1 result' in summaries


# --- The lifespan ---


def test_with_no_evidence_each_option_gets_a_rough_estimate_by_the_model(tmp_path: Path) -> None:
    ran = pans(tmp_path)

    beta = option(ran, "Beta Steelo")
    assert beta.lifespan_years == Decimal(5)
    assert beta.lifespan_source == Source(
        kind=SourceKind.MODEL_ESTIMATE, reference=MODEL_IDS["medium"], label="rough estimate"
    )
    assert any(
        entry.summary == 'Estimated the lifespan of "Beta Steelo" at 5 years'
        and entry.reason == "no durability evidence was found"
        for entry in ran.output.trail
    )


def test_a_testers_range_for_the_product_gives_its_low_end_with_the_source(
    tmp_path: Path,
) -> None:
    alpha = option(
        pans(tmp_path, reading(lifespan(1, "the Alpha Cheapo lasts 6 to 8 years"))),
        "Alpha Cheapo",
    )

    assert alpha.lifespan_years == Decimal(6)
    assert alpha.lifespan_source == Source(
        kind=SourceKind.URL, reference=TEST_SITE, stated_by=StatedBy.TESTER
    )


def test_a_testers_lifespan_wins_over_a_makers_even_when_the_makers_is_lower(
    tmp_path: Path,
) -> None:
    alpha = option(
        pans(
            tmp_path,
            reading(
                lifespan(2, "Alpha pans last at least 10 years", about="line", by="manufacturer"),
                lifespan(1, "the Alpha Cheapo lasts 6 to 8 years"),
            ),
        ),
        "Alpha Cheapo",
    )

    assert alpha.lifespan_years == Decimal(6)


def test_a_line_lifespan_stands_on_the_brand_and_a_word_of_the_name(tmp_path: Path) -> None:
    found = (
        {
            "url": "https://www.example-tests.org/cheapo-line",
            "title": "The Alpha Cheapo range",
            "content": "Alpha's Cheapo pans last at least 10 years.",
        },
    )
    alpha = option(
        pans(
            tmp_path,
            reading(lifespan(1, "pans last at least 10 years", about="line")),
            found=found,
        ),
        "Alpha Cheapo",
    )

    assert alpha.lifespan_years == Decimal(10)


def test_a_makers_upper_bound_is_not_a_lifespan(tmp_path: Path) -> None:
    ran = pans(
        tmp_path,
        reading(lifespan(2, "lasts up to 20 years", by="manufacturer"), estimated_years=7),
    )

    assert option(ran, "Alpha Cheapo").lifespan_years == Decimal(7)
    assert excluded(ran)['Left out a lifespan for "Alpha Cheapo"'] == (
        "an upper bound is not a lifespan"
    )


def test_a_lifespan_from_a_result_that_does_not_name_the_product_is_left_out(
    tmp_path: Path,
) -> None:
    ran = pans(tmp_path, reading(lifespan(3, "Non-stick pans last 2 to 5 years")))

    assert excluded(ran)['Left out a lifespan for "Alpha Cheapo"'] == (
        "the passage of its quote does not name the product"
    )


def test_a_lifespan_of_the_type_is_shown_as_typical_and_bounds_the_estimate(
    tmp_path: Path,
) -> None:
    alpha = option(
        pans(
            tmp_path,
            reading(
                lifespan(3, "Non-stick pans last 2 to 5 years", about="type"), estimated_years=9
            ),
        ),
        "Alpha Cheapo",
    )

    typical = alpha.durability_evidence.typical_lifespan
    assert typical is not None
    assert typical.value == TypicalLifespan(low=Decimal(2), high=Decimal(5))
    assert alpha.lifespan_years == Decimal(5)
    assert alpha.lifespan_source is not None
    assert alpha.lifespan_source.kind is SourceKind.MODEL_ESTIMATE


def estimated(ran: Ran, name: str) -> str | None:
    return next(
        entry.reason
        for entry in ran.output.trail
        if entry.summary.startswith(f'Estimated the lifespan of "{name}"')
    )


def test_an_estimate_rests_only_on_the_evidence_that_passed_the_checks(tmp_path: Path) -> None:
    ran = pans(
        tmp_path,
        reading(
            lifespan(3, "Non-stick pans last 2 to 5 years"),
            wear_material=item(1, "PTFE coating", "Its PTFE coating wears"),
            rests_on=["lifespan", "wear_material"],
        ),
    )

    assert estimated(ran, "Alpha Cheapo") == "rests on: wear material"


def test_an_estimate_whose_evidence_all_failed_says_so(tmp_path: Path) -> None:
    ran = pans(
        tmp_path, reading(lifespan(3, "Non-stick pans last 2 to 5 years"), rests_on=["lifespan"])
    )

    assert estimated(ran, "Alpha Cheapo") == "none of the evidence it rests on passed the checks"


def test_an_estimate_that_names_no_evidence_beside_evidence_that_passed_says_so(
    tmp_path: Path,
) -> None:
    ran = pans(tmp_path, reading(wear_material=item(1, "PTFE coating", "Its PTFE coating wears")))

    assert estimated(ran, "Alpha Cheapo") == "the read named no evidence it rests on"


def test_a_type_quote_with_one_number_is_no_range_and_bounds_nothing(tmp_path: Path) -> None:
    found = (
        {
            "url": "https://www.example-guide.org/pans",
            "title": "How long do frying pans last",
            "content": "Steel pans last at least 10 years.",
        },
    )
    ran = pans(
        tmp_path,
        reading(lifespan(1, "Steel pans last at least 10 years", about="type"), estimated_years=6),
        found=found,
    )

    alpha = option(ran, "Alpha Cheapo")
    assert alpha.durability_evidence.typical_lifespan is None
    assert alpha.lifespan_years == Decimal(6)
    assert excluded(ran)['Left out a lifespan for "Alpha Cheapo"'] == (
        "a lifespan typical for the type is a range of years, and its quote states one number"
    )


def test_an_estimate_of_zero_years_is_asked_again(tmp_path: Path) -> None:
    ran = pans(tmp_path, reading(estimated_years=0))

    # The fake answers every evidence read of the Alpha Cheapo alike, so the retry fails too.
    assert option(ran, "Alpha Cheapo").lifespan_years is None


def test_an_estimate_is_kept_between_one_and_fifty_years(tmp_path: Path) -> None:
    assert option(pans(tmp_path, reading(estimated_years=80)), "Alpha Cheapo").lifespan_years == (
        Decimal(50)
    )


def test_a_read_that_fails_twice_leaves_the_lifespan_missing_with_the_reason(
    tmp_path: Path,
) -> None:
    ran = pans(tmp_path, ChatError("the service is down"))

    assert option(ran, "Alpha Cheapo").lifespan_years is None
    assert excluded(ran)['No lifespan for "Alpha Cheapo"'] == (
        "durability evidence could not be read"
    )
    assert ran.output.warnings == ()


# --- Durability evidence ---


def test_a_lifetime_warranty_and_the_text_items_are_kept_with_their_sources(
    tmp_path: Path,
) -> None:
    evidence = option(
        pans(
            tmp_path,
            reading(
                warranty={
                    "result": 1,
                    "quote": "comes with a lifetime warranty",
                    "stated_by": "tester",
                },
                wear_material=item(1, "PTFE coating", "Its PTFE coating wears"),
                care=item(1, "hand wash only", "Hand wash only ... keep the coating"),
            ),
        ),
        "Alpha Cheapo",
    ).durability_evidence

    assert evidence.warranty is not None
    assert evidence.warranty.value == WarrantyTerm(lifetime=True)
    assert evidence.wear_material is not None
    assert evidence.wear_material.value == "PTFE coating"
    assert evidence.care is not None
    assert evidence.care.source.reference == TEST_SITE


def test_a_two_year_warranty_is_the_legal_guarantee_and_goes_to_the_trail(
    tmp_path: Path,
) -> None:
    found = (
        {
            "url": "https://www.alpha.example/cheapo-warranty",
            "title": "Alpha Cheapo warranty",
            "content": "The Alpha Cheapo has a 2 year warranty.",
        },
    )
    ran = pans(
        tmp_path,
        reading(warranty={"result": 1, "quote": "a 2 year warranty", "stated_by": "manufacturer"}),
        found=found,
    )

    assert option(ran, "Alpha Cheapo").durability_evidence.warranty is None
    assert excluded(ran)['Left out a warranty for "Alpha Cheapo"'] == (
        "it is no longer than the EU legal guarantee, which says nothing about this product"
    )


def test_a_value_with_a_number_its_quote_does_not_hold_is_left_out(tmp_path: Path) -> None:
    ran = pans(tmp_path, reading(wear_material=item(1, "3 layer PTFE coating", "Its PTFE coating")))

    assert option(ran, "Alpha Cheapo").durability_evidence.wear_material is None
    assert excluded(ran)['Left out wear material for "Alpha Cheapo"'] == (
        "it holds a number that is not in its quote"
    )


def test_the_read_also_sees_the_options_own_product_page(tmp_path: Path) -> None:
    ran = pans(tmp_path)

    assert page_url("Alpha Cheapo") in evidence_input(ran, "Alpha Cheapo")
    assert "Look for consumables: no" in evidence_input(ran, "Alpha Cheapo")


# --- The recurring cost ---

KETTLE = {
    "url": "https://www.example-tests.org/alpha-cheapo-filter",
    "title": "Alpha Cheapo filters",
    "content": (
        "Replacement filters for the Alpha Cheapo cost $15 for a pack of 3. Replace the filter "
        "every 6 months. Also descaler. Elsewhere: CHF 20 a filter."
    ),
}
RECURRING = DecisionFactor(
    id="researched-1",
    name="Filters",
    kind=FactorKind.RECURRING_COST,
    why="Filters have to be bought again.",
    source=Source(kind=SourceKind.URL, reference="https://www.example-guide.org/filters"),
)


def consumable(amount: str, interval: str | None = "every 6 months", pack: str | None = None):
    return {
        "result": 1,
        "name": "replacement filter",
        "stated_by": "seller",
        "amount_quote": amount,
        "interval_quote": interval,
        "pack_count_quote": pack,
    }


def test_a_recurring_cost_in_dollars_is_converted_at_the_fixed_rate_per_piece(
    tmp_path: Path,
) -> None:
    ran = pans(
        tmp_path,
        reading(consumable=consumable("$15", pack="a pack of 3"), other_consumables=["descaler"]),
        found=(KETTLE,),
        factors=(RECURRING,),
    )

    alpha = option(ran, "Alpha Cheapo")
    # $15 at 1.1253 per euro is €13.33; a third of it twice a year.
    assert alpha.recurring_cost_per_year is not None
    assert alpha.recurring_cost_per_year.quantize(Decimal("0.01")) == Decimal("8.89")
    assert alpha.recurring_cost_state is RecurringCostState.FOUND
    assert alpha.recurring_cost_converted_from == "USD"
    assert alpha.other_consumables_left_out
    found = next(e for e in ran.output.trail if e.summary.startswith('Recurring cost of "Alpha'))
    assert found.reason is not None
    assert 'a bare "$" is read as US dollars' in found.reason
    assert "15 USD converted at 1.1253 per euro" in found.reason


def test_a_recurring_cost_in_another_currency_is_dropped_and_not_found(tmp_path: Path) -> None:
    ran = pans(
        tmp_path, reading(consumable=consumable("CHF 20")), found=(KETTLE,), factors=(RECURRING,)
    )

    assert option(ran, "Alpha Cheapo").recurring_cost_state is RecurringCostState.NOT_FOUND
    assert excluded(ran)['Left out a recurring cost for "Alpha Cheapo"'] == (
        "its amount is in a currency that is not converted"
    )


def test_a_pack_price_with_no_quoted_count_leaves_the_cost_not_found(tmp_path: Path) -> None:
    ran = pans(
        tmp_path,
        reading(consumable=consumable("$15 for a pack")),
        found=(KETTLE,),
        factors=(RECURRING,),
    )

    assert option(ran, "Alpha Cheapo").recurring_cost_per_year is None
    assert excluded(ran)['Left out a recurring cost for "Alpha Cheapo"'] == (
        "the price is for a pack with no quoted count"
    )


def test_without_a_recurring_cost_factor_no_cost_is_looked_for(tmp_path: Path) -> None:
    ran = pans(tmp_path, reading(consumable=consumable("$15")), found=(KETTLE,))

    alpha = option(ran, "Alpha Cheapo")
    assert alpha.recurring_cost_state is RecurringCostState.NOT_LOOKED_FOR
    assert alpha.recurring_cost_per_year is None


def test_with_no_researched_factor_a_recurring_cost_is_looked_for(tmp_path: Path) -> None:
    usage = DecisionFactor(id="usage-1", name="Usage frequency", kind=FactorKind.USAGE, why="x")

    ran = pans(tmp_path, factors=(usage,))

    assert option(ran, "Beta Steelo").recurring_cost_state is RecurringCostState.NOT_FOUND


# --- The linked product ---


def test_a_linked_product_with_no_category_gets_an_estimate_and_no_recurring_cost(
    tmp_path: Path,
) -> None:
    linked = ProductOption(id="option-link", name="Alpha Cheapo 28 cm", brand="Alpha")
    request = Request(original_text="https://shop.example.nl/a", scope=Scope.GENERAL)

    ran = run(tmp_path, request=request, linked=linked, factors=(RECURRING,))

    (product,) = ran.output.options
    assert product.lifespan_years == Decimal(5)
    assert product.recurring_cost_state is RecurringCostState.NOT_LOOKED_FOR


def test_a_linked_product_with_no_brand_gets_no_sourced_lifespan(tmp_path: Path) -> None:
    linked = ProductOption(id="option-link", name="Alpha Cheapo")
    request = Request(original_text="https://shop.example.nl/a", scope=Scope.GENERAL)

    ran = run(
        tmp_path,
        request=request,
        linked=linked,
        evidence={"Alpha Cheapo": (REVIEW,)},
        evidence_reads={
            "Alpha Cheapo": reading(lifespan(1, "the Alpha Cheapo lasts 6 to 8 years"))
        },
    )

    (product,) = ran.output.options
    assert product.lifespan_source is not None
    assert product.lifespan_source.kind is SourceKind.MODEL_ESTIMATE


# --- Full page text ---


def test_the_read_sees_a_results_full_text_and_a_quote_from_it_stands(tmp_path: Path) -> None:
    page = {
        **REVIEW,
        "content": "A short snippet about the Alpha Cheapo.",
        "raw_content": "The Alpha Cheapo review. After long testing, the Alpha Cheapo lasts "
        "at least 7 years.",
    }

    ran = pans(
        tmp_path, reading(lifespan(1, "the Alpha Cheapo lasts at least 7 years")), found=(page,)
    )

    assert "lasts at least 7 years" in evidence_input(ran, "Alpha Cheapo")
    assert option(ran, "Alpha Cheapo").lifespan_years == Decimal(7)


def test_a_reply_citing_result_zero_is_asked_again_with_the_error(tmp_path: Path) -> None:
    zero = json.loads(reading(wear_material=item(1, "PTFE coating", "Its PTFE coating wears")))
    zero["wear_material"]["result"] = 0

    ran = pans(
        tmp_path,
        json.dumps(zero),
        factors=(HOB,),
    )

    # The fake answers every evidence read of the Alpha Cheapo alike, so the retry fails too.
    assert option(ran, "Alpha Cheapo").lifespan_years is None
    assert (
        excluded(ran)['No lifespan for "Alpha Cheapo"'] == "durability evidence could not be read"
    )


# --- A recorded reply over a real result ---

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"
# A real levoit.com result, found by a search made by hand in task 1.8.3 and trimmed to the
# lines the read quotes, and the real model's reply over it (docs/findings/task_1.8.3.md).
LEVOIT_RESULT = FIXTURES / "tavily" / "air-purifier-evidence-levoit-filter.json"
LEVOIT_READ = FIXTURES / "nebius" / "evidence-levoit-core-300.json"


def test_a_recorded_read_of_a_real_dollar_price_is_converted_and_labelled(tmp_path: Path) -> None:
    (result,) = json.loads(LEVOIT_RESULT.read_text(encoding="utf-8"))["response"]["results"]
    recorded = json.loads(LEVOIT_READ.read_text(encoding="utf-8"))
    levoit = ProductOption(id="option-link", name="Levoit Core 300", brand="Levoit")
    request = Request(original_text="an air purifier", category="air purifier", scope=Scope.GENERAL)
    filters = RECURRING.model_copy(update={"name": "Replacement filters"})

    ran = run(
        tmp_path,
        request=request,
        linked=levoit,
        factors=(filters,),
        shop=Shop(finding({"air purifier kopen": ()}), {}),
        evidence={"Levoit Core 300": (result,)},
        evidence_reads={"Levoit Core 300": recorded["reply"]},
    )

    assert evidence_input(ran, "Levoit Core 300") == recorded["input"]
    (product,) = ran.output.options
    assert product.recurring_cost_converted_from == "USD"
    # $54.99 at 1.1253 per euro is €48.87, for a 2-pack replaced every 6 to 8 months.
    report = assemble(request, ran.output.trail, (), factors=(filters,), options=(product,))
    assert (
        "Recurring cost: €36.65 a year, Replacement Filter (levoit.com), converted from USD at a "
        "fixed rate, other consumables not counted"
    ) in option_lines(report)


# --- From the LCA review: what a lifespan or warranty must be about ---

GUIDE_PAGE = {
    "url": "https://www.shop.example.nl/buying-guide",
    "title": "Pan buying guide",
    "content": (
        "The Alpha Cheapo is our cheapest pan.\n"
        "Consider a Gamma saucepan: lasts at least 30 years with care."
    ),
}


def test_a_lifespan_counts_only_when_the_passage_of_its_quote_names_the_product(
    tmp_path: Path,
) -> None:
    ran = pans(tmp_path, reading(lifespan(1, "lasts at least 30 years")), found=(GUIDE_PAGE,))

    assert option(ran, "Alpha Cheapo").lifespan_source.kind is SourceKind.MODEL_ESTIMATE
    assert excluded(ran)['Left out a lifespan for "Alpha Cheapo"'] == (
        "the passage of its quote does not name the product"
    )


def test_a_line_is_not_named_by_a_word_for_a_material_or_a_tier(tmp_path: Path) -> None:
    nonstick = {
        "url": "https://www.example-tests.org/alpha",
        "title": "Alpha pans",
        "content": "Alpha nonstick pans last at least 10 years.",
    }
    linked = ProductOption(id="option-link", name="Alpha Nonstick Pro", brand="Alpha")

    ran = run(
        tmp_path,
        linked=linked,
        factors=(HOB,),
        evidence={"Alpha Nonstick Pro": (nonstick,)},
        evidence_reads={
            "Alpha Nonstick Pro": reading(lifespan(1, "pans last at least 10 years", about="line"))
        },
    )

    assert excluded(ran)['Left out a lifespan for "Alpha Nonstick Pro"'] == (
        "the passage of its quote does not name the line"
    )


def test_an_upper_bound_is_no_lifespan_whoever_states_it(tmp_path: Path) -> None:
    ran = pans(tmp_path, reading(lifespan(2, "lasts up to 20 years", by="tester")))

    assert excluded(ran)['Left out a lifespan for "Alpha Cheapo"'] == (
        "an upper bound is not a lifespan"
    )


def test_a_limited_lifetime_warranty_stays_limited(tmp_path: Path) -> None:
    limited = {
        **REVIEW,
        "content": REVIEW["content"] + " The Alpha Cheapo has a limited lifetime warranty.",
    }
    quote = {"result": 1, "quote": "a limited lifetime warranty", "stated_by": "manufacturer"}

    alpha = option(pans(tmp_path, reading(warranty=quote), found=(limited,)), "Alpha Cheapo")

    assert alpha.durability_evidence.warranty is not None
    assert alpha.durability_evidence.warranty.value == WarrantyTerm(lifetime=True, limited=True)


def test_a_typical_lifespan_keeps_the_type_its_quote_names(tmp_path: Path) -> None:
    typed = {
        **lifespan(3, "Non-stick pans last 2 to 5 years", about="type"),
        "type": "Non-stick pans",
    }
    alpha = option(pans(tmp_path, reading(typed)), "Alpha Cheapo")

    typical = alpha.durability_evidence.typical_lifespan
    assert typical is not None
    assert typical.value == TypicalLifespan(low=Decimal(2), high=Decimal(5), type="Non-stick pans")


def test_a_type_name_that_is_not_in_the_quote_is_dropped_and_the_range_kept(tmp_path: Path) -> None:
    typed = {**lifespan(3, "Non-stick pans last 2 to 5 years", about="type"), "type": "Woks"}
    alpha = option(pans(tmp_path, reading(typed)), "Alpha Cheapo")

    typical = alpha.durability_evidence.typical_lifespan
    assert typical is not None
    assert typical.value.type is None
