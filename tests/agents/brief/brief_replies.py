"""What the brief agent's tests share: a frying pan's two template searches and what they find,
the model's replies written by hand, and running `research_brief` on them. Rules:
docs/architecture/category_brief.md and docs/architecture/interview.md.
"""

import asyncio
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from fakes import UNUSED_SOURCES, Clock, counted, failing_page_service, fake_chat, finding
from shopper.agents.brief.agent import research_brief
from shopper.agents.brief.prompt import LOCAL_TERM_PROMPT, STATED_PROMPT
from shopper.agents.bundle import BriefOutput
from shopper.llm import ChatRequest
from shopper.state import ProductOption, Request, Scope, TrailKind, WarningCode
from shopper.tools.brief_store import brief_store
from shopper.tools.results import SearchRequest, SearchService
from shopper.tools.search import search_view
from shopper.tools.sources import Sources

NOON = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
FRYING_PAN = Request(original_text="a frying pan", category="frying pan", scope=Scope.TUNED)
LINK = "https://example.org/shop/some-product"


# --- What the search service finds ---

GUIDE_QUERY = "frying pan buying guide what to look for"
CARE_QUERY = "frying pan care maintenance and replacement parts"
GUIDE_URL = "https://example.org/frying-pan-guide"
MAKER_URL = "https://maker.example.com/pan-manual"
CARE_URL = "https://example.org/frying-pan-care"
GUIDE = {
    "url": GUIDE_URL,
    "title": "How to choose a frying pan",
    "content": (
        "Only pans with a magnetic base work on an induction hob. "
        "A pan of 28 cm suits most households."
    ),
}
MAKER = {
    "url": MAKER_URL,
    "title": "Care instructions",
    "content": "Our non-stick pans must be washed by hand to protect the coating.",
}
CARE = {
    "url": CARE_URL,
    "title": "Looking after a frying pan",
    "content": (
        "A carbon steel pan needs seasoning with oil before first use. "
        "A worn non-stick coating cannot be repaired, so the pan is replaced."
    ),
}
# The second search finds the guide again; it is shown to the model once, as result 1.
FOUND = {GUIDE_QUERY: (GUIDE, MAKER), CARE_QUERY: (CARE, GUIDE)}


# --- What the model writes, by hand ---


def stated(*requirements: Mapping[str, object]) -> str:
    """The small model's reply to the call that reads what the request states, written by hand."""
    return json.dumps({"requirements": list(requirements)})


def requirement(
    factor: int | str,
    phrase: str,
    *,
    choice: int | None = None,
    value: str | None = None,
    frequency: str | None = None,
) -> dict[str, object]:
    """One requirement in that reply: a factor by its number in the prompt, or "new"."""
    return {
        "factor": factor,
        "choice": choice,
        "value": value,
        "frequency": frequency,
        "phrase": phrase,
    }


NOTHING_STATED = stated()


def factor(
    name: str,
    kind: str,
    why: str,
    result: int,
    quote: str,
    stated_by: str = "tester",
    *,
    amount: str | None = None,
    interval: str | None = None,
    pack: str | None = None,
) -> dict[str, object]:
    """One decision factor in the read's reply, citing a search result by its number; a
    recurring-cost factor may quote its amount, interval and pack count from that result."""
    return {
        "name": name,
        "kind": kind,
        "why": why,
        "result": result,
        "quote": quote,
        "stated_by": stated_by,
        "amount_quote": amount,
        "interval_quote": interval,
        "pack_count_quote": pack,
    }


HOB = factor(
    "Hob compatibility",
    "compatibility",
    "Not every pan works on an induction hob.",
    1,
    "Only pans with a magnetic base work on an induction hob.",
)
SIZE = factor(
    "Pan size",
    "requirement",
    "A pan that is too small is soon replaced.",
    1,
    "A pan of 28 cm suits most households.",
)
SEASONING = factor(
    "Seasoning",
    "care",
    "A carbon steel pan needs seasoning to keep food from sticking.",
    3,
    "needs seasoning with oil before first use",
)
HAND_WASHING = factor(
    "Hand washing",
    "care",
    "Some coatings do not survive a dishwasher.",
    2,
    "must be washed by hand to protect the coating",
    stated_by="manufacturer",
)
COATING_WEAR = factor(
    "Coating wear",
    "recurring_cost",
    "A worn coating means buying a new pan.",
    3,
    "A worn non-stick coating cannot be repaired",
)
FIVE_FACTORS = (HOB, SIZE, SEASONING, HAND_WASHING, COATING_WEAR)


def reading(
    *factors: Mapping[str, object],
    gaps: Sequence[Mapping[str, str]] = (),
    follow_up_query: str | None = None,
) -> str:
    """The medium model's reply to a read, written by hand."""
    return json.dumps(
        {"factors": list(factors), "gaps": list(gaps), "follow_up_query": follow_up_query}
    )


def phrasing(*questions: Mapping[str, object], usage_frequencies: Sequence[str] = ()) -> str:
    """The model's reply to the phrasing call, written by hand."""
    return json.dumps({"questions": list(questions), "usage_frequencies": list(usage_frequencies)})


def asked(number: int, text: str, reason: str, *choices: str) -> dict[str, object]:
    """A question in the phrasing reply, for the factor with this number in the prompt."""
    return {"factor": number, "text": text, "reason": reason, "choices": list(choices)}


def care(number: int, statement: str) -> dict[str, object]:
    """A care statement in the phrasing reply."""
    return {"factor": number, "text": statement, "reason": None, "choices": []}


# The recurring-cost factor gets no question, so the model is shown four factors.
HOB_QUESTION = asked(
    1,
    "Which hob do you cook on?",
    "Not every pan works on every hob.",
    "Induction",
    "Gas",
    "Electric or ceramic",
)
SIZE_QUESTION = asked(
    2,
    "Which size of pan do you need?",
    "The size decides how much fits in the pan.",
    "Smaller than 28 cm",
    "28 cm",
    "Larger than 28 cm",
)
SEASONING_STATEMENT = care(3, "Some frying pans need seasoning with oil before first use.")
HAND_WASHING_STATEMENT = care(4, "Some frying pans are washed by hand only.")
FOUR_QUESTIONS = (HOB_QUESTION, SIZE_QUESTION, SEASONING_STATEMENT, HAND_WASHING_STATEMENT)


# --- Running the agent ---


class Ran(NamedTuple):
    """What one call of the agent gave, and what it asked of the model and the search service.

    `requests` are the research and phrasing calls; `stated_requests` the calls that read what
    the request states.
    """

    output: BriefOutput
    requests: list[ChatRequest]
    stated_requests: list[ChatRequest]
    searches: list[SearchRequest]
    term_requests: tuple[ChatRequest, ...] = ()


def run(
    cache: Path,
    *replies: str | Exception,
    request: Request = FRYING_PAN,
    linked: ProductOption | None = None,
    service: SearchService = UNUSED_SOURCES.search,
    now: datetime = NOON,
    stated_replies: Sequence[str | Exception] = (NOTHING_STATED,),
    local_terms: Mapping[str, str | Exception] | None = None,
) -> Ran:
    """One call of the agent; the replies to the stated-answers call come last, after research.
    The call for the local category term is answered by its category (`fake_chat`)."""
    chat, requests = fake_chat((*replies, *stated_replies), local_terms)
    counted_service, searches = counted(service)
    sources = Sources(
        search=counted_service,
        fetch_page=failing_page_service(),
        cache_folder=cache,
        clock=Clock(now),
    )
    store = brief_store(sources.cache_folder, sources.clock)
    output = asyncio.run(research_brief(request, linked, chat, search_view(sources, 3), store))
    return Ran(
        output,
        [
            request
            for request in requests
            if not is_stated_call(request) and not is_term_call(request)
        ],
        [request for request in requests if is_stated_call(request)],
        searches,
        tuple(request for request in requests if is_term_call(request)),
    )


def is_stated_call(request: ChatRequest) -> bool:
    return request.messages[0] == {"role": "system", "content": STATED_PROMPT}


def is_term_call(request: ChatRequest) -> bool:
    return request.messages[0] == {"role": "system", "content": LOCAL_TERM_PROMPT}


def brief(cache: Path, *questions: Mapping[str, object], frequencies: Sequence[str] = ()) -> Ran:
    """A run on the five factors with this phrasing reply."""
    return run(
        cache,
        reading(*FIVE_FACTORS),
        phrasing(*questions, usage_frequencies=frequencies),
        service=finding(FOUND),
    )


# --- Reading what it gave ---


def excluded(output: BriefOutput, opening: str = "Left out") -> list[tuple[str, str]]:
    """The summary and the reason of each exclusion on the trail whose summary opens this way:
    "Left out" for a factor of a read, "No question" for a factor that was not phrased."""
    return [
        (entry.summary, entry.reason)
        for entry in output.trail
        if entry.kind is TrailKind.EXCLUDED and entry.summary.startswith(opening)
    ]


def asked_about(output: BriefOutput) -> list[str]:
    return [question.factor_id for question in output.questions]


def warnings(output: BriefOutput) -> list[tuple[WarningCode, str]]:
    return [(warning.code, warning.message) for warning in output.warnings]


def trail(output: BriefOutput, opening: str) -> list[tuple[TrailKind, str, str | None]]:
    """The kind, summary and reason of each trail entry whose summary opens this way."""
    return [
        (entry.kind, entry.summary, entry.reason)
        for entry in output.trail
        if entry.summary.startswith(opening)
    ]
