"""The timed probe of task 1.9.7: one tier 3 estimate on the large model, reasoning in full, and
the same call once with `low_effort`. Spends Nebius credits.

uv run python scripts/lca_probe.py

Prints the time, the completion tokens and whether a reasoning text came back for each call,
and writes the full call's input and reply to `tests/fixtures/nebius/lca-kettles.json`. The
results are in docs/findings/task_1.9.7.md.
"""

import asyncio
import json
import time
from decimal import Decimal
from typing import Any

import openai

from shopper.agents.lca.agent import estimate_input
from shopper.agents.lca.models import EstimateReply
from shopper.agents.lca.prompt import ESTIMATE_PROMPT
from shopper.config import (
    FIXTURES_FOLDER,
    LCA_MAX_TOKENS,
    LCA_TIMEOUT_SECONDS,
    LOW_EFFORT_REQUEST,
    MODEL_IDS,
    NEBIUS_BASE_URL,
    NEBIUS_KEY_NAME,
    load_env,
    require,
)
from shopper.state import Material, ProductOption, Source, SourceKind

PAGE = Source(kind=SourceKind.URL, reference="https://shop.example/russell-hobbs-structure")
OPTIONS = (
    ProductOption(
        id="option-link",
        name="Russell Hobbs Structure waterkoker 28081-70",
        brand="Russell Hobbs",
        materials=(
            Material(name="plastic", source=PAGE),
            Material(name="stainless steel", source=PAGE),
        ),
        weight_kg=Decimal("1.1"),
        weight_source=PAGE,
    ),
    ProductOption(id="option-1", name="Fellow Corvo EKG", brand="Fellow"),
    ProductOption(id="option-2", name="Bosch TWK3A011", brand="Bosch"),
)
RECORDED = FIXTURES_FOLDER / "nebius" / "lca-kettles.json"


async def probe(client: openai.AsyncOpenAI, prompt: str, low_effort: bool) -> dict[str, Any]:
    extra = {name: dict(value) for name, value in LOW_EFFORT_REQUEST.items()}
    started = time.monotonic()
    response = await client.chat.completions.create(
        model=MODEL_IDS["large"],
        messages=[
            {"role": "system", "content": ESTIMATE_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=LCA_MAX_TOKENS,
        timeout=LCA_TIMEOUT_SECONDS,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "result",
                "schema": EstimateReply.model_json_schema(),
                "strict": True,
            },
        },
        extra_body=extra if low_effort else None,
    )
    seconds = time.monotonic() - started
    message = response.choices[0].message
    reasoning = getattr(message, "reasoning_content", None) or ""
    reply = message.content or ""
    try:
        EstimateReply.model_validate_json(reply)
        valid = True
    except ValueError:
        valid = False
    usage = response.usage
    return {
        "low_effort": low_effort,
        "seconds": round(seconds, 1),
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "reasoning_characters": len(reasoning),
        "finish_reason": response.choices[0].finish_reason,
        "valid": valid,
        "reply": reply,
    }


async def main() -> None:
    key = require(load_env(), NEBIUS_KEY_NAME)
    client = openai.AsyncOpenAI(base_url=NEBIUS_BASE_URL, api_key=key, max_retries=0)
    prompt = estimate_input(OPTIONS)
    full = await probe(client, prompt, low_effort=False)
    low = await probe(client, prompt, low_effort=True)
    for run in (full, low):
        shown = {name: value for name, value in run.items() if name != "reply"}
        print(json.dumps(shown))
    print(full["reply"])
    print(low["reply"])
    recorded = {"model": MODEL_IDS["large"], "input": prompt, "reply": full["reply"]}
    RECORDED.write_text(json.dumps(recorded, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
