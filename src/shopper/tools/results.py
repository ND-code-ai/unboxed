"""What the web search and the page fetch return, the format they store, and their interfaces.

A tool returns a result that says what went wrong; it does not raise through the agent. It
raises only for a programmer error: a request the service rejects as malformed, a missing or
rejected key, or a fixture that does not exist. Rules: docs/architecture/data_sources.md.
"""

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from shopper.config import SearchPurpose
from shopper.state import DomainModel


class FailureKind(StrEnum):
    """What went wrong; the table in data_sources.md ("Failure kinds") says when each applies."""

    NOT_FOUND = "not_found"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    TIMED_OUT = "timed_out"
    CREDITS_EXHAUSTED = "credits_exhausted"
    DAILY_LIMIT_REACHED = "daily_limit_reached"
    LIMIT_REACHED = "limit_reached"
    NOT_RECORDED = "not_recorded"
    UNAVAILABLE = "unavailable"


class Service(StrEnum):
    TAVILY = "tavily"
    FIRECRAWL = "firecrawl"


class StoredResponse(DomainModel):
    """One stored format for a cached response and a fixture.

    `request` holds the request as readable fields: the search query, the purpose and the
    parameters, or the URL and the parameters. A live response becomes a fixture by copying and
    trimming its file.
    """

    service: Service
    request: Mapping[str, Any]
    retrieved_at: datetime
    response: Mapping[str, Any]


class SearchRequest(DomainModel):
    """A search as it is sent: the search query, its purpose and every other parameter.

    `follow_up` marks a search query a model wrote; it is not sent to the service.
    """

    search_query: str
    purpose: SearchPurpose
    parameters: Mapping[str, Any]
    follow_up: bool = False


class PageRequest(DomainModel):
    url: str
    parameters: Mapping[str, Any]


class SearchResult(DomainModel):
    """One web page a search returned; `content` is the snippet the model reads, and
    `raw_content` the page's full text, cut, when the purpose asks for it. `published_date` is
    the day the page was published, when the search gives one."""

    url: str
    title: str
    content: str
    raw_content: str | None = None
    published_date: date | None = None


class SearchOutcome(DomainModel):
    """The results of one search, or why there are none.

    `credits` is what the service reported for this call; a cache hit costs none.
    `retrieved_at` is when the response was retrieved, also on a cache hit; missing when no
    response came back.
    """

    search_query: str
    purpose: SearchPurpose
    results: tuple[SearchResult, ...] = ()
    retrieved_at: datetime | None = None
    from_cache: bool = False
    credits: int = 0
    failure: FailureKind | None = None


class OfferKind(StrEnum):
    """What a page's product data offers (data_sources.md, "Firecrawl")."""

    # No product, or a product with no offer.
    NONE = "none"
    # An `AggregateOffer` with only a lowest price: no offer anyone can buy at.
    LOWEST_PRICE_ONLY = "lowest_price_only"
    # One offer was read; it may still have no price.
    OFFER = "offer"


class ListedProduct(DomainModel):
    """A product a listing page links to: its name, the link, the brand the listing names (when it
    names one) and the lowest price the listing page shows in euro, missing when it shows none in
    euro. That price is no offer anyone can buy at."""

    name: str
    url: str
    brand: str | None = None
    lowest_price: Decimal | None = None


class PageOffer(DomainModel):
    """One offer a product page states for its product, as the page states it: its price and its
    shipping in euro, whether it can be bought now, its condition (the schema.org value, such as
    "NewCondition") and its seller. Each is missing when the offer does not state it, and a price
    or a shipping cost in another currency is missing too."""

    price: Decimal | None = None
    shipping: Decimal | None = None
    in_stock: bool | None = None
    condition: str | None = None
    seller: str | None = None


class ProductPage(DomainModel):
    """A fetched product page: name, brand and offer from its JSON-LD, and its text as markdown.

    `price` is in euro or missing. A price stated in another currency is never read as euros: it
    is missing, and `other_currency` names the currency the page stated. `in_stock` says
    whether the offer's availability is one that can be bought now, and `seller` names whoever
    sells it; each is missing when the offer does not state it. `offers` holds every offer the
    page states for its product, in its order, the used ones included. `listed` holds the
    products a listing page links to, in its order. `retrieved_at` is when the page was fetched,
    also on a cache hit; missing when no page came back.
    """

    url: str
    name: str | None = None
    brand: str | None = None
    offer: OfferKind = OfferKind.NONE
    price: Decimal | None = None
    other_currency: str | None = None
    in_stock: bool | None = None
    seller: str | None = None
    offers: tuple[PageOffer, ...] = ()
    listed: tuple[ListedProduct, ...] = ()
    markdown: str = ""
    retrieved_at: datetime | None = None
    from_cache: bool = False
    credits: int = 0
    failure: FailureKind | None = None


Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


# The service behind a tool: the HTTP client or its fixture twin. It returns the stored response,
# or the failure when there is none to store.
SearchService = Callable[[SearchRequest], Awaitable[StoredResponse | FailureKind]]
PageService = Callable[[PageRequest], Awaitable[StoredResponse | FailureKind]]


class WebSearch(Protocol):
    """The web search an agent is given: a freshly limited view, made each time its node runs.

    `follow_up` marks a search query a model wrote: a follow-up search, or a search filled
    with a term, a category or a name a model or a page wrote. The fixture twins answer one only
    when it was recorded, and otherwise with `not_recorded`.
    """

    async def __call__(
        self, search_query: str, purpose: SearchPurpose, *, follow_up: bool = False
    ) -> SearchOutcome: ...


class PageFetch(Protocol):
    """The page fetch for a URL the user pasted, a listing page or a product page, limited like
    the web search."""

    async def __call__(self, url: str) -> ProductPage: ...
