"""The web search an agent is given, against recorded responses in tests/fixtures/."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from fakes import (
    Clock,
    answering_search_service,
    counted,
    failing_page_service,
    failing_search_service,
    finding,
)
from shopper.config import RAW_CONTENT_MAX_CHARACTERS, SearchPurpose
from shopper.tools.fixtures import FixtureMissingError, fixture_search_service
from shopper.tools.results import (
    FailureKind,
    SearchOutcome,
    SearchRequest,
    SearchService,
    StoredResponse,
)
from shopper.tools.search import search_view
from shopper.tools.sources import Sources, fixture_sources

FIXTURES = Path(__file__).parent.parent / "fixtures"
FRYING_PAN = "frying pan buying guide what to look for"
KETTLE = "kettle buying guide what to look for"
DRILL = "drill buying guide what to look for"
NOON = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def sources_with(tmp_path: Path, service: SearchService, clock: Clock | None = None) -> Sources:
    return Sources(
        search=service,
        fetch_page=failing_page_service(),
        cache_folder=tmp_path / "cache",
        clock=clock or Clock(NOON),
    )


def search(
    sources: Sources, max_calls: int, *queries: tuple[str, SearchPurpose]
) -> list[SearchOutcome]:
    """Run the searches one after another through one limited view."""
    view = search_view(sources, max_calls)

    async def run() -> list[SearchOutcome]:
        return [await view(query, purpose) for query, purpose in queries]

    return asyncio.run(run())


def test_a_search_gives_the_recorded_results_and_the_credits_reported(tmp_path: Path) -> None:
    sources = fixture_sources(FIXTURES, tmp_path / "cache")

    (outcome,) = search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))

    assert [result.url for result in outcome.results] == [
        "https://www.tasteofhome.com/article/frying-pan-guide",
        "https://www.consumerreports.org/home-garden/cookware/buying-guide",
        "https://www.all-clad.com/blog/post/The-Ultimate-Frying-Pan-Buying-Guide-How-to-choose-the-right-fry-pan-size-for-you",
    ]
    assert outcome.results[2].content == (
        "Eggs: A small frying pan of around 8 inches is usually sufficient for cooking eggs."
    )
    assert outcome.credits == 1
    assert outcome.from_cache is False
    assert outcome.failure is None


def test_a_result_on_an_excluded_domain_is_dropped_as_the_live_search_would(
    tmp_path: Path,
) -> None:
    # Recorded in task 1.8, before every eBay site was excluded from the evidence search; it
    # holds ebay.co.uk, and two social sites the purpose excluded from the start.
    sources = fixture_sources(FIXTURES, tmp_path / "cache")

    (outcome,) = search(
        sources, 1, ("Ryobi R18PD3-215GZ replacement battery price", SearchPurpose.EVIDENCE)
    )

    sites = [result.url.split("/")[2] for result in outcome.results]
    assert sites == [
        "www.idealo.co.uk",
        "m.media-amazon.com",
        "www.amazon.co.uk",
        "tooltechltd.com",
        "www.reddit.com",
    ]


def test_full_page_text_comes_cut_to_its_length_and_none_stays_none(tmp_path: Path) -> None:
    page = {
        "url": "https://a.example/p",
        "title": "P",
        "content": "snippet",
        "raw_content": "x" * 50_000,
    }
    bare = {"url": "https://b.example/p", "title": "Q", "content": "snippet", "raw_content": None}
    sources = sources_with(tmp_path, finding({"kettle durability": (page, bare)}))

    (outcome,) = search(sources, 1, ("kettle durability", SearchPurpose.EVIDENCE))

    assert outcome.results[0].raw_content == "x" * RAW_CONTENT_MAX_CHARACTERS
    assert outcome.results[1].raw_content is None


@pytest.mark.parametrize(
    ("published", "day"),
    [
        ("2025-03-14", date(2025, 3, 14)),
        ("2025-03-14T08:00:00Z", date(2025, 3, 14)),
        ("Fri, 14 Mar 2025 08:00:00 GMT", date(2025, 3, 14)),
        ("last spring", None),
        (None, None),
    ],
)
def test_a_result_keeps_the_day_it_was_published_when_the_search_gives_one(
    tmp_path: Path, published: str | None, day: date | None
) -> None:
    page = {"url": "https://a.example/p", "title": "P", "content": "x", "published_date": published}
    sources = sources_with(tmp_path, finding({"alpha pan review": (page,)}))

    (outcome,) = search(sources, 1, ("alpha pan review", SearchPurpose.FINDINGS))

    assert outcome.results[0].published_date == day


def test_an_evidence_search_drops_social_sites_and_every_ebay_domain(tmp_path: Path) -> None:
    sites = ("www.facebook.com", "www.ebay.co.uk", "www.ebay.be", "www.which.co.uk")
    found = tuple(
        {"url": f"https://{site}/p", "title": "Kettle", "content": "The kettle lasts."}
        for site in sites
    )
    sources = sources_with(tmp_path, finding({"kettle durability": found}))

    (outcome,) = search(sources, 1, ("kettle durability", SearchPurpose.EVIDENCE))

    assert [result.url for result in outcome.results] == ["https://www.which.co.uk/p"]


def test_a_repeated_search_query_makes_no_network_call(tmp_path: Path) -> None:
    service, calls = counted(fixture_search_service(FIXTURES))
    sources = sources_with(tmp_path, service)

    first, again = search(
        sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY), (FRYING_PAN, SearchPurpose.CATEGORY)
    )

    assert len(calls) == 1
    assert again.from_cache is True
    assert again.credits == 0
    assert again.results == first.results


def test_the_cache_outlives_the_view_so_a_later_analysis_reuses_it(tmp_path: Path) -> None:
    service, calls = counted(fixture_search_service(FIXTURES))
    sources = sources_with(tmp_path, service)

    search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))
    (later,) = search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))

    assert len(calls) == 1
    assert later.from_cache is True


def test_a_search_says_when_it_was_retrieved_also_from_the_cache(tmp_path: Path) -> None:
    clock = Clock(NOON)
    sources = sources_with(tmp_path, fixture_search_service(FIXTURES), clock)

    (first,) = search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))
    clock.now = NOON + timedelta(days=3)
    (later,) = search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))

    # The fixture was recorded on another day; the clock stamps it when it is stored.
    assert first.retrieved_at == NOON
    assert later.from_cache is True
    assert later.retrieved_at == NOON


def test_a_failed_search_was_never_retrieved(tmp_path: Path) -> None:
    sources = sources_with(tmp_path, failing_search_service(FailureKind.TIMED_OUT))

    (outcome,) = search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))

    assert outcome.retrieved_at is None


def test_case_and_spacing_do_not_change_the_cache_key(tmp_path: Path) -> None:
    service, calls = counted(fixture_search_service(FIXTURES))
    sources = sources_with(tmp_path, service)

    search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))
    (again,) = search(
        sources, 3, ("  Frying pan  buying GUIDE what to look for", SearchPurpose.CATEGORY)
    )

    assert len(calls) == 1
    assert again.from_cache is True


def test_the_call_after_the_limit_returns_limit_reached_without_a_network_call(
    tmp_path: Path,
) -> None:
    service, calls = counted(fixture_search_service(FIXTURES))
    sources = sources_with(tmp_path, service)

    outcomes = search(
        sources,
        2,
        (FRYING_PAN, SearchPurpose.CATEGORY),
        (KETTLE, SearchPurpose.CATEGORY),
        (DRILL, SearchPurpose.CATEGORY),
    )

    assert [outcome.failure for outcome in outcomes] == [None, None, FailureKind.LIMIT_REACHED]
    assert outcomes[2].search_query == DRILL
    assert len(calls) == 2


def test_cache_hits_do_not_count_toward_the_limit(tmp_path: Path) -> None:
    service, _ = counted(fixture_search_service(FIXTURES))
    sources = sources_with(tmp_path, service)

    outcomes = search(
        sources,
        2,
        (FRYING_PAN, SearchPurpose.CATEGORY),
        (FRYING_PAN, SearchPurpose.CATEGORY),
        (KETTLE, SearchPurpose.CATEGORY),
        (FRYING_PAN, SearchPurpose.CATEGORY),
    )

    assert [outcome.failure for outcome in outcomes] == [None, None, None, None]


def test_a_new_view_has_its_full_limit_again(tmp_path: Path) -> None:
    sources = sources_with(tmp_path, fixture_search_service(FIXTURES))

    search(sources, 1, (FRYING_PAN, SearchPurpose.CATEGORY))
    (outcome,) = search(sources, 1, (KETTLE, SearchPurpose.CATEGORY))

    assert outcome.failure is None


def test_a_search_with_no_results_is_not_found_and_is_cached(tmp_path: Path) -> None:
    service, calls = counted(fixture_search_service(FIXTURES))
    sources = sources_with(tmp_path, service)

    first, again = search(
        sources,
        3,
        ("zzqx frying pan nonsense", SearchPurpose.CATEGORY),
        ("zzqx frying pan nonsense", SearchPurpose.CATEGORY),
    )

    assert first.failure is FailureKind.NOT_FOUND
    assert again.failure is FailureKind.NOT_FOUND
    assert len(calls) == 1


def test_a_failure_is_returned_and_not_cached(tmp_path: Path) -> None:
    service, calls = counted(failing_search_service(FailureKind.RATE_LIMITED))
    sources = sources_with(tmp_path, service)

    first, again = search(
        sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY), (FRYING_PAN, SearchPurpose.CATEGORY)
    )

    assert first.failure is FailureKind.RATE_LIMITED
    assert again.from_cache is False
    assert len(calls) == 2


def test_a_listing_pages_search_is_searched_again_after_a_day(tmp_path: Path) -> None:
    # A listing page shows prices, which change (task 1.12, docs/findings/task_1.12.md).
    service, calls = counted(fixture_search_service(FIXTURES))
    clock = Clock(NOON)
    sources = sources_with(tmp_path, service, clock)
    listing_search = ("koekenpan kopen", SearchPurpose.LISTING_PAGES)

    search(sources, 3, listing_search)
    clock.now = NOON + timedelta(hours=23)
    (same_day,) = search(sources, 3, listing_search)
    clock.now = NOON + timedelta(days=1, minutes=1)
    (next_day,) = search(sources, 3, listing_search)

    assert same_day.from_cache is True
    assert next_day.from_cache is False
    assert len(calls) == 2


def test_a_category_search_does_not_expire(tmp_path: Path) -> None:
    service, calls = counted(fixture_search_service(FIXTURES))
    clock = Clock(NOON)
    sources = sources_with(tmp_path, service, clock)

    search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))
    clock.now = NOON + timedelta(days=400)
    (later,) = search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))

    assert later.from_cache is True
    assert len(calls) == 1


def test_the_cache_file_is_the_stored_format_with_the_request_as_readable_fields(
    tmp_path: Path,
) -> None:
    sources = sources_with(tmp_path, fixture_search_service(FIXTURES))

    search(sources, 3, (FRYING_PAN, SearchPurpose.CATEGORY))

    (cached,) = (tmp_path / "cache").rglob("*.json")
    stored = StoredResponse.model_validate(json.loads(cached.read_text(encoding="utf-8")))
    assert stored.request["search_query"] == FRYING_PAN
    assert stored.request["purpose"] == "category"
    assert stored.request["parameters"]["search_depth"] == "basic"


def follow_up(sources: Sources, search_query: str) -> SearchOutcome:
    """One follow-up search: a search query a model wrote, not a code template."""
    view = search_view(sources, 3)
    return asyncio.run(view(search_query, SearchPurpose.CATEGORY, follow_up=True))


def test_a_follow_up_nobody_recorded_is_not_recorded_with_the_fixture_twin(
    tmp_path: Path,
) -> None:
    outcome = follow_up(
        fixture_sources(FIXTURES, tmp_path / "cache"), "frying pan seasoning and care guide"
    )

    assert outcome.failure is FailureKind.NOT_RECORDED
    assert outcome.search_query == "frying pan seasoning and care guide"


def test_a_search_query_a_model_wrote_is_answered_when_it_was_recorded(tmp_path: Path) -> None:
    view = search_view(fixture_sources(FIXTURES, tmp_path / "cache"), 3)

    outcome = asyncio.run(view("koekenpan kopen", SearchPurpose.LISTING_PAGES, follow_up=True))

    assert outcome.failure is None
    assert len(outcome.results) == 8


def test_a_not_recorded_search_is_not_cached(tmp_path: Path) -> None:
    service, calls = counted(fixture_search_service(FIXTURES))
    sources = replace(fixture_sources(FIXTURES, tmp_path / "cache"), search=service)

    follow_up(sources, "frying pan seasoning and care guide")
    again = follow_up(sources, "frying pan seasoning and care guide")

    assert again.failure is FailureKind.NOT_RECORDED
    assert len(calls) == 2


def test_a_follow_up_reaches_a_live_service(tmp_path: Path) -> None:
    service, calls = counted(answering_search_service(NOON))

    outcome = follow_up(sources_with(tmp_path, service), "frying pan seasoning and care guide")

    assert outcome.failure is None
    assert len(calls) == 1


def test_a_search_with_no_fixture_is_a_programmer_error_naming_the_search_query() -> None:
    service = fixture_search_service(FIXTURES)
    request = SearchRequest(
        search_query="a search nobody recorded", purpose=SearchPurpose.CATEGORY, parameters={}
    )

    with pytest.raises(FixtureMissingError, match="a search nobody recorded"):
        asyncio.run(service(request))


def test_a_fixture_is_matched_on_search_query_and_purpose_only() -> None:
    service = fixture_search_service(FIXTURES)
    request = SearchRequest(
        search_query=FRYING_PAN, purpose=SearchPurpose.CATEGORY, parameters={"max_results": 3}
    )

    stored = asyncio.run(service(request))

    assert isinstance(stored, StoredResponse)
