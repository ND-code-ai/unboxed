"""The live check of task 1.8.4: which findings template, whether full page text, and how much
reasoning. Spends credits.

uv run python scripts/findings_check.py search A B
uv run python scripts/findings_check.py read <template> <snippets|full> <little|full>
uv run python scripts/findings_check.py show <template> <snippets|full> <little|full>
uv run python scripts/findings_check.py rest <template> <snippets|full> <little|full>
uv run python scripts/findings_check.py fixtures <template> <snippets|full> <little|full>

`search` makes the findings search of each checked product (`CHECKED`) with each template
named, asking for full page text, and stores the results in
`.cache/live/check_1_8_4/searches-<template>.json` (one credit each, none on a cache hit).
`read` runs the app's findings read and checks on those stored results, with the snippets only
or the full text, and little or full reasoning, and stores each read's reply, the findings kept
and the trail in `reads-<template>-<text>-<reasoning>.json`. `show` prints the kept findings
with their quotes, for checking by hand, and the drops per cause. `rest` searches and reads the
other recorded products (`REST`) with the chosen settings. `fixtures` writes, for all eighteen
products, the stored search as a fixture in tests/fixtures/tavily/ (the full text dropped when
snippets were chosen) and the read of the chosen settings in tests/fixtures/nebius/. The
design, the decision rule and the results are in docs/findings/task_1.8.4.md.
"""

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from types import MappingProxyType
from typing import Any

import httpx

from shopper.agents.tco import findings
from shopper.agents.tco.evidence import Subject
from shopper.agents.tco.prompt import FINDINGS_PROMPT
from shopper.config import (
    CACHE_FOLDER,
    FIXTURES_FOLDER,
    MODEL_IDS,
    NEBIUS_KEY_NAME,
    SEARCH_PURPOSE_PARAMETERS,
    SearchPurpose,
    load_env,
    require,
)
from shopper.llm import ChatModel, ChatRequest, nebius_chat
from shopper.state import ProductOption
from shopper.terminal.report_text import trail_line
from shopper.tools import search as search_tool
from shopper.tools.results import (
    SearchOutcome,
    SearchResult,
    Service,
    StoredResponse,
    WebSearch,
)
from shopper.tools.search import search_view
from shopper.tools.sources import live_sources

CHECK_FOLDER = CACHE_FOLDER / "live" / "check_1_8_4"
TEMPLATES = {
    "A": "{product} long term review durability",
    "B": "{product} owner review problems",
}
# (category, name, brand): three per tuned category, from the recorded price searches.
CHECKED = (
    ("frying pan", "Demeyere Atlantis", "Demeyere"),
    ("frying pan", "GreenPan Valencia Pro", "GreenPan"),
    ("frying pan", "Tramontina Professional", "Tramontina"),
    ("kettle", "Fellow Corvo EKG", "Fellow"),
    ("kettle", "Hario Buono", "Hario"),
    ("kettle", "Russell Hobbs Structure", "Russell Hobbs"),
    ("drill", "DeWalt DCD801QQ2", "DeWalt"),
    ("drill", "Makita GFD02D", "Makita"),
    ("drill", "Ryobi R18PD3-215GZ", "Ryobi"),
)
REST = (
    ("frying pan", "Fissler Original-Profi", "Fissler"),
    ("frying pan", "GreenPan Stanley Tucci", "GreenPan"),
    ("frying pan", "Legend Copper Core", "Legend"),
    ("kettle", "Chefman Glass Electric Kettle", "Chefman"),
    ("kettle", "Cuisinart CPK-17P1", "Cuisinart"),
    ("kettle", "OXO Brew Adjustable Temperature Kettle", "OXO"),
    ("drill", "Black+Decker BCD700S1K-GB", "Black+Decker"),
    ("drill", "Erbauer ECCD18-Li", "Erbauer"),
    ("drill", "Titan TTI884COM", "Titan"),
)
# The most specific mark first: a name or a summary reason also says "its quote".
CAUSES = (
    ("name", ("does not name",)),
    ("overlap", ("copies six",)),
    ("model_text", ("its summary", "it has no summary")),
    ("kind", ("is speaking",)),
    ("quote", ("its quote", "cites no search result")),
)
EU_ENDINGS = (
    ".nl", ".be", ".de", ".fr", ".it", ".es", ".at", ".ie", ".pl", ".se", ".dk", ".fi", ".pt",
    ".cz", ".lu", ".gr", ".eu",
)  # fmt: skip


def with_full_text() -> None:
    """The findings search asks for full page text, so both texts come from one credit."""
    parameters = dict(SEARCH_PURPOSE_PARAMETERS)
    parameters[SearchPurpose.FINDINGS] = MappingProxyType(
        {**SEARCH_PURPOSE_PARAMETERS[SearchPurpose.FINDINGS], "include_raw_content": "text"}
    )
    search_tool.SEARCH_PURPOSE_PARAMETERS = MappingProxyType(parameters)


async def search_all(labels: list[str], products: tuple[tuple[str, str, str], ...]) -> None:
    with_full_text()
    env = load_env()
    async with httpx.AsyncClient() as client:
        search = search_view(live_sources(env, client), 2 * len(products))
        for label in labels:
            outcomes = await asyncio.gather(
                *(
                    search(TEMPLATES[label].format(product=name), SearchPurpose.FINDINGS)
                    for _, name, _ in products
                )
            )
            stored = _stored_searches(label, broken_ok=True)
            stored.update(
                {
                    name: outcome.model_dump(mode="json")
                    for (_, name, _), outcome in zip(products, outcomes, strict=True)
                }
            )
            write_json(_searches_path(label), stored)
            credits = sum(outcome.credits for outcome in outcomes)
            print(f"template {label}: {len(outcomes)} searches, {credits} credits")


def _searches_path(label: str) -> Any:
    return CHECK_FOLDER / f"searches-{label}.json"


def _stored_searches(label: str, *, broken_ok: bool = False) -> dict[str, Any]:
    """The stored searches of a template. A file a crashed run left broken is started over when
    searching, since every search it held comes back from the cache."""
    path = _searches_path(label)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        if not broken_ok:
            raise
        print(f"{path} could not be read; starting it over")
        return {}


def write_json(path: Path, data: object) -> None:
    """Write through a temporary file, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    partial.replace(path)


def replaying(label: str, text: str) -> WebSearch:
    """The stored searches of one template, with the snippets only or the full text."""
    stored = {
        name: SearchOutcome.model_validate(outcome)
        for name, outcome in _stored_searches(label).items()
    }
    by_query = {outcome.search_query: outcome for outcome in stored.values()}

    async def search(query: str, purpose: SearchPurpose, *, follow_up: bool = False) -> Any:
        outcome = by_query[query.strip()]
        if text == "full":
            return outcome
        results = tuple(
            SearchResult.model_validate({**result.model_dump(), "raw_content": None})
            for result in outcome.results
        )
        return outcome.model_copy(update={"results": results})

    return search


def recording(chat: ChatModel, calls: dict[str, dict[str, str]]) -> ChatModel:
    async def recorded(request: ChatRequest) -> str:
        reply = await chat(request)
        if request.messages[0]["content"] == FINDINGS_PROMPT:
            product = request.messages[-1]["content"].splitlines()[0].removeprefix("Product: ")
            calls[product] = {"input": request.messages[-1]["content"], "reply": reply}
        return reply

    return recorded


async def read_all(
    label: str, text: str, reasoning: str, products: tuple[tuple[str, str, str], ...]
) -> None:
    env = load_env()
    calls: dict[str, dict[str, str]] = {}
    chat = recording(nebius_chat(require(env, NEBIUS_KEY_NAME)), calls)
    search = replaying(label, text)
    subjects = [
        (category, Subject(ProductOption(id=f"option-{n}", name=name, brand=brand)))
        for n, (category, name, brand) in enumerate(products, start=1)
    ]
    found = await asyncio.gather(
        *(
            findings.option_findings(
                subject,
                category,
                chat,
                search,
                template=TEMPLATES[label],
                low_effort=reasoning == "little",
            )
            for category, subject in subjects
        )
    )
    path = _reads_path(label, text, reasoning)
    stored = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for (category, subject), each in zip(subjects, found, strict=True):
        name = subject.option.name
        stored[name] = {
            "category": category,
            "state": each.state,
            "findings": [finding.model_dump(mode="json") for finding in each.findings],
            "trail": [trail_line(entry) for entry in each.trail],
            "call": calls.get(name),
        }
    write_json(path, stored)
    print(f"{label} {text} {reasoning}: {len(found)} reads in {path}")


def _reads_path(label: str, text: str, reasoning: str) -> Any:
    return CHECK_FOLDER / f"reads-{label}-{text}-{reasoning}.json"


def show(label: str, text: str, reasoning: str) -> None:
    stored = json.loads(_reads_path(label, text, reasoning).read_text(encoding="utf-8"))
    causes: Counter[str] = Counter()
    kept = eu = 0
    for name, read in stored.items():
        print(f"\n=== {name} ({read['category']}): {read['state']}")
        replies = json.loads(read["call"]["reply"])["findings"] if read["call"] else []
        quotes = {each["summary"].strip(): each for each in replies}
        for finding in read["findings"]:
            kept += 1
            url = finding["source"]["reference"]
            eu += url.split("/")[2].endswith(EU_ENDINGS)
            given = quotes.get(finding["summary"], {})
            print(f"  [{finding['kind']}] {finding['summary']}")
            print(f"      quote: {given.get('quote')!r}")
            print(f"      rating: {finding['rating']} ({finding['review_count']}) {url}")
        for line in read["trail"]:
            if "excluded: Left out" in line:
                reason = line.split("reason: ", 1)[1]
                print(f"  dropped: {reason}")
                causes[_cause(reason)] += 1
    print(f"\nkept {kept}, from EU or Dutch sites {eu}; dropped by cause {dict(causes)}")


def write_fixtures(label: str, text: str, reasoning: str) -> None:
    searches = _stored_searches(label)
    reads = json.loads(_reads_path(label, text, reasoning).read_text(encoding="utf-8"))
    for category, name, _ in (*CHECKED, *REST):
        outcome = searches[name]
        results = [
            {key: value for key, value in result.items() if value is not None}
            | ({} if text == "full" else {"raw_content": None})
            for result in outcome["results"]
        ]
        request = search_tool.search_request(outcome["search_query"], SearchPurpose.FINDINGS)
        stored = StoredResponse(
            service=Service.TAVILY,
            request={
                "search_query": request.search_query,
                "purpose": request.purpose,
                "parameters": dict(request.parameters),
            },
            retrieved_at=outcome["retrieved_at"],
            response={"query": request.search_query, "results": results},
        )
        slug = _slug(name)
        tavily = FIXTURES_FOLDER / "tavily" / f"{_slug(category)}-findings-{slug}.json"
        tavily.write_text(stored.model_dump_json(indent=2) + "\n", encoding="utf-8")
        call = reads[name]["call"]
        if call is not None:
            nebius = FIXTURES_FOLDER / "nebius" / f"findings-{slug}.json"
            recorded = {
                "model": MODEL_IDS[findings.FINDINGS_TIER],
                "input": call["input"],
                "reply": call["reply"],
                "recorded_on": outcome["retrieved_at"][:10],
            }
            nebius.write_text(
                json.dumps(recorded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
    print(f"fixtures written for {len(CHECKED) + len(REST)} products")


def _slug(text: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in text.lower()).split())


def _cause(reason: str) -> str:
    return next(
        (cause for cause, marks in CAUSES if any(mark in reason for mark in marks)), "other"
    )


def main(arguments: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    command, *rest = arguments
    if command == "search":
        asyncio.run(search_all(rest, CHECKED))
    elif command == "read":
        asyncio.run(read_all(*rest, CHECKED))
    elif command == "show":
        show(*rest)
    elif command == "fixtures":
        write_fixtures(*rest)
    elif command == "rest":
        label, text, reasoning = rest
        asyncio.run(search_all([label], REST))
        asyncio.run(read_all(label, text, reasoning, REST))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
