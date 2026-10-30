"""The sources the graph is built with: live services or their fixture twins, and the cache.

Live or fixtures is an explicit choice (`SHOPPER_SOURCES`); there is no silent fallback. Each
mode has its own cache folder, so a report never mixes real and recorded research.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx

from shopper.config import (
    CACHE_FOLDER,
    FIRECRAWL_KEY_NAME,
    FIXTURES_FOLDER,
    TAVILY_KEY_NAME,
    require,
    sources_mode,
    tavily_daily_credit_limit,
)
from shopper.tools.firecrawl import firecrawl_service
from shopper.tools.fixtures import fixture_page_service, fixture_search_service
from shopper.tools.ledger import with_daily_ceiling
from shopper.tools.results import Clock, PageService, SearchService, utc_now
from shopper.tools.tavily import tavily_service

LEDGER_FILE = "tavily_credits.json"


@dataclass(frozen=True)
class Sources:
    """The services behind the web search and the page fetch, where their cache is, and the clock.

    Agents never get this; each gets a limited view made from it (`search_view`, `page_view`).
    """

    search: SearchService
    fetch_page: PageService
    cache_folder: Path
    clock: Clock = utc_now


def sources_from_env(env: Mapping[str, str], client: httpx.AsyncClient) -> Sources:
    """The live services unless `SHOPPER_SOURCES` chooses the fixtures. The app's fixtures read a
    page no recording holds as `not_recorded`, as a model's search query is: the live model can
    pick a candidate no recording read, and a user can paste any link."""
    if sources_mode(env) == "fixtures":
        return fixture_sources(lenient=True)
    return live_sources(env, client)


def live_sources(
    env: Mapping[str, str],
    client: httpx.AsyncClient,
    cache_folder: Path = CACHE_FOLDER / "live",
    clock: Clock = utc_now,
) -> Sources:
    """Tavily behind the daily credit ceiling, and Firecrawl.

    A missing key raises MissingSettingError here, as a configuration error; there is no fallback
    to the fixtures.
    """
    tavily_key = require(env, TAVILY_KEY_NAME)
    firecrawl_key = require(env, FIRECRAWL_KEY_NAME)
    search = with_daily_ceiling(
        tavily_service(client, tavily_key, clock),
        cache_folder / LEDGER_FILE,
        tavily_daily_credit_limit(env),
        clock,
    )
    fetch_page = firecrawl_service(client, firecrawl_key, clock)
    return Sources(search=search, fetch_page=fetch_page, cache_folder=cache_folder, clock=clock)


def fixture_sources(
    fixtures_folder: Path = FIXTURES_FOLDER,
    cache_folder: Path = CACHE_FOLDER / "fixtures",
    *,
    lenient: bool = False,
) -> Sources:
    """The fixture twins: recorded responses, no network, no key. A page no fixture holds raises
    unless `lenient`."""
    return Sources(
        search=fixture_search_service(fixtures_folder),
        fetch_page=fixture_page_service(fixtures_folder, lenient=lenient),
        cache_folder=cache_folder,
    )
