"""Live check of the web search and the page fetch. Spends 3 credits; run it on purpose.

uv run python -m shopper.checks.check_sources "<product page URL>"

Three calls confirm the points docs/architecture/data_sources.md lists as "to confirm": the
length of a result's content at basic depth, whether `include_domains_mode="prefer"` is accepted
and changes the ranking, whether `country="netherlands"` is accepted, and whether a scrape with
markdown and raw HTML costs 1 credit and keeps the JSON-LD script blocks. Nothing is cached; the
Tavily credits are added to the daily ledger.
"""

import asyncio
import sys
from urllib.parse import urlparse

import httpx

from shopper.config import (
    NETHERLANDS,
    PREFERRED_TESTER_DOMAINS,
    InvalidSettingError,
    MissingSettingError,
    SearchPurpose,
    load_env,
)
from shopper.tools.http import RejectedKeyError, ServiceRequestError
from shopper.tools.product_page import page_request, product_page
from shopper.tools.results import FailureKind, SearchRequest, StoredResponse
from shopper.tools.search import search_outcome, search_request
from shopper.tools.sources import live_sources

USAGE = 'Usage: uv run python -m shopper.checks.check_sources "<product page URL>"'
SEARCH_QUERY = "best frying pan tested"


async def check(url: str) -> int:
    async with httpx.AsyncClient() as client:
        sources = live_sources(load_env(), client)
        # The category purpose: no country and the shops excluded, as the discovery search that
        # this check was written for in task 1.6.
        category = search_request(SEARCH_QUERY, SearchPurpose.CATEGORY)
        plain = category.model_copy(
            update={"parameters": {**category.parameters, "country": NETHERLANDS}}
        )
        preferred = plain.model_copy(
            update={
                "parameters": {
                    **plain.parameters,
                    "include_domains": PREFERRED_TESTER_DOMAINS,
                    "include_domains_mode": "prefer",
                }
            }
        )
        with_prefer = await sources.search(preferred)
        without = await sources.search(plain)
        page = await sources.fetch_page(page_request(url))
    _show_search(
        'With include_domains_mode="prefer" and country="netherlands"', preferred, with_prefer
    )
    _show_search('Without include_domains, with country="netherlands"', plain, without)
    _show_page(url, page)
    return 0


def _show_search(label: str, request: SearchRequest, fetched: StoredResponse | FailureKind) -> None:
    print(f"\n{label}:")
    if isinstance(fetched, FailureKind):
        print(f"  FAILED: {fetched}")
        return
    outcome = search_outcome(request, fetched, from_cache=False)
    lengths = sorted(len(result.content) for result in outcome.results)
    print(f"  credits {outcome.credits}, {len(outcome.results)} results")
    if lengths:
        print(f"  content length: shortest {lengths[0]}, longest {lengths[-1]}")
    for number, result in enumerate(outcome.results, start=1):
        domain = urlparse(result.url).netloc.removeprefix("www.")
        mark = "  (preferred)" if domain in PREFERRED_TESTER_DOMAINS else ""
        print(f"  {number}. {domain}{mark}")


def _show_page(url: str, fetched: StoredResponse | FailureKind) -> None:
    print("\nFirecrawl, markdown and raw HTML:")
    if isinstance(fetched, FailureKind):
        print(f"  FAILED: {fetched}")
        return
    data = fetched.response.get("data", {})
    metadata = data.get("metadata", {})
    page = product_page(page_request(url), fetched, from_cache=False)
    print(f"  creditsUsed reported: {metadata.get('creditsUsed', 'not reported')}")
    print(f"  page status {metadata.get('statusCode')}")
    print(f"  JSON-LD blocks kept: {'application/ld+json' in data.get('rawHtml', '')}")
    print(f"  name {page.name!r}, euro price {page.price}, other currency {page.other_currency}")


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print(USAGE)
        return 2
    try:
        return asyncio.run(check(arguments[0]))
    except (
        MissingSettingError,
        InvalidSettingError,
        RejectedKeyError,
        ServiceRequestError,
    ) as error:
        print(error)
        return 1


if __name__ == "__main__":
    # Piped output on Windows defaults to cp1252, which cannot encode all page text.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
