"""Step 1 of option research: the candidates the comparison sites' listing pages name.

One listing search with the local category term, restricted to the comparison sites; per site,
the first result that is a listing page of the whole category and holds a non-empty `ItemList`;
the two lists merged alternately, a product named on both kept once. When the term stands in too
few listed names, the search runs once more with the English category. Rules:
docs/architecture/option_research.md ("Listing pages") and docs/findings/task_1.12.md
("Decided", items 1 and 2).
"""

import asyncio
from collections.abc import Sequence
from itertools import zip_longest
from typing import NamedTuple

from shopper.agents.tco.checks import names_kind, same_product
from shopper.agents.tco.models import Candidate, ListedCandidates
from shopper.agents.tco.trail import counted, entry, searched
from shopper.config import (
    COMPARISON_SITES,
    LISTING_TEMPLATE,
    MIN_NAMES_WITH_TERM,
    TCO_FETCH_LIMIT,
    ComparisonSite,
    SearchPurpose,
)
from shopper.state import Source, SourceKind, TrailEntry, TrailKind
from shopper.tools.results import FailureKind, ListedProduct, PageFetch, ProductPage, WebSearch
from shopper.tools.search import on_domain


class ListingSearch(NamedTuple):
    """One listing search and its listing pages: the products they name, merged, the pages read,
    the trail, whether the search failed or every page fetch did, and every listed name before
    the merge."""

    products: tuple[ListedProduct, ...]
    pages: tuple[ProductPage, ...]
    trail: tuple[TrailEntry, ...]
    failed: bool
    names: tuple[str, ...] = ()


async def listed_candidates(
    category: str, local_term: str | None, search: WebSearch, fetch: PageFetch
) -> ListedCandidates:
    """The candidates the listing pages name, in listing order.

    The listing search holds the local term a model wrote, so it is searched as a model's query.
    With no term, or one that stands in fewer than three listed names, the English category is
    searched instead and the name check on the product pages is skipped; when that search names
    no product, the term's candidates stand.
    """
    first = None
    reason = "category research found no local category term"
    # The words a product name holds for the kind of product, which name no product.
    kind_words = f"{category} {local_term or ''}"
    if local_term is not None:
        first = await _listing_search(local_term, kind_words, search, fetch, ())
        with_term = sum(names_kind(local_term, name) for name in first.names)
        if with_term >= MIN_NAMES_WITH_TERM:
            return ListedCandidates(
                _candidates(first), local_term, first.trail, len(first.pages), first.failed
            )
        reason = (
            f'"{local_term}" stands in {counted(with_term, "listed product name")}, '
            f"fewer than {MIN_NAMES_WITH_TERM}"
        )
    read = () if first is None else first.pages
    lead = () if first is None else first.trail
    english = await _listing_search(category, kind_words, search, fetch, read)
    decided = entry(
        TrailKind.DECIDED,
        f'Searched the listing pages with the category "{category}"; product names are not '
        "checked for the local term",
        reason=reason,
    )
    pages_read = len(read) + len(english.pages)
    if first is not None and first.products and not english.products:
        stands = entry(
            TrailKind.DECIDED,
            "The candidates of the first listing search stand",
            reason=f'the search with "{category}" named no product',
        )
        trail = (*lead, decided, *english.trail, stands)
        return ListedCandidates(_candidates(first), None, trail, pages_read, failed=False)
    failed = english.failed and (first is None or first.failed)
    trail = (*lead, decided, *english.trail)
    return ListedCandidates(_candidates(english), None, trail, pages_read, failed)


def _candidates(found: ListingSearch) -> tuple[Candidate, ...]:
    return tuple(
        Candidate(number, product) for number, product in enumerate(found.products, start=1)
    )


async def _listing_search(
    term: str,
    kind_words: str,
    search: WebSearch,
    fetch: PageFetch,
    read: Sequence[ProductPage],
) -> ListingSearch:
    """One listing search and the listing page of each comparison site in its results; a page
    read before is not read again. Each site may try an equal share of the pages an analysis
    reads, those read before taken off. `kind_words` name the kind of product, not one product."""
    outcome = await search(
        LISTING_TEMPLATE.format(term=term), SearchPurpose.LISTING_PAGES, follow_up=True
    )
    searched_entry = searched(outcome)
    if outcome.failure is not None:
        failed = outcome.failure is not FailureKind.NOT_FOUND
        return ListingSearch((), (), (searched_entry,), failed=failed)
    listings = _listing_urls([result.url for result in outcome.results])
    urls = [url for _, url in listings]
    share = (TCO_FETCH_LIMIT - len(read)) // len(COMPARISON_SITES)
    by_site = await asyncio.gather(
        *(
            _listing_page([url for on, url in listings if on == domain][:share], fetch, read)
            for domain in COMPARISON_SITES
        )
    )
    found = sorted(
        (each for each in by_site if each.page is not None),
        key=lambda each: urls.index(each.page.url) if each.page is not None else 0,
    )
    lists = [each.page.listed for each in found if each.page is not None]
    pages = tuple(page for each in by_site for page in each.read)
    products, merged = _merged(lists, kind_words)
    trail = (
        searched_entry,
        *(entry_ for each in by_site for entry_ in each.trail),
        *merged,
    )
    names = tuple(product.name for listed in lists for product in listed)
    every_fetch_failed = bool(pages) and all(page.failure is not None for page in pages)
    return ListingSearch(products, pages, trail, failed=every_fetch_failed, names=names)


class SitePage(NamedTuple):
    """A comparison site's listing page, missing when none of its results gave one, the pages
    read for it and the trail."""

    page: ProductPage | None
    read: tuple[ProductPage, ...]
    trail: tuple[TrailEntry, ...]


def _listing_urls(urls: Sequence[str]) -> list[tuple[str, str]]:
    """The results that may be a listing page of a comparison site's whole category, each with
    its site, in result order: a filtered list stands for the listing of its category when the
    site's URLs name it (`category_cut`), and any other that is no listing page is left out."""
    listings = (
        (domain, _category_listing_url(url, site))
        for url in urls
        for domain, site in COMPARISON_SITES.items()
        if on_domain(url, (domain,))
    )
    return list(dict.fromkeys((domain, url) for domain, url in listings if url is not None))


def _category_listing_url(url: str, site: ComparisonSite) -> str | None:
    """The URL itself when it may be a listing page of the whole category, the listing of its
    category when it is a filtered list the site's URLs name, else nothing."""
    if not any(part in url for part in site.not_listing):
        return url
    cut = next((url.index(part) for part in site.category_cut if part in url), None)
    return None if cut is None else url[:cut]


async def _listing_page(
    urls: Sequence[str], fetch: PageFetch, read: Sequence[ProductPage]
) -> SitePage:
    """The first of the site's results whose page holds a non-empty `ItemList`."""
    already = {page.url: page for page in read}
    fetched: list[ProductPage] = []
    trail: list[TrailEntry] = []
    for url in urls:
        page = already.get(url) or await fetch(url)
        if url not in already:
            fetched.append(page)
        if page.failure is None and page.listed:
            listed = entry(
                TrailKind.FOUND,
                f"Read the listing page: {counted(len(page.listed), 'product')}",
                source=Source(kind=SourceKind.URL, reference=url),
            )
            return SitePage(page, tuple(fetched), (*trail, listed))
        trail.append(_no_listing_page(page))
    return SitePage(None, tuple(fetched), tuple(trail))


def _no_listing_page(page: ProductPage) -> TrailEntry:
    return entry(
        TrailKind.EXCLUDED,
        "Read no listing page",
        reason=str(page.failure) if page.failure is not None else "it lists no products",
        source=Source(kind=SourceKind.URL, reference=page.url),
    )


def _merged(
    lists: Sequence[Sequence[ListedProduct]], kind_words: str
) -> tuple[tuple[ListedProduct, ...], tuple[TrailEntry, ...]]:
    """The lists merged alternately, in the order their pages were found. A product that names
    the same product as one kept from another list is that product, and the first kept stands; a
    list names each of its products once."""
    kept: list[tuple[int, ListedProduct]] = []
    trail: list[TrailEntry] = []
    for row in zip_longest(*lists):
        for origin, product in enumerate(row):
            if product is None:
                continue
            same = next(
                (
                    other
                    for list_of, other in kept
                    if list_of != origin
                    and same_product(
                        product.name, other.name, product.brand or other.brand, kind_words
                    )
                ),
                None,
            )
            if same is None:
                kept.append((origin, product))
                continue
            trail.append(
                entry(
                    TrailKind.DECIDED,
                    f'Kept "{same.name}" once',
                    reason=f'"{product.name}" on another site names the same product',
                )
            )
    return tuple(product for _, product in kept), tuple(trail)
