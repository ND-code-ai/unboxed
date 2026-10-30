"""What code adds when a report is assembled: the caveats and the check-before-you-buy list.

Pure functions that `assemble_report` in graph.py calls. Rules: docs/architecture/agents.md
("One report shape").
"""

from collections.abc import Sequence

from shopper.calc.budget import nothing_within_budget_warning
from shopper.calc.comparison import compare
from shopper.calc.evidence import summarise_evidence
from shopper.state import (
    SCOPES_THAT_DO_NOT_RUN,
    Answer,
    AnswerStatus,
    Assumptions,
    Caveat,
    CaveatCode,
    CheckItem,
    CheckReason,
    DecisionFactor,
    FactorKind,
    Fit,
    LcaResult,
    Listing,
    ProductOption,
    Question,
    Report,
    Request,
    Scope,
    TrailEntry,
    Warning,
)

DEFAULT_ASSUMPTIONS = Assumptions()
ANSWERED = frozenset({AnswerStatus.CHOSEN, AnswerStatus.STATED})

CAVEAT_BY_SCOPE = {
    Scope.GENERAL: CaveatCode.NOT_TUNED,
    Scope.ENERGY_HEAVY: CaveatCode.ENERGY_HEAVY,
    Scope.CLOTHING: CaveatCode.CLOTHING,
}


def assemble(
    request: Request,
    trail: Sequence[TrailEntry],
    warnings: Sequence[Warning],
    *,
    factors: Sequence[DecisionFactor] = (),
    questions: Sequence[Question] = (),
    answers: Sequence[Answer] = (),
    options: Sequence[ProductOption] = (),
    lca_results: Sequence[LcaResult] = (),
    listings: Sequence[Listing] = (),
    assumptions: Assumptions = DEFAULT_ASSUMPTIONS,
) -> Report:
    """The report for what the agents produced; every number on it is computed by `calc/`.

    A request that does not run gives a report with the request, its trail and its warnings.
    With no options there is nothing to compare, so the comparison is missing.
    """
    if request.scope in SCOPES_THAT_DO_NOT_RUN:
        return Report(request=request, trail=tuple(trail), warnings=tuple(warnings))
    comparison = compare(options, lca_results, assumptions, request.budget) if options else None
    over_budget = nothing_within_budget_warning(options, listings, request.budget)
    return Report(
        request=request,
        factors=tuple(factors),
        questions=tuple(questions),
        answers=tuple(answers),
        options=tuple(options),
        lca_results=tuple(lca_results),
        listings=tuple(listings),
        assumptions=assumptions,
        comparison=comparison,
        evidence_summary=summarise_evidence(options, lca_results, assumptions),
        caveats=caveats_for(request.scope),
        check_before_you_buy=check_before_you_buy(factors, answers, options),
        trail=tuple(trail),
        warnings=(*warnings, *(() if over_budget is None else (over_budget,))),
    )


def caveats_for(scope: Scope) -> tuple[Caveat, ...]:
    """The caveat a scope calls for; none for a tuned scope or a request that does not run."""
    code = CAVEAT_BY_SCOPE.get(scope)
    return () if code is None else (Caveat(code=code),)


def check_before_you_buy(
    factors: Sequence[DecisionFactor],
    answers: Sequence[Answer],
    options: Sequence[ProductOption],
) -> tuple[CheckItem, ...]:
    """The factors the user left open or that could not be verified, in the order of the factors,
    then the price of each option that has one, to confirm before buying: prices change.

    How often the product is used is an assumption the user sets, so it is never on the list.
    """
    answered = {answer.factor_id for answer in answers if answer.status in ANSWERED}
    open_factors = tuple(
        item
        for factor in factors
        if factor.kind is not FactorKind.USAGE
        for item in (
            _unverified(factor.id, options)
            if factor.id in answered
            else (CheckItem(factor_id=factor.id, reason=CheckReason.UNANSWERED),)
        )
    )
    prices = tuple(
        CheckItem(option_id=option.id, reason=CheckReason.PRICE)
        for option in options
        if option.price is not None
    )
    return (*open_factors, *prices)


def _unverified(factor_id: str, options: Sequence[ProductOption]) -> tuple[CheckItem, ...]:
    """One item per option whose value for the factor could not be verified."""
    return tuple(
        CheckItem(factor_id=factor_id, option_id=option.id, reason=CheckReason.UNVERIFIED)
        for option in options
        if any(
            value.factor_id == factor_id and value.fit is Fit.UNVERIFIED
            for value in option.factor_values
        )
    )
