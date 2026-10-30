"""Fakes for the edges: the model, the services behind the tools and the clock.

Passed in as parameters, never patched in.
"""

import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from shopper.agents.brief.prompt import LOCAL_TERM_PROMPT
from shopper.agents.tco.prompt import (
    EVIDENCE_PROMPT,
    FINDINGS_PROMPT,
    JUDGE_NAMES_PROMPT,
    JUDGE_PAGES_PROMPT,
    PAGE_PROMPT,
)
from shopper.llm import ChatModel, ChatRequest
from shopper.tools.results import (
    FailureKind,
    PageRequest,
    PageService,
    SearchRequest,
    SearchService,
    Service,
    StoredResponse,
)
from shopper.tools.sources import Sources

# The local category term the model gives for each tuned category: the words of the recorded
# listing searches (docs/findings/task_1.12.md). Any other category gets itself as its term.
LOCAL_TERMS = {"frying pan": "koekenpan", "kettle": "waterkoker", "drill": "accuboormachine"}


def fake_chat(
    replies: Sequence[str | Exception],
    local_terms: Mapping[str, str | Exception] | None = None,
) -> tuple[ChatModel, list[ChatRequest]]:
    """A chat model that gives hand-written replies in order and records what it was asked.

    The call for the local category term runs beside the category searches, so it is answered
    by its category instead: from `local_terms`, else from `LOCAL_TERMS`.
    """
    requests: list[ChatRequest] = []
    remaining = list(replies)

    async def chat(request: ChatRequest) -> str:
        requests.append(request)
        if request.messages[0]["content"] == LOCAL_TERM_PROMPT:
            reply = local_term_reply(request, local_terms or {})
        else:
            reply = remaining.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return chat, requests


def local_term_reply(
    request: ChatRequest, local_terms: Mapping[str, str | Exception]
) -> str | Exception:
    """The reply for the category the call names: a reply given for it, or its term."""
    named = re.search(r"^Category: (.*)$", request.messages[1]["content"], re.MULTILINE)
    assert named is not None
    category = named.group(1)
    if category in local_terms:
        return local_terms[category]
    return json.dumps({"local_term": LOCAL_TERMS.get(category, category)})


def sold_as(
    name: str,
    sells: str = "the_item",
    quote: str | None = None,
    *,
    piece_count: int | None = None,
    piece_count_quote: str | None = None,
) -> str:
    """A page read that says the page sells this, quoted by the name unless another quote is
    given; the amount's own words are not checked."""
    return json.dumps(
        {
            "results": [
                {
                    "result": 1,
                    "amounts": [
                        {
                            "quote": "€ 1",
                            "name": name,
                            "sells": sells,
                            "sells_quote": name if quote is None else quote,
                            "piece_count": piece_count,
                            "piece_count_quote": piece_count_quote,
                        }
                    ],
                }
            ]
        }
    )


def judged(*judgements: tuple[int, str, str | None], set_requested: bool | None = None) -> str:
    """A durability judgement: each candidate's number, value and reason. With `set_requested`
    it is the judgement by name, which also says whether a set is asked for."""
    reply: dict[str, object] = {
        "candidates": [
            {"candidate": number, "durability_judgement": value, "durability_reason": reason}
            for number, value, reason in judgements
        ]
    }
    if set_requested is not None:
        reply["set_requested"] = set_requested
    return json.dumps(reply)


# Judgements that judge no candidate, so every judgement is unknown.
NOT_JUDGED_BY_NAME = judged(set_requested=False)
NOT_JUDGED_BY_PAGE = judged()


# An evidence read that found nothing: the estimate rests on no evidence.
NO_EVIDENCE = json.dumps(
    {
        "lifespans": [],
        "warranty": None,
        "repairability": None,
        "wear_material": None,
        "care": None,
        "consumable": None,
        "other_consumables": [],
        "estimated_years": 5,
        "estimate_rests_on": [],
        "fits": [],
        "gaps": [],
    }
)

# A findings read that kept nothing.
NO_FINDINGS = json.dumps({"findings": [], "gaps": []})


def fake_chat_with_reads(
    replies: Sequence[str | Exception],
    *,
    by_name: str | Exception = NOT_JUDGED_BY_NAME,
    by_page: str | Exception = NOT_JUDGED_BY_PAGE,
    page_reads: Mapping[str, str | Exception] | None = None,
    evidence_reads: Mapping[str, str | Exception] | None = None,
    findings_reads: Mapping[str, str | Exception] | None = None,
) -> tuple[ChatModel, list[ChatRequest]]:
    """As `fake_chat`, except that option research's calls are answered by what they are about,
    since they run at the same time and their order is not fixed: the two durability judgements
    by their prompt, a page read by the page's product name, and an evidence or findings read by
    its product. A page read of a page not given sells the item; an evidence or findings read of
    a product not given finds nothing."""
    requests: list[ChatRequest] = []
    remaining = list(replies)
    by_product = {
        EVIDENCE_PROMPT: (evidence_reads or {}, NO_EVIDENCE),
        FINDINGS_PROMPT: (findings_reads or {}, NO_FINDINGS),
    }

    async def chat(request: ChatRequest) -> str:
        requests.append(request)
        system = request.messages[0]["content"]
        # The first user message names what is read; a retry adds the validation error after it.
        asked = request.messages[1]["content"]
        reply: str | Exception
        if system == LOCAL_TERM_PROMPT:
            reply = local_term_reply(request, {})
        elif system == JUDGE_NAMES_PROMPT:
            reply = by_name
        elif system == JUDGE_PAGES_PROMPT:
            reply = by_page
        elif system == PAGE_PROMPT:
            page = re.search(r"^\[1\] (.*)$", asked, re.MULTILINE)
            assert page is not None
            reply = (page_reads or {}).get(page.group(1), sold_as(page.group(1)))
        elif system in by_product:
            product = re.search(r"^Product: (.*)$", asked, re.MULTILINE)
            assert product is not None
            reads, nothing = by_product[system]
            reply = reads.get(product.group(1), nothing)
        else:
            reply = remaining.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return chat, requests


def extraction(
    category: str | None = "frying pan",
    scope: str = "tuned",
    budget_phrase: str | None = None,
    budget_amount: float | None = None,
    budget_currency: str | None = None,
) -> str:
    """The supervisor model's reply, written by hand."""
    return json.dumps(
        {
            "category": category,
            "scope": scope,
            "budget_phrase": budget_phrase,
            "budget_amount": budget_amount,
            "budget_currency": budget_currency,
        }
    )


def typing(*typed: str) -> Callable[[str], str]:
    """What the user types in the terminal app, one line per prompt; the input ends when the
    lines run out."""
    remaining = iter(typed)

    def read(prompt: str) -> str:
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    return read


class Clock:
    """A clock a test sets; calling it gives the time it was set to."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def counted[R: (SearchRequest, PageRequest)](
    service: Callable[[R], Awaitable[StoredResponse | FailureKind]],
) -> tuple[Callable[[R], Awaitable[StoredResponse | FailureKind]], list[R]]:
    """The same service, noting each request that reached it: each one a network call."""
    calls: list[R] = []

    async def call(request: R) -> StoredResponse | FailureKind:
        calls.append(request)
        return await service(request)

    return call, calls


def failing_search_service(failure: FailureKind) -> SearchService:
    async def search(request: SearchRequest) -> FailureKind:
        return failure

    return search


def failing_page_service(failure: FailureKind = FailureKind.UNAVAILABLE) -> PageService:
    async def fetch(request: PageRequest) -> FailureKind:
        return failure

    return fetch


def answering_search_service(at: datetime) -> SearchService:
    """A search service that finds one result for any search query."""

    async def search(request: SearchRequest) -> StoredResponse:
        return StoredResponse(
            service=Service.TAVILY,
            request={"search_query": request.search_query, "purpose": request.purpose},
            retrieved_at=at,
            response={
                "results": [
                    {"url": "https://example.org/a", "title": "A", "content": request.search_query}
                ],
                "usage": {"credits": 1},
            },
        )

    return search


def finding(found: Mapping[str, Sequence[Mapping[str, str]]]) -> SearchService:
    """A search service that finds these results for these search queries, at one credit each;
    any other search query fails the test."""

    async def search(request: SearchRequest) -> StoredResponse:
        return StoredResponse(
            service=Service.TAVILY,
            request={"search_query": request.search_query, "purpose": request.purpose},
            retrieved_at=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
            response={"results": list(found[request.search_query]), "usage": {"credits": 1}},
        )

    return search


def recording(found: Mapping[str, Sequence[Mapping[str, str]]]) -> SearchService:
    """A search service that answers as the fixture twin does: these results for these search
    queries, and `not_recorded` for a search query a model wrote that it has none for."""
    answer = finding(found)

    async def search(request: SearchRequest) -> StoredResponse | FailureKind:
        if request.follow_up and request.search_query not in found:
            return FailureKind.NOT_RECORDED
        return await answer(request)

    return search


async def _never_searched(request: SearchRequest) -> StoredResponse | FailureKind:
    raise AssertionError(f"no search expected, got {request.search_query!r}")


async def _never_fetched(request: PageRequest) -> StoredResponse | FailureKind:
    raise AssertionError(f"no page fetch expected, got {request.url!r}")


# For a graph whose agents call no tool: any call fails the test, and nothing is cached.
UNUSED_SOURCES = Sources(
    search=_never_searched, fetch_page=_never_fetched, cache_folder=Path("unused-cache")
)


TransportHandler = Callable[[httpx.Request], httpx.Response]


def transport_answers(
    *responses: httpx.Response | Exception,
) -> tuple[TransportHandler, list[httpx.Request]]:
    """An HTTP transport handler that gives these responses in order, an exception being
    raised, and records each request."""
    seen: list[httpx.Request] = []
    remaining = list(responses)

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        response = remaining.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    return handle, seen
