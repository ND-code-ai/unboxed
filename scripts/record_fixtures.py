"""Record a search or a page live and write it as a trimmed fixture. Spends credits.

uv run python scripts/record_fixtures.py search <purpose> <fixture name> "<search query>"
uv run python scripts/record_fixtures.py page <fixture name> "<url>" [--with-text]

Add `--cached` to write what the live cache holds for it, at no credit (a live run of the day
stored it). `--with-text` keeps a page's text as far as the product-page read sees it, so a test
can replay that read (task 1.15: the braadpan, hapjespan and wok pages of task 1.12).

A search is sent as a model's search query, with its purpose's parameters from config.py, and
written to `tests/fixtures/tavily/<fixture name>.json` with every snippet kept and full page text
cut to the length the app reads. A page is read with Firecrawl and written to
`tests/fixtures/firecrawl/<fixture name>.json`, cut to its JSON-LD product data (shoppers' reviews
and pictures left out) and its text's first heading and stock lines, as the pages of task 1.12
were. Both are also stored in the live cache, under the key the app uses, so a live run reads
them for free. Task 1.13 recorded the drill's listing search with the English category and the
evidence and findings searches of the options with it (docs/findings/task_1.13.md).
"""

import asyncio
import json
import re
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

from shopper.config import (
    CACHE_FOLDER,
    FIXTURES_FOLDER,
    PAGE_TEXT_MAX_CHARACTERS,
    RAW_CONTENT_MAX_CHARACTERS,
    SearchPurpose,
    load_env,
)
from shopper.tools.cache import read_cached, search_key, write_cached
from shopper.tools.product_page import page_request, product_page
from shopper.tools.results import FailureKind, Service, StoredResponse
from shopper.tools.search import search_outcome, search_request
from shopper.tools.sources import live_sources

_JSON_LD = re.compile(
    r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
PRODUCT_DATA_TYPES = frozenset({"Product", "ProductGroup", "ItemList", "AggregateOffer", "Offer"})
STOCK_WORDS = ("voorraad", "leverbaar", "uitverkocht", "in stock", "beschikbaar")
# Shoppers' reviews and pictures are not product data; they are not committed.
DROPPED_KEYS = frozenset({"review", "image", "potentialAction"})
KEPT_METADATA = ("statusCode", "creditsUsed", "sourceURL", "url")


async def search(purpose: str, name: str, query: str, cached: bool) -> int:
    request = search_request(query, SearchPurpose(purpose), follow_up=True)
    key = search_key(request.search_query, request.parameters)
    if cached:
        fetched = _cached(Service.TAVILY, key)
    else:
        async with httpx.AsyncClient() as client:
            fetched = await live_sources(load_env(), client).search(request)
    if isinstance(fetched, FailureKind):
        print(f"FAILED: {fetched}")
        return 1
    stored = fetched.model_copy(update={"request": {**fetched.request, "purpose": request.purpose}})
    write_cached(CACHE_FOLDER / "live", key, stored)
    outcome = search_outcome(request, stored, from_cache=False)
    print(f"{outcome.credits} credits, {len(outcome.results)} results")
    for number, result in enumerate(outcome.results, start=1):
        print(f"[{number}] {result.url}\n    {result.title}")
    _write(FIXTURES_FOLDER / "tavily" / f"{name}.json", _trimmed_search(stored))
    return 0


async def page(name: str, url: str, cached: bool, with_text: bool) -> int:
    request = page_request(url)
    if cached:
        fetched = _cached(Service.FIRECRAWL, request.url)
    else:
        async with httpx.AsyncClient() as client:
            fetched = await live_sources(load_env(), client).fetch_page(request)
    if isinstance(fetched, FailureKind):
        print(f"FAILED: {fetched}")
        return 1
    read = product_page(request, fetched, from_cache=False)
    if read.failure is None:
        write_cached(CACHE_FOLDER / "live", request.url, fetched)
    print(f"{read.name!r}: {len(read.offers)} offers, {len(read.listed)} listed, {read.failure}")
    _write(FIXTURES_FOLDER / "firecrawl" / f"{name}.json", _trimmed_page(fetched, with_text))
    return 0


def _cached(service: Service, key: str) -> StoredResponse | FailureKind:
    """What the live cache holds under the key, whatever its age; `not_recorded` when nothing."""
    stored = read_cached(CACHE_FOLDER / "live", service, key, None, datetime.now(UTC))
    return FailureKind.NOT_RECORDED if stored is None else stored


def _trimmed_search(stored: StoredResponse) -> StoredResponse:
    results = [
        {**result, "raw_content": result["raw_content"][:RAW_CONTENT_MAX_CHARACTERS]}
        if result.get("raw_content")
        else result
        for result in stored.response.get("results", ())
    ]
    return stored.model_copy(update={"response": {**stored.response, "results": results}})


def _trimmed_page(stored: StoredResponse, with_text: bool) -> StoredResponse:
    data = stored.response.get("data", {})
    blocks = [
        block
        for block in _blocks(data.get("rawHtml", ""))
        if any(node.get("@type") in PRODUCT_DATA_TYPES for node in _walk(block))
    ]
    scripts = "".join(
        '<script type="application/ld+json">'
        f"{json.dumps(_without(block, DROPPED_KEYS), ensure_ascii=False)}</script>"
        for block in blocks
    )
    markdown = data.get("markdown", "")
    lines = markdown.splitlines()
    heading = next((line for line in lines if line.startswith("# ")), "")
    stock = [line for line in lines if any(word in line.lower() for word in STOCK_WORDS)]
    text = markdown[:PAGE_TEXT_MAX_CHARACTERS] if with_text else "\n".join([heading, *stock[:5]])
    trimmed = {
        **data,
        "rawHtml": f"<html><head>{scripts}</head></html>",
        "markdown": text.strip(),
        "metadata": {
            key: value for key, value in data.get("metadata", {}).items() if key in KEPT_METADATA
        },
    }
    return stored.model_copy(update={"response": {**stored.response, "data": trimmed}})


def _blocks(raw_html: str) -> list[Any]:
    found = []
    for block in _JSON_LD.findall(raw_html):
        try:
            found.append(json.loads(block))
        except json.JSONDecodeError:
            continue
    return found


def _walk(value: Any) -> Iterator[dict[str, Any]]:
    """Every object inside a JSON value, depth first."""
    if isinstance(value, dict):
        yield value
        for each in value.values():
            yield from _walk(each)
    elif isinstance(value, list):
        for each in value:
            yield from _walk(each)


def _without(value: Any, keys: frozenset[str]) -> Any:
    """The JSON value with these keys left out at every depth."""
    if isinstance(value, dict):
        return {key: _without(each, keys) for key, each in value.items() if key not in keys}
    if isinstance(value, list):
        return [_without(each, keys) for each in value]
    return value


def _write(path: Any, stored: StoredResponse) -> None:
    path.write_text(stored.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path}")


def main(arguments: list[str]) -> int:
    flags = {each for each in arguments if each.startswith("--")}
    cached = "--cached" in flags
    match [each for each in arguments if each not in flags]:
        case ["search", purpose, name, query]:
            return asyncio.run(search(purpose, name, query, cached))
        case ["page", name, url]:
            return asyncio.run(page(name, url, cached, "--with-text" in flags))
    print(__doc__)
    return 2


if __name__ == "__main__":
    # Piped output on Windows defaults to cp1252, which cannot encode all page text.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
