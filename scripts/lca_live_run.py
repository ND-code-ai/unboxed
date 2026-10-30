"""The live run of task 1.9.8: the terminal app with --skip-all on the three tuned categories
and a cordless tool, then one estimate of the two stub frying pans. Spends Nebius, Tavily and
Firecrawl credits.

uv run python scripts/lca_live_run.py <output folder>

Writes each run's printed report to `<output folder>/<name>.txt`, and each LCA call's input,
reply, time and tokens to `tests/fixtures/nebius/lca-<name>.json`. The stub pans' estimate is
the recorded reply of the offline CLI tests. The results are in docs/findings/task_1.9.8.md.
"""

import asyncio
import contextlib
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import openai

from shopper.agents.lca.agent import estimate_co2e
from shopper.agents.lca.prompt import ESTIMATE_PROMPT
from shopper.agents.stubs import CARBON_STEEL_PAN, NON_STICK_PAN
from shopper.config import FIXTURES_FOLDER, NEBIUS_BASE_URL, NEBIUS_KEY_NAME, load_env, require
from shopper.llm import ChatError, ChatModel, ChatRequest, ChatTimeoutError, nebius_chat
from shopper.terminal.cli import run
from shopper.tools.sources import sources_from_env

RUNS = {
    "frying-pan": "I need a new frying pan, budget 50 euro",
    "kettle": "I need a new kettle",
    "drill": "I need a drill for putting up shelves",
    "cordless-screwdriver": "a cordless screwdriver, budget 80 euro",
}


def recording(key: str, calls: list[dict[str, Any]]) -> ChatModel:
    """The real model; each LCA call is sent here as well, to keep its time and tokens."""
    plain = nebius_chat(key)
    client = openai.AsyncOpenAI(base_url=NEBIUS_BASE_URL, api_key=key, max_retries=1)

    async def chat(request: ChatRequest) -> str:
        if request.messages[0]["content"] != ESTIMATE_PROMPT:
            return await plain(request)
        started = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=request.model,
                messages=list(request.messages),
                max_tokens=request.max_tokens,
                timeout=request.timeout,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "result",
                        "schema": request.json_schema,
                        "strict": True,
                    },
                },
            )
        except openai.APITimeoutError as error:
            calls.append({"failed": "timeout", "seconds": round(time.monotonic() - started, 1)})
            raise ChatTimeoutError(str(error)) from error
        except openai.OpenAIError as error:
            calls.append({"failed": str(error), "seconds": round(time.monotonic() - started, 1)})
            raise ChatError(str(error)) from error
        usage = response.usage
        reply = response.choices[0].message.content or ""
        calls.append(
            {
                "model": request.model,
                "input": request.messages[1]["content"],
                "reply": reply,
                "seconds": round(time.monotonic() - started, 1),
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "completion_tokens": usage.completion_tokens if usage else None,
                "finish_reason": response.choices[0].finish_reason,
            }
        )
        return reply

    return chat


def record(name: str, calls: list[dict[str, Any]]) -> None:
    path = FIXTURES_FOLDER / "nebius" / f"lca-{name}.json"
    first = calls[0] if len(calls) == 1 else {"calls": calls}
    path.write_text(json.dumps(first, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


async def main(folder: Path) -> None:
    env = load_env()
    key = require(env, NEBIUS_KEY_NAME)
    folder.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        for name, text in RUNS.items():
            calls: list[dict[str, Any]] = []
            printed = io.StringIO()
            started = time.monotonic()
            with contextlib.redirect_stdout(printed):
                status = await run(
                    text, recording(key, calls), sources_from_env(env, client), skip_all=True
                )
            seconds = round(time.monotonic() - started, 1)
            (folder / f"{name}.txt").write_text(printed.getvalue(), encoding="utf-8")
            if calls:
                record(name, calls)
            timings = [call.get("seconds") for call in calls]
            print(f"{name}: exit {status}, {seconds} s, LCA calls {timings}", file=sys.stderr)
    calls = []
    await estimate_co2e((NON_STICK_PAN, CARBON_STEEL_PAN), recording(key, calls))
    record("stub-pans", calls)
    print(f"stub-pans: LCA calls {[call.get('seconds') for call in calls]}", file=sys.stderr)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    asyncio.run(main(Path(sys.argv[1])))
