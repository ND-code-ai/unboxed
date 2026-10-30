"""The brief agent: research a category's decision factors and draw the questions from them.

Code runs the loop: it searches, gives the results to the model and checks what comes back. Rules:
docs/architecture/category_brief.md, docs/architecture/interview.md and
docs/architecture/data_sources.md ("Research rules"). This module knows nothing of the graph.
"""

import asyncio
import hashlib
from collections.abc import Sequence

from shopper import wording
from shopper.agents.brief.checks import (
    factor_fault,
    local_term_fault,
    question_fault,
    statement_fault,
    unwritable,
)
from shopper.agents.brief.models import (
    Cited,
    Followed,
    FoundTerm,
    LocalTerm,
    Phrased,
    Phrasing,
    PhrasingResult,
    ReadFactor,
    Reading,
    ReadResult,
    Researched,
    Stated,
)
from shopper.agents.brief.prompt import (
    LOCAL_TERM_INPUT,
    LOCAL_TERM_PROMPT,
    PHRASING_FACTOR,
    PHRASING_FREQUENCY,
    PHRASING_INPUT,
    PHRASING_PROMPT,
    READ_INPUT,
    READ_PROMPT,
)
from shopper.agents.brief.stated import read_stated
from shopper.agents.brief.trail import (
    by_model,
    counted,
    entry,
    first_read_stands,
    model_call_failed,
    searched,
)
from shopper.agents.brief.typical_cost import with_typical_cost
from shopper.agents.brief.usage_frequency import (
    DEFAULT_FREQUENCIES,
    FREQUENCIES_OFFERED,
    USAGE_FACTOR,
    USES_PER_YEAR,
    frequency_pick,
    usage_question,
)
from shopper.agents.bundle import BriefOutput
from shopper.agents.shared.model_text import fault_in
from shopper.agents.shared.research import (
    NUMBERED_RESULT,
    distinct_results,
    follow_up_fault,
    numbered,
)
from shopper.config import (
    BRIEF_MAX_TOKENS,
    BRIEF_TIMEOUT_SECONDS,
    ENOUGH_RESEARCHED_FACTORS,
    FIXED_RATES,
    MODEL_IDS,
    SEARCH_TEMPLATES,
    SearchPurpose,
    Tier,
)
from shopper.llm import ChatModel, Completion, LlmFailure, complete_structured
from shopper.state import (
    CARE_AVOID_CHOICE_ID,
    MAX_RESEARCHED_QUESTIONS,
    Choice,
    DecisionFactor,
    FactorKind,
    ProductOption,
    Question,
    Request,
    Source,
    SourceKind,
    StatedBy,
    TrailEntry,
    TrailKind,
    Warning,
    WarningCode,
)
from shopper.tools.brief_store import Brief, BriefStore
from shopper.tools.results import FailureKind, SearchResult, WebSearch

READ_TIER: Tier = "medium"
# The read reasons little: in full it took 13 to 39 s. With little reasoning it keeps fewer
# factors unless the prompt asks for every factor the results support, and even then the kettle
# kept 6 and 7 where task 1.7 kept 8 (docs/findings/task_1.7.2.md). The phrasing call reasons in
# full; with little reasoning its choices failed the checks.
READ_LOW_EFFORT = True
# Medium, not small: the small tier took 18 to 85 s and was cut off once (models.md).
PHRASING_TIER: Tier = "medium"
# Medium, not small: the small tier gave the hand-written term in none of six answers in task
# 1.12, the medium tier in two of three (docs/findings/task_1.12.md).
LOCAL_TERM_TIER: Tier = "medium"
# Ids carry a prefix per origin, so a cached id never collides with a factor of another origin.
RESEARCHED_ID = "researched-{number}"
QUESTION_ID = "question-{factor_id}"
CHOICE_ID = "choice-{number}"
# The kinds asked about. A recurring-cost factor gets no question: its typical yearly cost, when
# there is one, is shown as a line above the questions.
ASKABLE_KINDS = frozenset({FactorKind.COMPATIBILITY, FactorKind.REQUIREMENT, FactorKind.CARE})
# The product at a pasted link is already chosen: only what decides whether it fits is asked.
LINKED_KINDS = frozenset({FactorKind.COMPATIBILITY, FactorKind.REQUIREMENT})
MAX_LINKED_QUESTIONS = 2
# The two choices of every care question; their ids are constant so the answer can be recognised.
CARE_CHOICES = (
    Choice(id="care-fine", text=wording.CARE_FINE),
    Choice(id=CARE_AVOID_CHOICE_ID, text=wording.CARE_AVOID),
)
# The check a factor's citation has to pass, as the key of the brief cache names it.
QUOTE_CHECK_RULE = (
    "the quote stands in the text of the cited search result; case, spaces, quote marks, "
    "hyphens and the punctuation at its ends do not count"
)
# Changes whenever what produces a brief changes, so a brief made otherwise is not read back.
BRIEF_VERSION = hashlib.sha256(
    "\n".join(
        (
            READ_PROMPT,
            READ_INPUT,
            PHRASING_PROMPT,
            PHRASING_INPUT,
            PHRASING_FACTOR,
            PHRASING_FREQUENCY,
            LOCAL_TERM_PROMPT,
            LOCAL_TERM_INPUT,
            NUMBERED_RESULT,
            *SEARCH_TEMPLATES.values(),
            # The words a stored brief holds or the phrasing call reads.
            *wording.USAGE_FREQUENCIES.values(),
            wording.CARE_CLOSING_QUESTION,
            wording.CARE_FINE,
            wording.CARE_AVOID,
            # A stored typical yearly cost was converted at these rates.
            *(f"{code} {rate.per_euro} {rate.on}" for code, rate in FIXED_RATES.items()),
            MODEL_IDS[READ_TIER],
            f"read low effort: {READ_LOW_EFFORT}",
            MODEL_IDS[PHRASING_TIER],
            MODEL_IDS[LOCAL_TERM_TIER],
            QUOTE_CHECK_RULE,
        )
    ).encode("utf-8")
).hexdigest()[:16]
# Who is speaking in a cited search result, as a trail entry words it.
SPEAKERS = {
    StatedBy.TESTER: "a tester",
    StatedBy.OWNER: "an owner",
    StatedBy.MANUFACTURER: "the manufacturer",
    StatedBy.SELLER: "a seller",
}


async def research_brief(
    request: Request,
    linked_product: ProductOption | None,
    chat: ChatModel,
    search: WebSearch,
    store: BriefStore,
) -> BriefOutput:
    """The decision factors of the request's category, the answers the request states, and the
    questions drawn from the factors it does not settle.

    How often the product is used is always the last factor and, unless stated, the last
    question. A request with no category is not researched and not cached. With a linked
    product fewer questions are asked; which ones is decided in code from the cached brief, so
    no question is about the product itself.
    """
    category = request.category
    if category is None:
        return _usage_only(await read_stated(request, (USAGE_FACTOR,), (), chat))
    stored = store.read(category, BRIEF_VERSION)
    if stored is not None:
        from_cache = entry(
            TrailKind.FOUND,
            f"Category research for {category} from the cache, "
            f"researched on {stored.researched_at:%Y-%m-%d}",
        )
        brief, lead, phrasing_failed = stored.brief, (from_cache,), False
    else:
        researched = await _research(category, chat, search)
        if researched.every_step_succeeded:
            store.write(category, BRIEF_VERSION, researched.brief)
        brief, lead, phrasing_failed = researched.brief, (), researched.phrasing_failed
    factors = (*brief.factors, USAGE_FACTOR)
    stated = await read_stated(request, factors, brief.questions, chat)
    return _output(
        category,
        brief,
        stated,
        lead=lead,
        phrasing_failed=phrasing_failed,
        linked=linked_product is not None,
    )


def _output(
    category: str,
    brief: Brief,
    stated: Stated,
    *,
    lead: tuple[TrailEntry, ...],
    phrasing_failed: bool,
    linked: bool,
) -> BriefOutput:
    """The brief as the session uses it: at most four researched questions about factors the
    request does not settle, or two with a linked product, then usage unless the request
    states it.

    Which questions are asked is decided here and not stored, so it depends on the request:
    a stated answer frees its question's place for the next phrased one.
    """
    settled = _settled(stated)
    open_questions = [question for question in brief.questions if question.factor_id not in settled]
    asked = _drawn(open_questions, brief.factors, linked=linked)
    usage = usage_question(frequency_pick(brief.usage_frequencies) or DEFAULT_FREQUENCIES)
    return BriefOutput(
        factors=(*brief.factors, *stated.factors, USAGE_FACTOR),
        questions=(*asked, *_unless_stated(usage, settled)),
        phrased_questions=brief.questions,
        stated_answers=stated.answers,
        local_term=brief.local_term,
        trail=(
            *lead,
            *brief.trail,
            *stated.trail,
            *_unasked(len(open_questions) - len(asked), linked=linked),
        ),
        warnings=(*_warnings(category, brief, phrasing_failed), *stated.warnings),
    )


def _drawn(
    open_questions: Sequence[Question], factors: Sequence[DecisionFactor], *, linked: bool
) -> list[Question]:
    """The researched questions asked, in research order: the first four, or with a linked
    product the first two about a compatibility or a requirement."""
    if not linked:
        return list(open_questions[:MAX_RESEARCHED_QUESTIONS])
    kinds = {factor.id: factor.kind for factor in factors}
    fitting = [question for question in open_questions if kinds[question.factor_id] in LINKED_KINDS]
    return fitting[:MAX_LINKED_QUESTIONS]


def _settled(stated: Stated) -> frozenset[str]:
    """The ids of the factors the request settles."""
    return frozenset(answer.factor_id for answer in stated.answers)


def _unless_stated(question: Question, settled: frozenset[str]) -> tuple[Question, ...]:
    return () if question.factor_id in settled else (question,)


def _warnings(category: str, brief: Brief, phrasing_failed: bool) -> tuple[Warning, ...]:
    """One or two factors is not a warning; the trail records what was left out."""
    if not brief.factors:
        code, message = WarningCode.RESEARCH_UNAVAILABLE, wording.research_unavailable(category)
    elif phrasing_failed:
        code, message = WarningCode.QUESTIONS_UNAVAILABLE, wording.questions_unavailable(category)
    else:
        return ()
    return (Warning(code=code, message=message),)


async def _research(category: str, chat: ChatModel, search: WebSearch) -> Researched:
    """Search with both templates at once, beside the call for the local category term, read the
    results, and phrase the questions."""
    searches = asyncio.gather(
        *(
            search(template.format(category=category), purpose)
            for purpose, template in SEARCH_TEMPLATES.items()
        )
    )
    outcomes, term = await asyncio.gather(searches, _local_term(category, chat))
    results = distinct_results(result for outcome in outcomes for result in outcome.results)
    first = await _read(category, results, chat)
    followed = await _follow_up(category, first, results, chat, search)
    cited, costed = with_typical_cost(followed.read.cited)
    phrased = await _phrase(category, cited, chat)
    brief = Brief(
        factors=tuple(found.factor for found in cited),
        questions=phrased.questions,
        usage_frequencies=phrased.frequencies,
        local_term=term.term,
        trail=(
            *(searched(outcome) for outcome in outcomes),
            *first.summary,
            *followed.trail,
            *followed.read.details,
            *costed,
            *phrased.trail,
            *term.trail,
        ),
    )
    every_search_ran = all(outcome.failure in (None, FailureKind.NOT_FOUND) for outcome in outcomes)
    every_read_succeeded = first.reply is not None and not followed.second_read_failed
    every_call_succeeded = every_read_succeeded and phrased.succeeded and term.succeeded
    return Researched(
        brief,
        every_step_succeeded=every_search_ran and every_call_succeeded,
        phrasing_failed=not phrased.succeeded,
    )


async def _local_term(category: str, chat: ChatModel) -> FoundTerm:
    """The word shops here use for the category, once it passes the check; a failed call leaves
    the brief unstored, as a failed read does."""
    reply = await complete_structured(
        chat,
        LOCAL_TERM_TIER,
        LOCAL_TERM_INPUT.format(category=category),
        LocalTerm,
        system=LOCAL_TERM_PROMPT,
        max_tokens=BRIEF_MAX_TOKENS,
        timeout=BRIEF_TIMEOUT_SECONDS,
    )
    if isinstance(reply, LlmFailure):
        return FoundTerm(None, (model_call_failed("find the local category term", reply),), False)
    term = " ".join(reply.value.local_term.lower().split())
    fault = local_term_fault(term)
    if fault is not None:
        left_out = entry(TrailKind.EXCLUDED, "Left out the local category term", reason=fault)
        return FoundTerm(None, (by_model(left_out, reply),), True)
    found = entry(TrailKind.FOUND, f"Local category term: {term}")
    return FoundTerm(term, (by_model(found, reply),), True)


async def _follow_up(
    category: str,
    first: ReadResult,
    results: Sequence[SearchResult],
    chat: ChatModel,
    search: WebSearch,
) -> Followed:
    """The read that stands, and the trail of the follow-up search when one was called for.

    The model may propose one follow-up. It runs when the read reported gaps or too few factors
    were sourced, and a second read of every result so far then replaces the first, unless it
    kept fewer factors (a tie goes to the second).
    """
    reason = _reason_to_follow_up(first)
    proposed = (first.reply.value.follow_up_query or "").strip() if first.reply is not None else ""
    if first.reply is None or reason is None or not proposed:
        return Followed(first, ())
    fault = follow_up_fault(proposed, category)
    if fault is not None:
        discarded = entry(TrailKind.EXCLUDED, "Discarded the follow-up search query", reason=fault)
        return Followed(first, (by_model(discarded, first.reply),))
    decided = by_model(
        entry(TrailKind.DECIDED, f'Follow-up search: "{proposed}"', reason=reason), first.reply
    )
    outcome = await search(proposed, SearchPurpose.CATEGORY, follow_up=True)
    if outcome.failure not in (None, FailureKind.NOT_FOUND):
        not_run = entry(TrailKind.EXCLUDED, "Follow-up search not run", reason=str(outcome.failure))
        return Followed(first, (decided, not_run))
    every_result = distinct_results((*results, *outcome.results))
    if len(every_result) == len(results):
        nothing_new = entry(TrailKind.DECIDED, "The follow-up search found no new search result")
        return Followed(first, (decided, searched(outcome), nothing_new))
    second = await _read(category, every_result, chat)
    trail = (decided, searched(outcome), *second.summary)
    if second.reply is None:
        return Followed(first, trail, second_read_failed=True)
    if len(second.cited) < len(first.cited):
        stands = first_read_stands(len(second.cited), len(first.cited))
        return Followed(first, (*trail, stands))
    return Followed(second, trail)


def _reason_to_follow_up(read: ReadResult) -> str | None:
    if read.reply is None:
        return None
    if read.reply.value.gaps:
        return "the read reported gaps"
    if len(read.cited) < ENOUGH_RESEARCHED_FACTORS:
        return f"fewer than {ENOUGH_RESEARCHED_FACTORS} factors were sourced"
    return None


async def _read(category: str, results: Sequence[SearchResult], chat: ChatModel) -> ReadResult:
    """Give the results to the model and keep the factors that pass the checks."""
    if not results:
        return ReadResult((), (), (), reply=None)
    reading = await complete_structured(
        chat,
        READ_TIER,
        READ_INPUT.format(category=category, results=numbered(results)),
        Reading,
        system=READ_PROMPT,
        max_tokens=BRIEF_MAX_TOKENS,
        timeout=BRIEF_TIMEOUT_SECONDS,
        low_effort=READ_LOW_EFFORT,
    )
    if isinstance(reading, LlmFailure):
        failed = model_call_failed("read the search results", reading)
        return ReadResult((), (failed,), (), reply=None)
    cited, factor_entries = _kept(reading, results)
    shown = range(1, len(results) + 1)
    cited_results = {factor.result for factor in reading.value.factors if factor.result in shown}
    summary = (
        f"Read {counted(len(results), 'search result')}: {len(cited_results)} cited, "
        f"{counted(len(cited), 'factor')} kept"
    )
    return ReadResult(
        cited,
        (by_model(entry(TrailKind.FOUND, summary), reading),),
        (*factor_entries, *_gaps(reading)),
        reply=reading,
    )


def _gaps(reading: Completion[Reading]) -> tuple[TrailEntry, ...]:
    """A trail entry per gap the model reported. A gap never becomes a factor or a value."""
    return tuple(
        by_model(
            entry(
                TrailKind.DECIDED,
                f"Not covered by the search results: {gap.what.strip()}",
                reason=gap.reason.strip(),
            ),
            reading,
        )
        for gap in reading.value.gaps
        if gap.what.strip()
        and gap.reason.strip()
        and fault_in(gap.what) is None
        and fault_in(gap.reason) is None
    )


async def _phrase(category: str, cited: Sequence[Cited], chat: ChatModel) -> PhrasingResult:
    """Ask the model for a question per factor that can be asked about, and for the
    usage frequencies.

    With no researched factor there is nothing to phrase: the model is not called and code
    offers the default frequencies.
    """
    if not cited:
        return PhrasingResult((), DEFAULT_FREQUENCIES, (), succeeded=True)
    askable = tuple(found for found in cited if found.factor.kind in ASKABLE_KINDS)
    phrasing = await complete_structured(
        chat,
        PHRASING_TIER,
        _phrasing_input(category, askable),
        Phrasing,
        system=PHRASING_PROMPT,
        max_tokens=BRIEF_MAX_TOKENS,
        timeout=BRIEF_TIMEOUT_SECONDS,
    )
    if isinstance(phrasing, LlmFailure):
        failed = model_call_failed("phrase the questions", phrasing)
        return PhrasingResult((), DEFAULT_FREQUENCIES, (failed,), succeeded=False)
    questions, not_phrased = _questions(phrasing.value, askable, category)
    picked = frequency_pick(phrasing.value.usage_frequencies)
    entries = (*not_phrased, _frequencies_entry(picked))
    return PhrasingResult(
        questions,
        picked or DEFAULT_FREQUENCIES,
        tuple(by_model(each, phrasing) for each in entries),
        succeeded=True,
    )


def _unasked(left: int, *, linked: bool) -> tuple[TrailEntry, ...]:
    """The entry for phrased questions that are not asked; none when every one is."""
    if left <= 0:
        return ()
    questions = "question" if left == 1 else "questions"
    reason = (
        f"the product at the link is already chosen: at most {MAX_LINKED_QUESTIONS} questions "
        "about compatibility or requirements are asked besides how often the product is used"
        if linked
        else f"at most {MAX_RESEARCHED_QUESTIONS} questions are asked besides how often the "
        "product is used"
    )
    return (entry(TrailKind.DECIDED, f"Left {left} phrased {questions} unasked", reason=reason),)


def _frequencies_entry(picked: tuple[str, ...] | None) -> TrailEntry:
    offered = ", ".join(
        wording.USAGE_FREQUENCIES[frequency].lower() for frequency in picked or DEFAULT_FREQUENCIES
    )
    reason = (
        f"the default: the model did not pick {FREQUENCIES_OFFERED} different usage frequencies"
        if picked is None
        else "picked by the model for the category"
    )
    summary = f"Offered for how often the product is used: {offered}"
    return entry(TrailKind.DECIDED, summary, reason=reason)


def _phrasing_input(category: str, askable: Sequence[Cited]) -> str:
    """What the phrasing call reads: the factors to ask about by number, and the usage
    frequencies."""
    factors = "\n\n".join(
        PHRASING_FACTOR.format(
            number=number,
            name=found.factor.name,
            kind=found.factor.kind,
            why=found.factor.why,
            text=found.result.content,
        )
        for number, found in enumerate(askable, start=1)
    )
    frequencies = "\n".join(
        PHRASING_FREQUENCY.format(frequency=frequency, words=wording.USAGE_FREQUENCIES[frequency])
        for frequency in USES_PER_YEAR
    )
    return PHRASING_INPUT.format(category=category, factors=factors, frequencies=frequencies)


def _questions(
    phrasing: Phrasing, askable: Sequence[Cited], category: str
) -> tuple[tuple[Question, ...], tuple[TrailEntry, ...]]:
    """One question per factor that was phrased and passes the checks, in the order of the
    factors, and an exclusion for each factor that has none."""
    # The first entry for a factor counts; one for a number that is no factor is ignored.
    phrased = {entry.factor: entry for entry in reversed(phrasing.questions)}
    asked = [
        (found.factor, _asked(found, phrased.get(number), category))
        for number, found in enumerate(askable, start=1)
    ]
    questions = tuple(outcome for _, outcome in asked if isinstance(outcome, Question))
    not_phrased = tuple(
        entry(TrailKind.EXCLUDED, f'No question about the factor "{factor.name}"', reason=outcome)
        for factor, outcome in asked
        if isinstance(outcome, str)
    )
    return questions, not_phrased


def _asked(found: Cited, phrased: Phrased | None, category: str) -> Question | str:
    """The question about a factor, or why it counts as not phrased."""
    if phrased is None:
        return "the model wrote none"
    fault = (
        statement_fault(phrased.text, category)
        if found.factor.kind is FactorKind.CARE
        else question_fault(phrased, found.result.content)
    )
    return _question(found.factor, phrased) if fault is None else fault


def _question(factor: DecisionFactor, phrased: Phrased) -> Question:
    """A care factor's question is the model's statement and fixed words; any other factor's
    question is the model's own, with its reason and choices."""
    if factor.kind is FactorKind.CARE:
        statement = f"{phrased.text.strip().rstrip('.!?')}."
        return Question(
            id=QUESTION_ID.format(factor_id=factor.id),
            factor_id=factor.id,
            text=wording.care_question(statement),
            reason=factor.why,
            choices=CARE_CHOICES,
        )
    return Question(
        id=QUESTION_ID.format(factor_id=factor.id),
        factor_id=factor.id,
        text=phrased.text.strip(),
        reason=(phrased.reason or "").strip(),
        choices=tuple(
            Choice(id=CHOICE_ID.format(number=number), text=text.strip())
            for number, text in enumerate(phrased.choices, start=1)
        ),
    )


def _usage_only(stated: Stated) -> BriefOutput:
    """The brief of a request with no category: nothing is researched."""
    decided = entry(
        TrailKind.DECIDED,
        "Asked only how often the product is used",
        reason="the request names no category to research",
    )
    return BriefOutput(
        factors=(*stated.factors, USAGE_FACTOR),
        questions=_unless_stated(usage_question(), _settled(stated)),
        stated_answers=stated.answers,
        trail=(decided, *stated.trail),
        warnings=stated.warnings,
    )


def _kept(
    reading: Completion[Reading], results: Sequence[SearchResult]
) -> tuple[tuple[Cited, ...], tuple[TrailEntry, ...]]:
    """The factors of a read that pass the checks, numbered in the order read, and a trail entry
    for each factor: found, or excluded with the check it failed."""
    kept: list[Cited] = []
    entries: list[TrailEntry] = []
    for proposed in reading.value.factors:
        words_fault = unwritable(proposed)
        named_so_far = [found.factor.name for found in kept]
        fault = words_fault or factor_fault(proposed, results, named_so_far)
        if fault is None:
            result = results[proposed.result - 1]
            factor = _factor(proposed, len(kept) + 1, result)
            kept.append(Cited(factor, result, proposed))
            entries.append(entry(TrailKind.FOUND, _found(factor), source=factor.source))
        else:
            # A name that may not be written is not repeated on the trail either.
            named = "a factor" if words_fault else f'the factor "{proposed.name.strip()}"'
            entries.append(entry(TrailKind.EXCLUDED, f"Left out {named}", reason=fault))
    return tuple(kept), tuple(by_model(each, reading) for each in entries)


def _factor(proposed: ReadFactor, number: int, result: SearchResult) -> DecisionFactor:
    return DecisionFactor(
        id=RESEARCHED_ID.format(number=number),
        name=proposed.name.strip(),
        kind=FactorKind(proposed.kind),
        why=proposed.why.strip(),
        source=Source(kind=SourceKind.URL, reference=result.url, stated_by=proposed.stated_by),
    )


def _found(factor: DecisionFactor) -> str:
    speaker = SPEAKERS[factor.source.stated_by]
    return f'Factor "{factor.name}" ({factor.kind}), stated by {speaker}'
