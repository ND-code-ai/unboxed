"""Choosing the sources from the environment: live needs both keys, there is no fallback."""

import asyncio
from pathlib import Path

import httpx
import pytest

from shopper.config import MissingSettingError
from shopper.tools.fixtures import FixtureMissingError
from shopper.tools.results import FailureKind, PageRequest, StoredResponse
from shopper.tools.sources import Sources, fixture_sources, sources_from_env

KEYS = {"TAVILY_API_KEY": "tvly-test", "FIRECRAWL_API_KEY": "fc-test"}
FIXTURES = Path(__file__).parent.parent / "fixtures"
UNRECORDED = PageRequest(url="https://www.beslist.nl/p/a-pan-nobody-recorded/165/1/", parameters={})


def built(env: dict[str, str]) -> Sources:
    async def run() -> Sources:
        async with httpx.AsyncClient() as client:
            return sources_from_env(env, client)

    return asyncio.run(run())


def fetched(sources: Sources) -> StoredResponse | FailureKind:
    return asyncio.run(sources.fetch_page(UNRECORDED))


@pytest.mark.parametrize("missing", ["TAVILY_API_KEY", "FIRECRAWL_API_KEY"])
def test_live_sources_with_a_key_missing_are_a_configuration_error(missing: str) -> None:
    env = {name: value for name, value in KEYS.items() if name != missing}

    with pytest.raises(MissingSettingError, match=missing):
        built(env)


def test_fixtures_need_no_key(tmp_path: Path) -> None:
    built({"SHOPPER_SOURCES": "fixtures"})


def test_the_app_on_the_fixtures_reads_a_page_nobody_recorded_as_not_recorded() -> None:
    # With the live model a candidate the recordings never read can be picked; the run goes on.
    assert fetched(built({"SHOPPER_SOURCES": "fixtures"})) is FailureKind.NOT_RECORDED


def test_in_the_tests_a_page_nobody_recorded_is_a_programmer_error(tmp_path: Path) -> None:
    with pytest.raises(FixtureMissingError, match="a-pan-nobody-recorded"):
        fetched(fixture_sources(FIXTURES, tmp_path / "cache"))
