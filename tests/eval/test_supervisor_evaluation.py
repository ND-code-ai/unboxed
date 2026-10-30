"""The supervisor evaluation: does the model apply the scope and category definitions?

The evaluation itself is live (`uv run pytest -m live`) and spends credits. The offline tests
here only guard the prompt and the judging.
"""

import asyncio
from decimal import Decimal

import pytest
from supervisor_cases import CASES, HELD_OUT_TERMS, Case

from shopper.agents.supervisor.agent import (
    SUPERVISOR_PROMPT,
    ModelCallError,
    ParsedRequest,
    parse_request,
)
from shopper.config import NEBIUS_KEY_NAME, Tier, load_env, require
from shopper.llm import ChatModel, nebius_chat
from shopper.state import Request, Scope, Warning, WarningCode

RUNS = 2
ATTEMPTS_PER_CASE = 3
CONCURRENT_CALLS = 4

Answer = tuple[Scope, str | None]
OTHER_CURRENCY = WarningCode.BUDGET_OTHER_CURRENCY


@pytest.mark.parametrize("term", HELD_OUT_TERMS)
def test_no_held_out_product_appears_in_the_prompt(term: str) -> None:
    assert term.lower() not in SUPERVISOR_PROMPT.lower()


def test_the_prompt_has_at_most_three_worked_examples_per_scope() -> None:
    examples = SUPERVISOR_PROMPT.split("Worked examples.")[1].split("ONE PRODUCT")[0]

    for scope in Scope:
        assert examples.count(f": {scope},") <= 3


def test_tuned_returned_as_general_is_accepted_only_on_a_borderline_case() -> None:
    clear = Case("a frying pan", Scope.TUNED, "tuned")
    borderline = Case("a shaver", Scope.TUNED, "tuned", borderline=True)

    assert not scope_is_accepted(clear, Scope.GENERAL)
    assert scope_is_accepted(borderline, Scope.GENERAL)
    assert not scope_is_accepted(borderline, Scope.ENERGY_HEAVY)


def test_a_caveat_scope_returned_as_one_without_is_never_accepted() -> None:
    heater = Case("a heater", Scope.ENERGY_HEAVY, "energy line", borderline=True)

    assert not scope_is_accepted(heater, Scope.TUNED)
    assert not scope_is_accepted(heater, Scope.GENERAL)


def test_a_category_must_repeat_only_where_the_case_states_one() -> None:
    stated = Case("a frying pan", Scope.TUNED, "tuned", category="frying pan")
    unstated = Case("a tumble dryer", Scope.ENERGY_HEAVY, "energy line")

    assert problems_of(stated, ((Scope.TUNED, "frying pan"), (Scope.TUNED, "pan")))
    assert not problems_of(
        unstated, ((Scope.ENERGY_HEAVY, "clothes dryer"), (Scope.ENERGY_HEAVY, "tumble dryer"))
    )


def test_another_name_of_the_same_category_passes_but_a_wider_one_does_not() -> None:
    printer = Case(
        "a 3d printer",
        Scope.GENERAL,
        "digit in the name",
        category="3d printer",
        also_accepted=("three dimensional printer",),
    )

    assert not problems_of(
        printer, ((Scope.GENERAL, "3d printer"), (Scope.GENERAL, "three dimensional printer"))
    )
    assert problems_of(printer, ((Scope.GENERAL, "3d printer"), (Scope.GENERAL, "printer")))


def test_the_runs_must_agree_on_the_scope_also_on_a_borderline_case() -> None:
    borderline = Case("a shaver", Scope.TUNED, "tuned", borderline=True)

    assert problems_of(borderline, ((Scope.TUNED, "shaver"), (Scope.GENERAL, "shaver")))


def test_a_budget_outcome_is_the_warning_code_or_the_euro_amount() -> None:
    other_currency = Case(
        "a pan for 10 florins", Scope.TUNED, "budget", budget_outcome=OTHER_CURRENCY
    )
    euros = Case("a pan, 50 tops", Scope.TUNED, "budget", budget_outcome=Decimal("50"))

    assert not budget_problems_of(other_currency, (parsed(warning=OTHER_CURRENCY),) * 2)
    assert not budget_problems_of(euros, (parsed(budget="50"),) * 2)
    assert budget_problems_of(other_currency, (parsed(budget="10"),) * 2)
    assert budget_problems_of(other_currency, (parsed(warning=WarningCode.BUDGET_UNREADABLE),) * 2)
    assert budget_problems_of(euros, (parsed(warning=OTHER_CURRENCY),) * 2)
    assert budget_problems_of(euros, (parsed(budget="5"),) * 2)
    assert budget_problems_of(euros, (parsed(),) * 2)


def test_both_runs_must_give_the_budget_outcome() -> None:
    other_currency = Case(
        "a pan for 10 florins", Scope.TUNED, "budget", budget_outcome=OTHER_CURRENCY
    )

    problems = budget_problems_of(
        other_currency, (parsed(warning=OTHER_CURRENCY), parsed(budget="10"))
    )

    assert len(problems) == 1
    assert "run 2" in problems[0]


def test_a_case_that_states_no_budget_outcome_is_not_judged_on_its_budget() -> None:
    unstated = Case("a frying pan, budget 50 euro", Scope.TUNED, "tuned")

    assert not budget_problems_of(unstated, (parsed(budget="50"), parsed()))


def test_a_budget_case_that_was_not_evaluated_is_reported_once_by_the_scope_judging() -> None:
    euros = Case("a pan, 50 tops", Scope.TUNED, "budget", budget_outcome=Decimal("50"))

    assert not budget_problems_of(euros, (parsed(budget="50"), None))
    assert problems_of(euros, (answer_of(parsed(budget="50")), answer_of(None)))


def parsed(budget: str | None = None, warning: WarningCode | None = None) -> ParsedRequest:
    """A parsed request written by hand, with the budget or the budget warning given."""
    request = Request(
        original_text="a pan",
        category="frying pan",
        scope=Scope.TUNED,
        budget=None if budget is None else Decimal(budget),
    )
    warnings = () if warning is None else (Warning(code=warning, message="not applied"),)
    return ParsedRequest(request=request, warnings=warnings)


def scope_is_accepted(case: Case, scope: Scope) -> bool:
    if scope is case.scope:
        return True
    return case.borderline and case.scope is Scope.TUNED and scope is Scope.GENERAL


@pytest.mark.live
def test_the_evaluation_passes_in_two_runs_in_a_row(supervisor_tier: Tier) -> None:
    chat = nebius_chat(require(load_env(), NEBIUS_KEY_NAME))

    runs = asyncio.run(evaluate(chat, supervisor_tier))

    problems = [
        problem
        for case, requests in zip(CASES, zip(*runs, strict=True), strict=True)
        for problem in (
            *problems_of(case, tuple(answer_of(request) for request in requests)),
            *budget_problems_of(case, requests),
        )
    ]
    assert not problems, "\n" + "\n".join(problems)


async def evaluate(chat: ChatModel, tier: Tier) -> list[list[ParsedRequest | None]]:
    """Every case, RUNS times in a row; a case that could not be evaluated is missing."""
    limit = asyncio.Semaphore(CONCURRENT_CALLS)
    return [
        list(await asyncio.gather(*(parse_case(chat, tier, case, limit) for case in CASES)))
        for _ in range(RUNS)
    ]


async def parse_case(
    chat: ChatModel, tier: Tier, case: Case, limit: asyncio.Semaphore
) -> ParsedRequest | None:
    """The parsed request for one case; a timeout or service error is tried again."""
    for _ in range(ATTEMPTS_PER_CASE):
        async with limit:
            try:
                found: ParsedRequest = await parse_request(case.input, chat, tier)
            except ModelCallError as error:
                if error.failure.kind == "invalid_output":
                    raise
                continue
        return found
    return None


def answer_of(parsed_request: ParsedRequest | None) -> Answer | None:
    if parsed_request is None:
        return None
    return parsed_request.request.scope, parsed_request.request.category


def problems_of(case: Case, answers: tuple[Answer | None, ...]) -> list[str]:
    label = f"[{case.rule}] {case.input!r}"
    if any(found is None for found in answers):
        return [f"{label}: not evaluated (timeout or service error); run it again"]
    problems = [
        f"{label}: run {number} gave scope {scope}, expected {case.scope}"
        for number, (scope, _) in enumerate(answers, start=1)
        if not scope_is_accepted(case, scope)
    ]
    scopes = {scope for scope, _ in answers}
    if len(scopes) > 1:
        problems.append(f"{label}: the runs differ in scope: {sorted(scopes)}")
    categories = {category for _, category in answers}
    accepted = {case.category, *case.also_accepted}
    if case.category is not None and not categories <= accepted:
        problems.append(f"{label}: category {categories}, expected one of {sorted(accepted)}")
    return problems


def budget_outcome(parsed_request: ParsedRequest) -> WarningCode | Decimal | None:
    """The code of the warning that dropped the budget, or else the budget in euro.

    Parsing raises no warning but the one for a budget it dropped.
    """
    if parsed_request.warnings:
        return parsed_request.warnings[0].code
    return parsed_request.request.budget


def budget_problems_of(case: Case, requests: tuple[ParsedRequest | None, ...]) -> list[str]:
    """Where a run's budget outcome is not the one the case states; missing runs are skipped."""
    if case.budget_outcome is None:
        return []
    return [
        f"[{case.rule}] {case.input!r}: run {number} gave budget outcome "
        f"{budget_outcome(request)}, expected {case.budget_outcome}"
        for number, request in enumerate(requests, start=1)
        if request is not None and budget_outcome(request) != case.budget_outcome
    ]
