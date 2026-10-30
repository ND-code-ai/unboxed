"""Step 7 of option research: one findings search per product option and one read of its
results, for up to three short reports of how the option held up for a tester or an owner.

Findings are shown and feed nothing. A finding is a summary in the read's own words; its quote is
checked, written to a debug line on the `shopper.findings` logger and dropped, so it is never on
the option or the trail (docs/adr/0005-findings-summarised-quote-logged.md). Rules:
docs/architecture/option_evidence.md ("Findings").
"""

import logging
from typing import NamedTuple

from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.research import distinct_results, full_text, numbered, stands_in
from shopper.agents.tco.checks import names_product, text_of
from shopper.agents.tco.evidence import Evidenced, Subject
from shopper.agents.tco.evidence_checks import brand_fault, in_two_parts, passage
from shopper.agents.tco.finding_checks import (
    copied_fault,
    rating_in,
    scored_aspect,
    summary_fault,
)
from shopper.agents.tco.models import EvidenceContext, FindingsReading, ReadFinding
from shopper.agents.tco.prompt import FINDINGS_INPUT, FINDINGS_PROMPT
from shopper.agents.tco.trail import by_model, counted, entry, left_out_of, searched
from shopper.calc.reviews import review_count
from shopper.config import (
    FINDINGS_MAX_TOKENS,
    FINDINGS_TEMPLATE,
    FINDINGS_TIMEOUT_SECONDS,
    MAX_FINDINGS,
    SearchPurpose,
    Tier,
)
from shopper.llm import ChatModel, Completion, LlmFailure, complete_structured
from shopper.state import (
    Finding,
    FindingKind,
    FindingsState,
    Source,
    SourceKind,
    StatedBy,
    TrailEntry,
    TrailKind,
)
from shopper.tools.results import FailureKind, WebSearch

FINDINGS_TIER: Tier = "medium"
# Chosen in the live check of task 1.8.4 (docs/findings/task_1.8.4.md).
FINDINGS_LOW_EFFORT = True
KINDS = {StatedBy.TESTER: FindingKind.TEST, StatedBy.OWNER: FindingKind.OWNER_REPORT}
# How the trail names each kind; the report's words are in wording.py.
TRAIL_LABELS = {FindingKind.TEST: "Test", FindingKind.OWNER_REPORT: "Owner report"}
NOT_IN_RESULT = "its quote is not in the search result"
NOT_FINDINGS = {StatedBy.MANUFACTURER: "the manufacturer", StatedBy.SELLER: "a seller"}
LINE_ONLY = "the passage of its quote names the line, not the product"

logger = logging.getLogger("shopper.findings")


class Found(NamedTuple):
    """What the findings step gives an option: the findings, the state that says why there are
    none, and the trail."""

    findings: tuple[Finding, ...]
    state: FindingsState
    trail: tuple[TrailEntry, ...]


class Rated(NamedTuple):
    """A finding's rating and review count, or why its rating is left out."""

    rating: str | None = None
    review_count: int | None = None
    fault: str | None = None


def with_findings(evidenced: Evidenced, found: Found) -> Evidenced:
    """The option's evidence with its findings merged in after it; an option the evidence
    removed loses its findings and their trail, since it has no block on the report."""
    if evidenced.removed:
        return evidenced
    option = evidenced.option
    evidence = option.durability_evidence.model_copy(
        update={"findings": found.findings, "findings_state": found.state}
    )
    return evidenced._replace(
        option=option.model_copy(update={"durability_evidence": evidence}),
        trail=(*evidenced.trail, *found.trail),
    )


async def option_findings(
    subject: Subject,
    category: str | None,
    chat: ChatModel,
    search: WebSearch,
    *,
    template: str = FINDINGS_TEMPLATE,
    low_effort: bool = FINDINGS_LOW_EFFORT,
) -> Found:
    """Up to three findings for the option, the first that pass the checks in the order the read
    named them.

    The search query holds a name a model or a page wrote, so it is searched as a model's query.
    `template` and `low_effort` are the config's; the live check of task 1.8.4 passes the ones it
    compares.
    """
    option = subject.option
    if option.brand is None:
        return Found((), FindingsState.NOT_SEARCHED, (_no_brand(option.name),))
    outcome = await search(
        template.format(product=option.name), SearchPurpose.FINDINGS, follow_up=True
    )
    if outcome.failure is not None:
        state = (
            FindingsState.NONE_FOUND
            if outcome.failure is FailureKind.NOT_FOUND
            else FindingsState.NOT_SEARCHED
        )
        return Found((), state, (searched(outcome),))
    results = tuple(full_text(result) for result in distinct_results(outcome.results))
    context = EvidenceContext(option, option.brand, category or "", results)
    reply = await _read(context, chat, low_effort)
    if isinstance(reply, LlmFailure):
        failed = entry(
            TrailKind.EXCLUDED,
            f'Could not read the owner and tester reports for "{option.name}"',
            reason=f"the model call failed ({reply.kind})",
        )
        return Found((), FindingsState.NOT_SEARCHED, (searched(outcome), by_model(failed, reply)))
    kept, checked = checked_findings(context, reply.value)
    read = entry(
        TrailKind.FOUND,
        f'Read the owner and tester reports for "{option.name}": '
        f"{counted(len(kept), 'finding')} kept of {len(reply.value.findings)} given, "
        f"{counted(len(results), 'result')} shown",
    )
    trail = (read, *checked, *_gaps(option.name, reply.value))
    state = FindingsState.FOUND if kept else FindingsState.NONE_FOUND
    return Found(kept, state, (searched(outcome), *(by_model(each, reply) for each in trail)))


async def _read(
    context: EvidenceContext, chat: ChatModel, low_effort: bool
) -> Completion[FindingsReading] | LlmFailure:
    return await complete_structured(
        chat,
        FINDINGS_TIER,
        FINDINGS_INPUT.format(
            name=context.option.name,
            brand=context.brand,
            category=context.category or "not known",
            results=numbered(context.results),
        ),
        FindingsReading,
        system=FINDINGS_PROMPT,
        max_tokens=FINDINGS_MAX_TOKENS,
        timeout=FINDINGS_TIMEOUT_SECONDS,
        low_effort=low_effort,
    )


def checked_findings(
    context: EvidenceContext, reading: FindingsReading
) -> tuple[tuple[Finding, ...], tuple[TrailEntry, ...]]:
    """The findings that pass the checks, at most three and one per cited result, and a trail
    entry for each finding and rating, kept or left out. Each quote goes to the debug log."""
    name = context.option.name
    kept: list[Finding] = []
    trail: list[TrailEntry] = []
    cited: set[int] = set()
    for read in reading.findings:
        fault = (
            f"at most {MAX_FINDINGS} findings are kept"
            if len(kept) >= MAX_FINDINGS
            else finding_fault(context, read, cited)
        )
        logger.debug(
            'Finding for "%s", result %d: "%s"; %s', name, read.result, read.quote, fault or "kept"
        )
        if fault is not None:
            trail.append(left_out_of(name, "a finding", fault))
            continue
        cited.add(read.result)
        finding, rated = _finding(context, read)
        kept.append(finding)
        trail.append(_found(context, read, finding))
        if rated.fault is not None:
            trail.append(left_out_of(name, "the rating of a finding", rated.fault))
    return tuple(kept), tuple(trail)


def finding_fault(context: EvidenceContext, read: ReadFinding, cited: set[int]) -> str | None:
    """Why a finding is left out: who is speaking, its quote, its name, its summary."""
    results = context.results
    if read.stated_by in NOT_FINDINGS:
        return f"{NOT_FINDINGS[read.stated_by]} is speaking, so it is no test or owner report"
    if read.on_shop_page:
        return "it comes from a shop's page, whose reviews are not used"
    if not 1 <= read.result <= len(results):
        return "it cites no search result that was shown"
    if read.result in cited:
        return "an earlier finding cites the same search result"
    if in_two_parts(read.quote):
        return "its quote is in two parts"
    if not read.quote.strip() or not stands_in(read.quote, results[read.result - 1]):
        return NOT_IN_RESULT
    fault = brand_fault(context, read.result, read.quote, about="line")
    if fault is not None:
        return fault
    fault = summary_fault(read.summary, read.quote)
    if fault is not None:
        return fault
    seen = tuple(text_of(result) for result in results)
    return copied_fault(read.summary, seen, (*_split(context.brand), *_split(context.option.name)))


def _split(text: str | None) -> tuple[str, ...]:
    return tuple((text or "").split())


def _finding(context: EvidenceContext, read: ReadFinding) -> tuple[Finding, Rated]:
    kind = KINDS[read.stated_by]
    result = context.results[read.result - 1]
    rated = _rated(context, read, kind)
    finding = Finding(
        kind=kind,
        summary=" ".join(read.summary.split()),
        source=Source(kind=SourceKind.URL, reference=result.url, stated_by=read.stated_by),
        rating=rated.rating,
        review_count=rated.review_count,
        published_date=result.published_date,
    )
    return finding, rated


def _rated(context: EvidenceContext, read: ReadFinding, kind: FindingKind) -> Rated:
    """The rating from its own quote in the same result, checked on its own: in one piece, in a
    passage that names the product (a neighbouring model's stars mislead), with a value on a
    scale for the product as a whole, not for one aspect such as its durability; an owner
    report's only with its review count."""
    quote = (read.rating_quote or "").strip()
    if not quote:
        return Rated()
    result = context.results[read.result - 1]
    if in_two_parts(quote) or not stands_in(quote, result):
        return Rated(fault=NOT_IN_RESULT)
    if brand_fault(context, read.result, quote) is not None:
        return Rated(fault="it is for another product")
    rating = rating_in(quote)
    if rating is None:
        return Rated(fault="it states no value on a scale")
    aspect = scored_aspect(quote)
    if aspect is not None:
        return Rated(fault=f"it scores {aspect}, not the product as a whole")
    if kind is FindingKind.TEST:
        return Rated(rating)
    count = review_count(quote)
    if count is None:
        return Rated(fault="an owner's rating is kept only with its number of reviews")
    return Rated(rating, count)


def _found(context: EvidenceContext, read: ReadFinding, finding: Finding) -> TrailEntry:
    """A kept finding's entry: its summary and source, never its quote; it says so when the
    passage names only the product's line."""
    names = names_product(
        passage(read.quote, context.results[read.result - 1]),
        context.brand or "",
        context.option.name,
        context.category,
    )
    return entry(
        TrailKind.FOUND,
        f'{TRAIL_LABELS[finding.kind]} for "{context.option.name}": {finding.summary}',
        reason=None if names else LINE_ONLY,
        source=finding.source,
    )


def _no_brand(name: str) -> TrailEntry:
    return entry(
        TrailKind.DECIDED,
        f'Did not look up owner and tester reports for "{name}"',
        reason="its product page names no brand, so no report can be checked to name it",
    )


def _gaps(name: str, reading: FindingsReading) -> tuple[TrailEntry, ...]:
    return tuple(
        entry(
            TrailKind.DECIDED,
            f'No owner or tester report of "{name}": {gap.what.strip()}',
            reason=gap.reason.strip(),
        )
        for gap in reading.gaps
        if gap.what.strip()
        and gap.reason.strip()
        and fault_in(gap.what) is None
        and fault_in(gap.reason) is None
    )
