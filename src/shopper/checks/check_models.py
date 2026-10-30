"""Live check of the model tiers. Spends credits; run it on purpose.

uv run python -m shopper.checks.check_models
    one completion and one structured result per tier
uv run python -m shopper.checks.check_models --compare
    small tier against its alternative on parsing
"""

import asyncio
import sys
import time
from typing import get_args

from pydantic import BaseModel, ConfigDict

from shopper.agents.supervisor.agent import SUPERVISOR_PROMPT, SUPERVISOR_TEMPERATURE, Extraction
from shopper.config import (
    MODEL_IDS,
    NEBIUS_KEY_NAME,
    SMALL_TIER_ALTERNATIVE,
    MissingSettingError,
    Tier,
    load_env,
    require,
)
from shopper.llm import (
    ChatModel,
    ChatRequest,
    Completion,
    LlmFailure,
    complete,
    complete_structured,
    nebius_chat,
)

COMPLETION_PROMPT = "In one short sentence, what is a cast-iron frying pan good for?"

# (input, expected budget amount, expected scope); parsed with the supervisor's own prompt.
PARSE_CASES: tuple[tuple[str, float | None, str], ...] = (
    ("I need a new frying pan, budget 50 euro", 50, "tuned"),
    ("Ik zoek een stofzuiger tot €150", 150, "tuned"),
    ("cordless drill for occasional DIY", None, "tuned"),
    ("a new fridge, max 600", 600, "energy_heavy"),
    ("winter boots under 120 euros", 120, "clothing"),
    ("weekly meal box subscription", None, "not_a_product"),
    ("office chair, around €200", 200, "general"),
    ("https://www.bol.com/nl/nl/p/tefal-koekenpan-28-cm/9200000012345/", None, "tuned"),
)
COMPARE_ROUNDS = 2


class ParseOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    first_try: bool
    correct: bool
    seconds: float


def with_model(chat: ChatModel, model: str) -> ChatModel:
    async def chat_with_model(request: ChatRequest) -> str:
        return await chat(request.model_copy(update={"model": model}))

    return chat_with_model


async def check_tier(chat: ChatModel, tier: Tier) -> bool:
    text = await complete(chat, tier, COMPLETION_PROMPT)
    parsed = await _extract(chat, tier, PARSE_CASES[0][0])
    print(f"[{tier}] {MODEL_IDS[tier]}")
    print(f"  completion: {_show(text)}")
    print(f"  structured: {_show(parsed)}")
    return isinstance(text, Completion) and isinstance(parsed, Completion)


async def parse_once(chat: ChatModel, case: tuple[str, float | None, str]) -> ParseOutcome:
    input_text, budget, scope = case
    calls = 0

    async def counting_chat(request: ChatRequest) -> str:
        nonlocal calls
        calls += 1
        return await chat(request)

    start = time.perf_counter()
    result = await _extract(counting_chat, "small", input_text)
    seconds = time.perf_counter() - start
    valid = isinstance(result, Completion)
    correct = valid and result.value.budget_amount == budget and result.value.scope == scope
    if not correct:
        print(f"    miss on {input_text!r}: {_show(result)}")
    return ParseOutcome(
        valid=valid, first_try=valid and calls == 1, correct=correct, seconds=seconds
    )


async def _extract(
    chat: ChatModel, tier: Tier, input_text: str
) -> Completion[Extraction] | LlmFailure:
    return await complete_structured(
        chat,
        tier,
        input_text,
        Extraction,
        system=SUPERVISOR_PROMPT,
        temperature=SUPERVISOR_TEMPERATURE,
    )


async def compare_small(chat: ChatModel) -> None:
    for model in (MODEL_IDS["small"], SMALL_TIER_ALTERNATIVE):
        print(f"{model}")
        outcomes = await asyncio.gather(
            *(
                parse_once(with_model(chat, model), case)
                for _ in range(COMPARE_ROUNDS)
                for case in PARSE_CASES
            )
        )
        seconds = sorted(outcome.seconds for outcome in outcomes)
        print(
            f"  schema-valid {sum(o.valid for o in outcomes)}/{len(outcomes)}, "
            f"valid on first try {sum(o.first_try for o in outcomes)}/{len(outcomes)}, "
            f"budget and scope correct {sum(o.correct for o in outcomes)}/{len(outcomes)}, "
            f"median {seconds[len(seconds) // 2]:.1f} s, slowest {seconds[-1]:.1f} s"
        )


def _show(result: Completion | LlmFailure) -> str:
    if isinstance(result, LlmFailure):
        return f"FAILED ({result.kind}): {result.detail}"
    value = result.value
    return value.model_dump_json() if isinstance(value, BaseModel) else value.strip()


async def main(arguments: list[str]) -> int:
    try:
        chat = nebius_chat(require(load_env(), NEBIUS_KEY_NAME))
    except MissingSettingError as error:
        print(error)
        return 1
    if "--compare" in arguments:
        await compare_small(chat)
        return 0
    passed = [await check_tier(chat, tier) for tier in get_args(Tier)]
    return 0 if all(passed) else 1


if __name__ == "__main__":
    # Piped output on Windows defaults to cp1252, which cannot encode all model text.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main(sys.argv[1:])))
