"""The live check of task 1.14: the extracting reads at the default temperature and at a low one.
Spends Nebius credits only; the searches and pages are recorded ones.

uv run python scripts/temperature_check.py run <page|brief|evidence> <default|low> [reads]
uv run python scripts/temperature_check.py show <page|brief|evidence>
uv run python scripts/temperature_check.py record

`run` reads every input of one read `reads` times (5 when not given) through the app's own code,
the real model and the recorded searches and pages: the product pages the live run of task 1.15
fetched (still in `.cache/live/firecrawl/`, whatever their age), the brief searches of the three
tuned categories and the evidence searches of task 1.15 that found a result (`tests/fixtures/`).
`default` sends no temperature, so Nebius uses its own, 1.0, which the model cards recommend;
`low` sends `LOW`. Each read's outcome as code keeps it, and per model call its finish reason,
its tokens, whether its text repeats itself, and the reply, go to
`.cache/live/check_1_14/<read>-<setting>.json`. `show` prints, per input, how many reads differ
from the most common outcome at each setting, and the calls cut off or repeating. The design and
the results are in docs/findings/task_1.14.md.

`record` reads the frying pan pages the replay test of the page read uses (`RECORDED_PAGES`, in
`tests/fixtures/firecrawl/` with their text) once each, at the setting the app sends, and writes
each reply with the prompt and the input it was read over to
`tests/fixtures/nebius/page-read-<page>.json`.
"""

import asyncio
import contextvars
import json
import re
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from shopper.agents.brief import agent as brief_agent
from shopper.agents.shared.research import distinct_results
from shopper.agents.tco.evidence import Subject, option_evidence
from shopper.agents.tco.models import Candidate, PageContext
from shopper.agents.tco.page_read import read_page
from shopper.config import (
    CACHE_FOLDER,
    FIXTURES_FOLDER,
    NEBIUS_KEY_NAME,
    SEARCH_TEMPLATES,
    SearchPurpose,
    load_env,
    require,
)
from shopper.llm import ChatModel, ChatRequest, nebius_chat
from shopper.state import ProductOption
from shopper.tools.product_page import page_request, product_page
from shopper.tools.results import (
    ListedProduct,
    ProductPage,
    SearchOutcome,
    Service,
    StoredResponse,
    WebSearch,
)
from shopper.tools.search import search_outcome, search_request, search_view
from shopper.tools.sources import fixture_sources

CHECK_FOLDER = CACHE_FOLDER / "live" / "check_1_14"
LOW = 0.0
# What each setting sends: no temperature, so Nebius uses its own, or `LOW`.
SETTINGS: dict[str, float | None] = {"default": None, "low": LOW}
READS = 5
AT_ONCE = 6
# The local term and whether a recurring cost is looked for, as the live briefs of task 1.15 hold
# them.
TERMS = {"frying pan": "koekenpan", "kettle": "waterkoker", "drill": "boormachine"}
RECURRING = {"frying pan": False, "kettle": True, "drill": False}
# The product pages the live run of task 1.15 fetched on 24 October 2026.
PAGES_FETCHED_ON = "2026-10-24"
PAGE_PATH = re.compile(r"beslist\.nl/p/|kieskeurig\.nl/[^/]+/product/")
# The evidence searches of task 1.15 that found a result, by fixture name.
EVIDENCE = (
    ("frying pan", "frying-pan-evidence-de-buyer-mineral-b-element-koekenpan-26", "de Buyer"),
    ("frying pan", "frying-pan-evidence-greenchef-diamond-inductie-koekenpan-24", "GreenChef"),
    ("frying pan", "frying-pan-evidence-wmf-profi-resist", "WMF"),
    ("kettle", "kettle-evidence-midea-roestvrijstalen-waterkoker-wit-1-5", "Midea"),
    ("drill", "drill-evidence-bosch-easydrill-18v-38-accu-schroefboorm", "Bosch"),
    ("drill", "drill-evidence-einhell-power-x-change", "Einhell"),
)
# A line of a reply or its reasoning this long, written this many times, is a repetition.
REPEATED_LINE_CHARACTERS = 40
REPEATED_TIMES = 3

Calls = contextvars.ContextVar[list[dict[str, Any]]]


def noting_responses(calls: Calls) -> Callable[[httpx.Response], Awaitable[None]]:
    """A response hook that keeps what each model call's response says about how it ended, in
    the list `calls` holds for the read running now."""

    async def note(response: httpx.Response) -> None:
        if not response.request.url.path.endswith("/chat/completions"):
            return
        await response.aread()
        noted = calls.get(None)
        if noted is not None and response.status_code == 200:
            noted.append(_ending(response.json()))

    return note


def _ending(body: dict[str, Any]) -> dict[str, Any]:
    choice = body["choices"][0]
    message = choice["message"]
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    content = message.get("content") or ""
    usage = body.get("usage") or {}
    return {
        "finish_reason": choice.get("finish_reason"),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "repeats": repeats(reasoning) or repeats(content),
        "reply": content,
    }


def repeats(text: str) -> bool:
    """Whether a long line or sentence of the text is written `REPEATED_TIMES` times or more."""
    parts = [part.strip() for part in re.split(r"[\n.!?]+", text)]
    counted = Counter(part for part in parts if len(part) >= REPEATED_LINE_CHARACTERS)
    return any(times >= REPEATED_TIMES for times in counted.values())


def at_temperature(chat: ChatModel, temperature: float | None) -> ChatModel:
    if temperature is None:
        return chat

    async def at_set(request: ChatRequest) -> str:
        return await chat(request.model_copy(update={"temperature": temperature}))

    return at_set


# --- The inputs of each read: a name and a function that reads it once ---

Read = Callable[[ChatModel], Awaitable[Any]]


def page_inputs() -> list[tuple[str, Read]]:
    inputs = []
    for path in sorted((CACHE_FOLDER / "live" / "firecrawl").glob("*.json")):
        stored = StoredResponse.model_validate_json(path.read_text(encoding="utf-8"))
        url = stored.request["url"]
        if stored.retrieved_at.date().isoformat() != PAGES_FETCHED_ON or not PAGE_PATH.search(url):
            continue
        category = _category(url)
        page = product_page(page_request(url), stored, from_cache=True)
        inputs.append((url, _page_read(category, page)))
    return inputs


def _category(url: str) -> str:
    if "/pan/" in url or "/165/" in url:
        return "frying pan"
    if "/boormachine/" in url or "/35000/" in url:
        return "drill"
    return "kettle"


def _page_read(category: str, page: ProductPage) -> Read:
    context = PageContext(category, TERMS[category], set_requested=False, sized=False)
    candidate = Candidate(1, _listed(page))

    async def fetch(url: str) -> ProductPage:
        return page

    async def read(chat: ChatModel) -> Any:
        found = await read_page(candidate, context, chat, fetch)
        if found.offered is not None:
            offered = found.offered
            sells = "incomplete" if offered.incomplete else "the item"
            return f"{sells} at {offered.price}"
        return found.trail[-1].reason if found.trail else "nothing"

    return read


def _listed(page: ProductPage) -> ListedProduct:
    return ListedProduct(name=page.name or page.url, url=page.url)


def brief_inputs() -> list[tuple[str, Read]]:
    return [(category, _brief_read(category)) for category in TERMS]


def _brief_read(category: str) -> Read:
    search = search_view(fixture_sources(), max_calls=4)

    async def read(chat: ChatModel) -> Any:
        outcomes = [
            await search(template.format(category=category), purpose)
            for purpose, template in SEARCH_TEMPLATES.items()
        ]
        results = distinct_results(result for outcome in outcomes for result in outcome.results)
        found = await brief_agent._read(category, results, chat)
        return sorted(f"{cited.factor.kind}: {cited.result.url}" for cited in found.cited) or [
            "no factor kept"
        ]

    return read


def evidence_inputs() -> list[tuple[str, Read]]:
    return [(name, _evidence_read(category, name, brand)) for category, name, brand in EVIDENCE]


def _evidence_read(category: str, fixture: str, brand: str) -> Read:
    path = FIXTURES_FOLDER / Service.TAVILY / f"{fixture}.json"
    stored = StoredResponse.model_validate_json(path.read_text(encoding="utf-8"))
    query = stored.request["search_query"]
    name = query.removesuffix(" durability lifespan warranty")
    option = ProductOption(id="option-1", name=name, brand=brand)

    async def search(
        search_query: str, purpose: SearchPurpose, *, follow_up: bool = False
    ) -> SearchOutcome:
        request = search_request(query, SearchPurpose.EVIDENCE, follow_up=True)
        return search_outcome(request, stored, from_cache=True)

    recorded: WebSearch = search

    async def read(chat: ChatModel) -> Any:
        subject = Subject(option)
        found = await option_evidence(subject, category, RECURRING[category], chat, recorded)
        kept = found.option
        evidence = kept.durability_evidence
        return {
            "lifespan": f"{kept.lifespan_years} ({kept.lifespan_source.kind})"
            if kept.lifespan_source
            else None,
            "warranty": None if evidence.warranty is None else str(evidence.warranty.value),
            "repairability": evidence.repairability is not None,
            "wear_material": evidence.wear_material is not None,
            "care": evidence.care is not None,
            "typical_lifespan": evidence.typical_lifespan is not None,
            "recurring": f"{kept.recurring_cost_state} {kept.recurring_cost_per_year}",
        }

    return read


# The frying pan pages of the replay test (tests/agents/tco/test_tco_pages.py), by fixture name.
RECORDED_PAGES = (
    "frying-pan-03-beslist-wmf-profi-resist-koekenpan-roestvrij-sta",
    "frying-pan-04-kieskeurig-tefal-trattoria-braadpan-24-cm-zwart-ind",
    "frying-pan-05-kieskeurig-greenchef-diamond-inductie-koekenpan-24",
    "frying-pan-08-kieskeurig-tefal-renew-black-on-keramische-hapjespa",
    "frying-pan-10-kieskeurig-tefal-xl-force-wokpan-28-cm-zwart",
)


async def record() -> int:
    async with httpx.AsyncClient() as client:
        real = nebius_chat(require(load_env(), NEBIUS_KEY_NAME), client)
        for name in RECORDED_PAGES:
            print(f"{name}: {await _record(name, real)}")
    return 0


async def _record(name: str, real: ChatModel) -> Any:
    path = FIXTURES_FOLDER / Service.FIRECRAWL / f"{name}-page.json"
    stored = StoredResponse.model_validate_json(path.read_text(encoding="utf-8"))
    url = stored.request["url"]
    page = product_page(page_request(url), stored, from_cache=True)
    sent: list[tuple[ChatRequest, str]] = []

    async def noting(request: ChatRequest) -> str:
        reply = await real(request)
        sent.append((request, reply))
        return reply

    found = await _page_read("frying pan", page)(noting)
    request, reply = sent[-1]
    recorded = {
        "model": request.model,
        "system": request.messages[0]["content"],
        "input": request.messages[1]["content"],
        "reply": reply,
        "recorded_on": datetime.now(UTC).date().isoformat(),
    }
    out = FIXTURES_FOLDER / "nebius" / f"page-read-{name}.json"
    out.write_text(json.dumps(recorded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return found


INPUTS = {"page": page_inputs, "brief": brief_inputs, "evidence": evidence_inputs}


# --- Running and showing ---


async def run(read_name: str, setting: str, reads: int) -> int:
    temperature = SETTINGS[setting]
    inputs = INPUTS[read_name]()
    limit = asyncio.Semaphore(AT_ONCE)
    calls_of_read: Calls = contextvars.ContextVar("calls_of_read")
    hooks = {"response": [noting_responses(calls_of_read)]}
    async with httpx.AsyncClient(event_hooks=hooks) as client:
        real = nebius_chat(require(load_env(), NEBIUS_KEY_NAME), client)
        chat = at_temperature(real, temperature)

        async def once(read: Read) -> dict[str, Any]:
            async with limit:
                calls: list[dict[str, Any]] = []
                calls_of_read.set(calls)
                outcome = await read(chat)
                return {"outcome": outcome, "calls": calls}

        per_input = [
            await asyncio.gather(*(once(read) for _ in range(reads))) for _, read in inputs
        ]
    stored = {
        "read": read_name,
        "setting": setting,
        "temperature": temperature,
        "run_at": datetime.now(UTC).isoformat(),
        "inputs": [
            {"input": name, "reads": result}
            for (name, _), result in zip(inputs, per_input, strict=True)
        ],
    }
    CHECK_FOLDER.mkdir(parents=True, exist_ok=True)
    (CHECK_FOLDER / f"{read_name}-{setting}.json").write_text(
        json.dumps(stored, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"{read_name} at {setting}: {len(inputs)} inputs, {reads} reads each")
    return 0


def show(read_name: str) -> int:
    for setting in SETTINGS:
        path = CHECK_FOLDER / f"{read_name}-{setting}.json"
        if path.is_file():
            stored = json.loads(path.read_text(encoding="utf-8"))
            print(f"\n## {read_name} at {setting}")
            print("\n".join(_shown(stored["inputs"])))
    return 0


def _shown(inputs: Sequence[dict[str, Any]]) -> list[str]:
    """Per input read, how many reads differ from its most common outcome and each outcome's
    count; then the totals, with the calls cut off, repeating or asked again."""
    lines: list[str] = []
    totals: Counter[str] = Counter()
    for each in (each for each in inputs if any(read["calls"] for read in each["reads"])):
        outcomes = Counter(json.dumps(read["outcome"], sort_keys=True) for read in each["reads"])
        reads = sum(outcomes.values())
        differ = reads - outcomes.most_common(1)[0][1]
        calls = [call for read in each["reads"] for call in read["calls"]]
        totals.update(
            differ=differ,
            reads=reads,
            cut=sum(call["finish_reason"] == "length" for call in calls),
            repeating=sum(bool(call["repeats"]) for call in calls),
            asked_again=sum(len(read["calls"]) > 1 for read in each["reads"]),
        )
        lines.append(f"- {each['input'][:90]}: {differ} of {reads} differ")
        lines.extend(f"    {n}x {outcome[:200]}" for outcome, n in outcomes.most_common())
    lines.append(
        f"TOTAL: {totals['differ']} of {totals['reads']} reads differ from their input's most "
        f"common outcome; {totals['cut']} calls cut off at max_tokens, {totals['repeating']} "
        f"repeating, {totals['asked_again']} reads asked again"
    )
    return lines


def main(arguments: Sequence[str]) -> int:
    match list(arguments):
        case ["run", read_name, setting, *rest] if read_name in INPUTS and setting in SETTINGS:
            return asyncio.run(run(read_name, setting, int(rest[0]) if rest else READS))
        case ["show", read_name] if read_name in INPUTS:
            return show(read_name)
        case ["record"]:
            return asyncio.run(record())
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
