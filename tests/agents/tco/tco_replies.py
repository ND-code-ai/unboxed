"""What the TCO analyzer's tests share: a shop to research (a listing search, its listing pages and
product pages, built in tests/pages.py), the model's replies written by hand, and running the agent
function on them. Rules: docs/architecture/option_research.md.
"""

import asyncio
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from fakes import (
    NOT_JUDGED_BY_NAME,
    NOT_JUDGED_BY_PAGE,
    Clock,
    fake_chat_with_reads,
    finding,
)
from pages import listed, listing_page, offer, product_page, results, serving
from shopper.agents.bundle import TcoOutput
from shopper.agents.tco.agent import research_options
from shopper.config import (
    EVIDENCE_TEMPLATE,
    FINDINGS_TEMPLATE,
    TCO_FETCH_LIMIT,
    TCO_SEARCH_LIMIT,
    SearchPurpose,
)
from shopper.llm import ChatRequest
from shopper.state import (
    Answer,
    DecisionFactor,
    ProductOption,
    Question,
    Request,
    Scope,
    TrailKind,
    WarningCode,
)
from shopper.tools.product_page import page_view
from shopper.tools.results import (
    FailureKind,
    PageService,
    SearchRequest,
    SearchService,
    StoredResponse,
)
from shopper.tools.search import search_view
from shopper.tools.sources import Sources

NOON = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
PAN = Request(original_text="a frying pan", category="frying pan", scope=Scope.TUNED)
PAN_LISTING = "https://www.beslist.nl/products/huis_tuin/koekenpannen"
PAN_SEARCH = "frying pan kopen"


class Shop(NamedTuple):
    """What a run researches: the search service behind the listing search, and the pages."""

    search: SearchService
    pages: Mapping[str, StoredResponse | FailureKind]


def page_url(name: str) -> str:
    return f"https://www.beslist.nl/p/{re.sub(r'[^a-z0-9]+', '-', name.lower())}/1"


def pan_shop(*pans: tuple[str, str], search_query: str = PAN_SEARCH) -> Shop:
    """One beslist.nl listing page of these pans, each at its price, and a product page per pan
    with one offer in stock and free shipping; a pan's brand is the first word of its name."""
    pages: dict[str, StoredResponse | FailureKind] = {
        PAN_LISTING: listing_page(
            PAN_LISTING, *(listed(name, page_url(name), price) for name, price in pans)
        ),
        **{
            page_url(name): product_page(page_url(name), name, name.split()[0], offer(price))
            for name, price in pans
        },
    }
    return Shop(finding({search_query: results(PAN_LISTING)}), pages)


TWO_PANS = (("Alpha Cheapo", "20"), ("Beta Steelo", "40"))
PAN_SHOP = pan_shop(*TWO_PANS)
BUDGET_PAN = Request(
    original_text="a frying pan, budget 50 euro",
    category="frying pan",
    scope=Scope.TUNED,
    budget=Decimal("50"),
)
PAN_TERM = "koekenpan"
KIESKEURIG_PANS = "https://www.kieskeurig.nl/pan/beste"


def at_kieskeurig(name: str) -> str:
    return f"https://www.kieskeurig.nl/pan/product/1-{re.sub(r'[^a-z0-9]+', '-', name.lower())}"


def kieskeurig_pans(*pans: tuple[str, str, StoredResponse | None]) -> Shop:
    """These pans on one kieskeurig.nl listing page, each at its listed price, with the product
    page given or else one in stock at that price, €2.99 shipping included in it. The search
    with the category finds the same page, for a run whose term stands in too few names."""
    pages: dict[str, StoredResponse | FailureKind] = {
        KIESKEURIG_PANS: listing_page(
            KIESKEURIG_PANS,
            *(listed(name, at_kieskeurig(name), price, name.split()[0]) for name, price, _ in pans),
        ),
        **{
            at_kieskeurig(name): page
            or product_page(at_kieskeurig(name), name, name.split()[0], offer(price, "2.99"))
            for name, price, page in pans
        },
    }
    found = results(KIESKEURIG_PANS)
    return Shop(finding({"koekenpan kopen": found, PAN_SEARCH: found}), pages)


# --- What the model writes, by hand ---


def reading(
    *lifespans: Mapping[str, object],
    warranty: Mapping[str, object] | None = None,
    repairability: Mapping[str, object] | None = None,
    wear_material: Mapping[str, object] | None = None,
    care: Mapping[str, object] | None = None,
    consumable: Mapping[str, object] | None = None,
    other_consumables: Sequence[str] = (),
    estimated_years: int = 5,
    rests_on: Sequence[str] = (),
    fits: Sequence[Mapping[str, object]] = (),
) -> str:
    return json.dumps(
        {
            "lifespans": list(lifespans),
            "warranty": warranty,
            "repairability": repairability,
            "wear_material": wear_material,
            "care": care,
            "consumable": consumable,
            "other_consumables": list(other_consumables),
            "estimated_years": estimated_years,
            "estimate_rests_on": list(rests_on),
            "fits": list(fits),
            "gaps": [],
        }
    )


# --- Running the agent ---


class Ran(NamedTuple):
    output: TcoOutput
    requests: list[ChatRequest]
    fetched: list[str]


def run(
    cache: Path,
    *,
    shop: Shop = PAN_SHOP,
    request: Request = PAN,
    local_term: str | None = None,
    linked: ProductOption | None = None,
    factors: Sequence[DecisionFactor] = (),
    questions: Sequence[Question] = (),
    answers: Sequence[Answer] = (),
    by_name: str | Exception = NOT_JUDGED_BY_NAME,
    by_page: str | Exception = NOT_JUDGED_BY_PAGE,
    page_reads: Mapping[str, str | Exception] | None = None,
    evidence_reads: Mapping[str, str | Exception] | None = None,
    evidence: Mapping[str, Sequence[Mapping[str, str]]] | None = None,
    findings_reads: Mapping[str, str | Exception] | None = None,
    findings: Mapping[str, Sequence[Mapping[str, str]]] | None = None,
    page_service: PageService | None = None,
) -> Ran:
    """The agent on the shop, its pages served by `page_service` when given. An evidence or a
    findings search finds `evidence` or `findings` by its product's name, and is not recorded
    otherwise; `fetched` holds every page asked of the shop's own service, in order."""
    chat, requests = fake_chat_with_reads(
        (),
        by_name=by_name,
        by_page=by_page,
        page_reads=page_reads,
        evidence_reads=evidence_reads,
        findings_reads=findings_reads,
    )
    fetched: list[str] = []
    sources = Sources(
        search=with_evidence(shop.search, evidence or {}, findings),
        fetch_page=page_service or serving(shop.pages, fetched),
        cache_folder=cache,
        clock=Clock(NOON),
    )
    output = asyncio.run(
        research_options(
            request,
            linked,
            local_term,
            factors,
            questions,
            answers,
            chat,
            search_view(sources, TCO_SEARCH_LIMIT),
            page_view(sources, TCO_FETCH_LIMIT),
        )
    )
    return Ran(output, requests, fetched)


def with_evidence(
    service: SearchService,
    evidence: Mapping[str, Sequence[Mapping[str, str]]],
    findings: Mapping[str, Sequence[Mapping[str, str]]] | None = None,
) -> SearchService:
    """The service, with these results for the evidence and the findings search of each product
    named, and `not_recorded` for any other, as the fixture twin answers a name a model wrote."""
    by_search_query = {
        **{EVIDENCE_TEMPLATE.format(product=name): results for name, results in evidence.items()},
        **{
            FINDINGS_TEMPLATE.format(product=name): results
            for name, results in (findings or {}).items()
        },
    }
    found = finding(by_search_query)

    async def search(request: SearchRequest) -> StoredResponse | FailureKind:
        if request.purpose not in (SearchPurpose.EVIDENCE, SearchPurpose.FINDINGS):
            return await service(request)
        if request.search_query in by_search_query:
            return await found(request)
        return FailureKind.NOT_RECORDED

    return search


def option(output: TcoOutput, name: str) -> ProductOption:
    return next(each for each in output.options if each.name == name)


def names(output: TcoOutput) -> list[str]:
    return [each.name for each in output.options]


def prices(output: TcoOutput) -> list[tuple[str, Decimal | None]]:
    return [(each.name, each.price) for each in output.options]


def left_out(output: TcoOutput) -> dict[str, str | None]:
    """Each candidate left out, by the name its trail entry gives, with the reason."""
    return {
        entry.summary.removeprefix("Left out ").strip('"'): entry.reason
        for entry in output.trail
        if entry.kind is TrailKind.EXCLUDED and entry.summary.startswith("Left out ")
    }


def decided(output: TcoOutput) -> list[tuple[str, str | None]]:
    return [
        (entry.summary, entry.reason) for entry in output.trail if entry.kind is TrailKind.DECIDED
    ]


def warnings(output: TcoOutput) -> list[tuple[WarningCode, str]]:
    return [(warning.code, warning.message) for warning in output.warnings]
