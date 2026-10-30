"""The two durability judgements of option research: by the candidates' listed names, before
any product page is read, and by the product pages of the candidates read, which decides the
slots. Both are the model's own view, never a sourced figure, and only order candidates. Rules:
docs/architecture/option_research.md ("Durability judgement").
"""

from collections.abc import Sequence

from shopper import wording
from shopper.agents.tco.checks import judgement_fault
from shopper.agents.tco.models import (
    UNKNOWN,
    Candidate,
    Judgement,
    NamesJudged,
    NamesJudgement,
    Offered,
    PagesJudged,
    PagesJudgement,
    ReadJudgement,
)
from shopper.agents.tco.prompt import (
    JUDGE_NAME,
    JUDGE_NAMES_INPUT,
    JUDGE_NAMES_PROMPT,
    JUDGE_PAGE,
    JUDGE_PAGES_INPUT,
    JUDGE_PAGES_PROMPT,
)
from shopper.agents.tco.trail import by_model, entry, model_call_failed
from shopper.config import (
    OPTION_RESEARCH_MAX_TOKENS,
    OPTION_RESEARCH_TIMEOUT_SECONDS,
    RAW_CONTENT_MAX_CHARACTERS,
    Tier,
)
from shopper.llm import ChatModel, Completion, LlmFailure, complete_structured
from shopper.state import TrailEntry, TrailKind

JUDGEMENT_TIER: Tier = "medium"
# Both judgements reason in full, as the shortlist that judged before them did (task 1.8.3).
JUDGEMENT_LOW_EFFORT = False


async def judged_by_name(
    category: str, candidates: Sequence[Candidate], chat: ChatModel
) -> NamesJudgement:
    """Each candidate's judgement from its listed name, and whether the category is a set; a
    failed call leaves every judgement unknown and no set asked for."""
    if not candidates:
        return NamesJudgement((), False, ())
    products = "\n".join(
        JUDGE_NAME.format(number=each.number, name=each.listed.name) for each in candidates
    )
    reply = await _judge(
        JUDGE_NAMES_INPUT.format(category=category, products=products),
        NamesJudged,
        JUDGE_NAMES_PROMPT,
        chat,
    )
    if isinstance(reply, LlmFailure):
        failed = model_call_failed("judge the candidates by their names", reply)
        return NamesJudgement(tuple(candidates), False, (failed,))
    judged = _judgements(reply.value.candidates, len(candidates))
    return NamesJudgement(
        tuple(
            each._replace(judgement=judged.get(each.number, (UNKNOWN, None))[0])
            for each in candidates
        ),
        reply.value.set_requested,
        _trail(
            "by its name", [(each.number, each.listed.name) for each in candidates], judged, reply
        ),
    )


async def judged_by_page(
    category: str, offered: Sequence[Offered], chat: ChatModel
) -> PagesJudgement:
    """Each candidate read, judged again from its product page; a failed call leaves every
    judgement unknown, so the slots are filled by price."""
    if not offered:
        return PagesJudgement((), ())
    products = "\n\n".join(
        JUDGE_PAGE.format(
            number=number, name=each.name, text=each.page.markdown[:RAW_CONTENT_MAX_CHARACTERS]
        )
        for number, each in enumerate(offered, start=1)
    )
    reply = await _judge(
        JUDGE_PAGES_INPUT.format(category=category, products=products),
        PagesJudged,
        JUDGE_PAGES_PROMPT,
        chat,
    )
    if isinstance(reply, LlmFailure):
        failed = model_call_failed("judge the candidates by their product pages", reply)
        return PagesJudgement(
            tuple(each._replace(judgement=UNKNOWN) for each in offered), (failed,)
        )
    judged = _judgements(reply.value.candidates, len(offered))
    return PagesJudgement(
        tuple(
            each._replace(judgement=judged.get(number, (UNKNOWN, None))[0])
            for number, each in enumerate(offered, start=1)
        ),
        _trail(
            "by its product page",
            [(number, each.name) for number, each in enumerate(offered, start=1)],
            judged,
            reply,
        ),
    )


async def _judge[T: NamesJudged | PagesJudged](
    prompt: str, schema: type[T], system: str, chat: ChatModel
) -> Completion[T] | LlmFailure:
    return await complete_structured(
        chat,
        JUDGEMENT_TIER,
        prompt,
        schema,
        system=system,
        max_tokens=OPTION_RESEARCH_MAX_TOKENS,
        timeout=OPTION_RESEARCH_TIMEOUT_SECONDS,
        low_effort=JUDGEMENT_LOW_EFFORT,
    )


def _judgements(
    read: Sequence[ReadJudgement], count: int
) -> dict[int, tuple[Judgement, str | None]]:
    """Each numbered candidate's judgement, with why it counts as unknown when it does; the first
    judgement for a number counts, and one for a number not shown is ignored."""
    judged: dict[int, tuple[Judgement, str | None]] = {}
    for each in read:
        if not 1 <= each.candidate <= count or each.candidate in judged:
            continue
        fault = judgement_fault(each)
        if fault is not None:
            judged[each.candidate] = (UNKNOWN, fault)
            continue
        reason = (each.durability_reason or "").strip() or None
        judged[each.candidate] = (Judgement(each.durability_judgement or "unknown", reason), None)
    return judged


def _trail[T: NamesJudged | PagesJudged](
    how: str,
    named: Sequence[tuple[int, str]],
    judged: dict[int, tuple[Judgement, str | None]],
    reply: Completion[T],
) -> tuple[TrailEntry, ...]:
    """One entry per candidate: its judgement, or why it counts as unknown."""
    return tuple(
        by_model(
            entry(
                TrailKind.FOUND,
                f'Judged "{name}" {how}: '
                + wording.JUDGED.format(judgement=judgement_words(judgement)),
                reason=fault,
            ),
            reply,
        )
        for number, name in named
        for judgement, fault in (
            judged.get(number, (UNKNOWN, "no durability judgement was given")),
        )
    )


def judgement_words(judgement: Judgement) -> str:
    """The durability judgement as the trail states it, with its reason when it gives one;
    never on the report."""
    return (
        judgement.value if judgement.reason is None else f"{judgement.value} ({judgement.reason})"
    )
