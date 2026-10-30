"""Step 7 of option research, findings: up to three short reports per product option of how it
held up for a tester or an owner, from one search and one read (option_evidence.md,
"Findings")."""

import asyncio
import json
import logging
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest
from tco_replies import PAN, Ran, pan_shop, run

from pages import offer, product_page
from shopper.agents.tco.checks import search_name
from shopper.config import EVIDENCE_TEMPLATE, FINDINGS_TEMPLATE, SHOP_DOMAINS, SearchPurpose
from shopper.llm import ChatError
from shopper.state import (
    Answer,
    AnswerStatus,
    Choice,
    DecisionFactor,
    FactorKind,
    Finding,
    FindingKind,
    FindingsState,
    ProductOption,
    Question,
    Source,
    SourceKind,
    StatedBy,
    TrailKind,
)
from shopper.tools.fixtures import fixture_search_service
from shopper.tools.results import FailureKind
from shopper.tools.search import search_request

FORUM = {
    "url": "https://www.reddit.com/r/cookware/comments/abc/alpha_cheapo",
    "title": "Alpha Cheapo after a year - r/cookware",
    "content": (
        "My Alpha Cheapo frying pan lost its non-stick coating after eight months of daily use. "
        "Rated 4.1/5 by me."
    ),
}
TEST = {
    "url": "https://www.example-tests.org/alpha-cheapo-review",
    "title": "Alpha Cheapo review",
    "content": (
        "We used the Alpha Cheapo every day for a year and the handle stayed tight. "
        "Our score: 8/10. Durability: 9/10. Many owners say the rivets loosen."
    ),
}
# A comparison site: the line of a rating names the product it is for.
COMPARED = {
    "url": "https://www.example-vergelijk.nl/koekenpannen",
    "title": "Koekenpannen vergeleken",
    "content": (
        "Alpha Cheapo: 4,5 van 5 sterren (1.234 beoordelingen). De Alpha Cheapo gaat jaren mee.\n"
        "Ook bekeken: Beta Steelo, 3,1 van 5 sterren (12 beoordelingen)."
    ),
}
GUIDE = {
    "url": "https://www.example-guide.org/pans",
    "title": "Frying pans compared",
    "content": "One pan in our kitchen warped after a month on high heat.",
}
COATING = "lost its non-stick coating after eight months of daily use"
HANDLE = "We used the Alpha Cheapo every day for a year and the handle stayed tight"


def report(
    result: int,
    quote: str,
    summary: str,
    by: str = "owner",
    rating_quote: str | None = None,
    on_shop_page: bool = False,
) -> dict[str, object]:
    return {
        "result": result,
        "on_shop_page": on_shop_page,
        "quote": quote,
        "summary": summary,
        "stated_by": by,
        "rating_quote": rating_quote,
    }


def reading(*findings: Mapping[str, object], gaps: Sequence[Mapping[str, str]] = ()) -> str:
    return json.dumps({"findings": list(findings), "gaps": list(gaps)})


OWNER = report(1, COATING, "One owner's pan lost its coating after eight months")
TESTED = report(2, HANDLE, "In one test the handle stayed tight after a year", by="tester")


def pans(
    tmp_path: Path,
    alpha: str | Exception | None = None,
    *,
    found: Sequence[Mapping[str, str]] | None = (FORUM, TEST, COMPARED, GUIDE),
    factors: Sequence[DecisionFactor] = (),
    evidence_reads: Mapping[str, str | Exception] | None = None,
) -> Ran:
    """Two pans; the Alpha Cheapo's findings search finds `found` (not recorded when None), and
    its findings read gives `alpha`."""
    return run(
        tmp_path,
        factors=factors,
        evidence_reads=evidence_reads,
        findings={} if found is None else {"Alpha Cheapo": found},
        findings_reads={} if alpha is None else {"Alpha Cheapo": alpha},
    )


def option(ran: Ran, name: str = "Alpha Cheapo") -> ProductOption:
    return next(each for each in ran.output.options if each.name == name)


def findings(ran: Ran, name: str = "Alpha Cheapo") -> tuple[Finding, ...]:
    return option(ran, name).durability_evidence.findings


def state(ran: Ran, name: str = "Alpha Cheapo") -> FindingsState:
    return option(ran, name).durability_evidence.findings_state


def left_out(ran: Ran) -> list[str | None]:
    """The reason of each finding and rating left out."""
    return [
        entry.reason
        for entry in ran.output.trail
        if entry.kind is TrailKind.EXCLUDED
        and entry.summary.startswith(("Left out a finding", "Left out the rating"))
    ]


def source(url: str, by: StatedBy) -> Source:
    return Source(kind=SourceKind.URL, reference=url, stated_by=by)


# --- What a finding holds ---


def test_a_finding_that_passes_holds_its_kind_summary_and_source(tmp_path: Path) -> None:
    ran = pans(tmp_path, reading(OWNER, TESTED))

    assert findings(ran) == (
        Finding(
            kind=FindingKind.OWNER_REPORT,
            summary="One owner's pan lost its coating after eight months",
            source=source(FORUM["url"], StatedBy.OWNER),
        ),
        Finding(
            kind=FindingKind.TEST,
            summary="In one test the handle stayed tight after a year",
            source=source(TEST["url"], StatedBy.TESTER),
        ),
    )
    assert state(ran) is FindingsState.FOUND


def test_no_quote_reaches_the_trail_and_each_is_logged_at_debug_level(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="shopper.findings"):
        ran = pans(tmp_path, reading(OWNER, TESTED, report(4, "warped after a month", "x")))

    trail = " ".join(f"{entry.summary} {entry.reason}" for entry in ran.output.trail)
    for quote in (COATING, HANDLE, "warped after a month"):
        assert quote not in trail
        assert any(quote in record.getMessage() for record in caplog.records)


def test_a_manufacturers_or_sellers_statement_is_no_finding(tmp_path: Path) -> None:
    ran = pans(tmp_path, reading(report(1, COATING, "One pan lost its coating", by="seller")))

    assert findings(ran) == ()
    assert state(ran) is FindingsState.NONE_FOUND
    assert left_out(ran) == ["a seller is speaking, so it is no test or owner report"]


def test_a_report_from_a_shops_page_is_no_finding(tmp_path: Path) -> None:
    ran = pans(tmp_path, reading(report(1, COATING, OWNER["summary"], on_shop_page=True)))

    assert findings(ran) == ()
    assert left_out(ran) == ["it comes from a shop's page, whose reviews are not used"]


# --- The checks ---


def test_a_summary_sharing_six_words_with_its_source_is_dropped(tmp_path: Path) -> None:
    copied = report(1, COATING, "One owner: lost its non-stick coating after eight months")

    ran = pans(tmp_path, reading(copied))

    assert findings(ran) == ()
    assert left_out(ran) == [
        "its summary copies six or more words in a row from the search results"
    ]


def test_a_generalised_owner_report_is_dropped(tmp_path: Path) -> None:
    general = report(1, COATING, "Many owners report the coating going within a year")

    ran = pans(tmp_path, reading(general))

    assert findings(ran) == ()
    assert left_out(ran) == ['its summary generalises ("many", "owners") where its quote does not']


def test_a_quote_not_in_its_result_or_in_two_parts_is_dropped(tmp_path: Path) -> None:
    ran = pans(
        tmp_path,
        reading(
            report(1, "the coating peeled in a week", "One owner's coating peeled"),
            report(2, "We used the Alpha Cheapo ... the handle stayed tight", "One test", "tester"),
        ),
    )

    assert findings(ran) == ()
    assert left_out(ran) == [
        "its quote is not in the search result",
        "its quote is in two parts",
    ]


def test_a_finding_whose_passage_names_no_line_is_dropped(tmp_path: Path) -> None:
    ran = pans(tmp_path, reading(report(4, "warped after a month on high heat", "One pan warped")))

    assert findings(ran) == ()
    assert left_out(ran) == ["the passage of its quote does not name the line"]


def test_a_passage_naming_only_the_line_is_kept_and_the_trail_says_so(tmp_path: Path) -> None:
    name = "Alpha Cheapo AC28"
    line = {
        "url": "https://www.example-forum.org/alpha",
        "title": "Alpha Cheapo pans",
        "content": "The coating on my Alpha Cheapo wore through in a year.",
    }
    summary = "One owner's coating wore through in a year"

    ran = run(
        tmp_path,
        shop=pan_shop((name, "20")),
        findings={name: (line,)},
        findings_reads={
            name: reading(report(1, "the coating on my Alpha Cheapo wore through", summary))
        },
    )

    assert [each.summary for each in findings(ran, name)] == [summary]
    assert any(
        entry.summary == f'Owner report for "{name}": {summary}'
        and entry.reason == "the passage of its quote names the line, not the product"
        for entry in ran.output.trail
    )


def test_one_finding_per_cited_result_and_at_most_three(tmp_path: Path) -> None:
    other = {
        "url": "https://www.example-forum.org/alpha-cheapo",
        "title": "Alpha Cheapo owners",
        "content": "My Alpha Cheapo handle snapped after two years.",
    }
    third = {
        "url": "https://www.example-forum.org/alpha-cheapo-2",
        "title": "Alpha Cheapo, five years on",
        "content": "My Alpha Cheapo is five years old and still flat.",
    }
    ran = pans(
        tmp_path,
        reading(
            OWNER,
            report(1, "Rated 4.1/5 by me", "One owner rated it"),
            TESTED,
            report(
                3,
                "My Alpha Cheapo handle snapped after two years",
                "One handle broke after two years",
            ),
            report(4, "My Alpha Cheapo is five years old and still flat", "One pan is still flat"),
        ),
        found=(FORUM, TEST, other, third),
    )

    assert len(findings(ran)) == 3
    assert left_out(ran) == [
        "an earlier finding cites the same search result",
        "at most 3 findings are kept",
    ]


# --- The rating ---


def test_a_tests_rating_needs_no_review_count(tmp_path: Path) -> None:
    rated = report(2, HANDLE, "In one test the handle stayed tight", "tester", "Our score: 8/10")

    ran = pans(tmp_path, reading(rated))

    (kept,) = findings(ran)
    assert (kept.rating, kept.review_count) == ("8/10", None)


def test_an_owners_rating_is_kept_with_its_review_count(tmp_path: Path) -> None:
    rated = report(
        3,
        "De Alpha Cheapo gaat jaren mee",
        "One owner's pan lasted for years",
        rating_quote="Alpha Cheapo: 4,5 van 5 sterren (1.234 beoordelingen)",
    )

    ran = pans(tmp_path, reading(rated))

    (kept,) = findings(ran)
    assert (kept.rating, kept.review_count) == ("4,5 van 5", 1234)


def test_an_owner_rating_with_no_review_count_is_dropped_and_the_finding_kept(
    tmp_path: Path,
) -> None:
    rated = report(
        1,
        COATING,
        "One owner's pan lost its coating after eight months",
        rating_quote="Rated 4.1/5 by me",
    )

    ran = pans(tmp_path, reading(rated))

    (kept,) = findings(ran)
    assert (kept.rating, kept.review_count) == (None, None)
    assert left_out(ran) == ["an owner's rating is kept only with its number of reviews"]


@pytest.mark.parametrize(
    ("rating_quote", "reason"),
    [
        (
            "Ook bekeken: Beta Steelo, 3,1 van 5 sterren (12 beoordelingen)",
            "it is for another product",
        ),
        ("gaat jaren mee", "it states no value on a scale"),
        (
            "Alpha Cheapo: 4,5 van 5 sterren",
            "an owner's rating is kept only with its number of reviews",
        ),
        ("4,5 van 5 sterren (1.234 reviews)", "its quote is not in the search result"),
    ],
)
def test_a_rating_that_fails_its_own_check_is_dropped(
    tmp_path: Path, rating_quote: str, reason: str
) -> None:
    rated = report(
        3,
        "De Alpha Cheapo gaat jaren mee",
        "One owner's pan lasted for years",
        rating_quote=rating_quote,
    )

    ran = pans(tmp_path, reading(rated))

    (kept,) = findings(ran)
    assert kept.rating is None
    assert left_out(ran) == [reason]


def test_a_score_for_one_aspect_is_no_overall_rating(tmp_path: Path) -> None:
    rated = report(2, HANDLE, TESTED["summary"], "tester", "Durability: 9/10")

    ran = pans(tmp_path, reading(rated))

    (kept,) = findings(ran)
    assert kept.rating is None
    assert left_out(ran) == ["it scores durability, not the product as a whole"]


# --- The findings state ---


def test_a_search_with_no_results_is_none_found_with_no_read(tmp_path: Path) -> None:
    ran = pans(tmp_path, found=())

    assert state(ran) is FindingsState.NONE_FOUND
    assert not any(
        "Product: Alpha Cheapo\nBrand: Alpha\nProduct category: frying pan\n\nSearch results"
        in request.messages[-1]["content"]
        for request in ran.requests
    )


def test_a_search_the_fixtures_did_not_record_is_not_searched(tmp_path: Path) -> None:
    ran = pans(tmp_path, found=None)

    assert state(ran) is FindingsState.NOT_SEARCHED
    assert state(ran, "Beta Steelo") is FindingsState.NOT_SEARCHED


def test_a_read_that_fails_twice_is_not_searched(tmp_path: Path) -> None:
    ran = pans(tmp_path, ChatError("down"))

    assert state(ran) is FindingsState.NOT_SEARCHED
    assert any(
        entry.summary == 'Could not read the owner and tester reports for "Alpha Cheapo"'
        for entry in ran.output.trail
    )


def test_a_read_that_keeps_none_is_none_found(tmp_path: Path) -> None:
    assert state(pans(tmp_path, reading())) is FindingsState.NONE_FOUND


def test_a_linked_product_with_no_brand_is_not_searched(tmp_path: Path) -> None:
    linked = ProductOption(id="option-linked", name="Unbranded pan")

    ran = run(tmp_path, request=PAN.model_copy(update={"category": None}), linked=linked)

    assert ran.output.options[0].durability_evidence.findings_state is FindingsState.NOT_SEARCHED
    assert any(
        entry.summary == 'Did not look up owner and tester reports for "Unbranded pan"'
        for entry in ran.output.trail
    )


def test_a_listed_product_whose_page_names_no_brand_is_not_searched_and_says_why(
    tmp_path: Path,
) -> None:
    # The office chairs of task 1.10's live run were listed with no brand; no link was pasted.
    shop = pan_shop(("Alpha Cheapo", "20"))
    url = next(url for url in shop.pages if "/p/" in url)
    pages = {**shop.pages, url: product_page(url, "Alpha Cheapo", None, offer("20"))}

    ran = run(tmp_path, shop=shop._replace(pages=pages))

    assert {
        (entry.summary, entry.reason)
        for entry in ran.output.trail
        if entry.summary.startswith(("Did not look up", "No sourced lifespan"))
    } == {
        (
            'Did not look up owner and tester reports for "Alpha Cheapo"',
            "its product page names no brand, so no report can be checked to name it",
        ),
        (
            'No sourced lifespan, warranty or recurring cost for "Alpha Cheapo"',
            "its product page names no brand, so no result can be checked to name it",
        ),
    }


# --- Merged with the evidence ---


def test_findings_are_merged_with_the_evidence_and_neither_overwrites_the_other(
    tmp_path: Path,
) -> None:
    evidence = json.dumps(
        {
            "lifespans": [],
            "warranty": None,
            "repairability": None,
            "wear_material": None,
            "care": None,
            "consumable": None,
            "other_consumables": [],
            "estimated_years": 4,
            "estimate_rests_on": [],
            "fits": [],
            "gaps": [],
        }
    )

    ran = pans(tmp_path, reading(OWNER), evidence_reads={"Alpha Cheapo": evidence})

    assert option(ran).lifespan_years == 4
    assert len(findings(ran)) == 1


def test_an_option_the_evidence_removes_loses_its_findings_and_their_trail(
    tmp_path: Path,
) -> None:
    hob = DecisionFactor(
        id="researched-1",
        name="Hob compatibility",
        kind=FactorKind.COMPATIBILITY,
        why="Not every pan works on induction.",
        source=Source(kind=SourceKind.URL, reference="https://www.example-guide.org/hobs"),
    )
    question = Question(
        id="question-researched-1",
        factor_id=hob.id,
        text="Which hob do you cook on?",
        reason="Some pans only work on some hobs.",
        choices=(Choice(id="choice-1", text="Induction"), Choice(id="choice-2", text="Gas")),
    )
    induction = Answer(factor_id=hob.id, status=AnswerStatus.CHOSEN, choice_id="choice-1")
    evidence_found = {
        "url": "https://www.example-tests.org/alpha",
        "title": "Alpha Cheapo",
        "content": "The Alpha Cheapo does not work on induction.",
    }
    fails = json.dumps(
        {
            "lifespans": [],
            "warranty": None,
            "repairability": None,
            "wear_material": None,
            "care": None,
            "consumable": None,
            "other_consumables": [],
            "estimated_years": 4,
            "estimate_rests_on": [],
            "fits": [
                {
                    "factor": 1,
                    "fit": "fails",
                    "value": "not for induction",
                    "result": 1,
                    "quote": "The Alpha Cheapo does not work on induction",
                    "stated_by": "tester",
                }
            ],
            "gaps": [],
        }
    )
    answered = run(
        tmp_path,
        factors=(hob,),
        questions=(question,),
        answers=(induction,),
        evidence={"Alpha Cheapo": (evidence_found,)},
        evidence_reads={"Alpha Cheapo": fails},
        findings={"Alpha Cheapo": (FORUM,)},
        findings_reads={"Alpha Cheapo": reading(OWNER)},
    )

    assert [each.name for each in answered.output.options] == ["Beta Steelo"]
    assert not any("Owner report for" in entry.summary for entry in answered.output.trail)
    assert not any(
        FINDINGS_TEMPLATE.format(product="Alpha Cheapo") in entry.summary
        for entry in answered.output.trail
    )


# --- The search ---


def test_the_search_is_the_template_filled_with_the_name_and_excludes_shops() -> None:
    request = search_request(
        FINDINGS_TEMPLATE.format(product="Alpha Cheapo"), SearchPurpose.FINDINGS
    )

    assert "Alpha Cheapo" in request.search_query
    assert set(SHOP_DOMAINS) <= set(request.parameters["exclude_domains"])
    assert "reddit.com" not in request.parameters["exclude_domains"]
    assert "country" not in request.parameters


# --- The recorded evidence and findings searches ---

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"
# The options the three tuned categories show with the fixture twin (tests/test_cli.py,
# "OPTIONS"), with their brands: their names come from the recorded product pages. The evidence
# search names each by its search name (task 1.15), the findings search by its whole name.
TUNED_OPTIONS = (
    ("GreenChef Diamond Inductie Koekenpan - Ø24 cm - Zwart - PFAS-vrij", "GreenChef"),
    ("de Buyer Mineral B Element Koekenpan - Ø 26 cm", "de Buyer"),
    ("WMF - Profi Resist - Koekenpan - Roestvrij Staal", "WMF"),
    (
        "Midea - Roestvrijstalen waterkoker - Wit - 1,5 liter - 2200 W - Met temperatuurinstelling "
        "en veiligheidsfuncties",
        "Midea",
    ),
    ("Inventum HW817D Waterkoker - 1.7L - RVS/Zwart - 2200W - Met Warmhoudfunctie", "Inventum"),
    ("Severin WK 9342 Waterkoker - 1L - 2400W - Zwart/RVS", "Severin"),
    (
        "Compacte 4-in-1 multifunctionele schroevendraaier 12V POWXBOX001 – incl. batterij 12V en "
        "2.0Ah lader",
        "Powerplus",
    ),
    ("Bosch - EasyDrill 18V-38 - Accu-schroefboormachine - 18 V - 2.5 Ah Li-ion", "Bosch"),
    ("Power X-Change - Klopboor-/schroefmachine - Rood - Accu - 18V", "Einhell"),
)


@pytest.mark.parametrize(("name", "brand"), TUNED_OPTIONS)
@pytest.mark.parametrize(
    ("template", "purpose", "named_by"),
    [
        (EVIDENCE_TEMPLATE, SearchPurpose.EVIDENCE, search_name),
        (FINDINGS_TEMPLATE, SearchPurpose.FINDINGS, lambda name, _: name),
    ],
    ids=["evidence", "findings"],
)
def test_every_tuned_option_has_its_evidence_and_findings_searches_recorded(
    name: str,
    brand: str,
    template: str,
    purpose: SearchPurpose,
    named_by: Callable[[str, str], str],
) -> None:
    query = template.format(product=named_by(name, brand))
    request = search_request(query, purpose, follow_up=True)

    answer = asyncio.run(fixture_search_service(FIXTURES)(request))

    assert answer is not FailureKind.NOT_RECORDED
