"""Recalculating a saved report with other assumptions: no agent runs, no model is called and
nothing is saved (docs/architecture/calculations.md, "Changing the assumptions")."""

from langgraph.graph.state import CompiledStateGraph

from shopper.api.models import FixedRefusalCode, RecalculateRequest, Recalculation
from shopper.calc.recalculation import recalculate
from shopper.config import (
    RECALCULATE_HORIZON_YEARS,
    RECALCULATE_LIFESPAN_YEARS,
    RECALCULATE_USES_PER_YEAR,
)
from shopper.graph.sessions import SessionHasNoReportError, SessionNotFoundError, read_report
from shopper.report_lines import ReportLines, evidence_summary_lines_of, option_lines_of
from shopper.state import Assumptions, Report


async def recalculated(
    graph: CompiledStateGraph, session_id: str, body: RecalculateRequest
) -> Recalculation | FixedRefusalCode:
    """The session's report recalculated with the assumptions; refused for one out of bounds, a
    session that is unknown or holds no report yet, a report with no options, and a lifespan for
    an option the report does not have."""
    if not within_bounds(body):
        return "invalid_assumptions"
    try:
        report = await read_report(graph, session_id)
    except SessionNotFoundError:
        return "session_not_found"
    except SessionHasNoReportError:
        return "no_report_yet"
    if not report.options:
        return "no_options"
    if not set(body.lifespan_overrides) <= {option.id for option in report.options}:
        return "unknown_option"
    assumptions = Assumptions(
        horizon_years=body.horizon_years,
        uses_per_year=body.uses_per_year,
        lifespan_overrides=body.lifespan_overrides,
    )
    return recalculation(report, assumptions)


def within_bounds(body: RecalculateRequest) -> bool:
    """Every assumption within what the app can calculate."""
    checked = [
        (body.horizon_years, RECALCULATE_HORIZON_YEARS),
        *((years, RECALCULATE_LIFESPAN_YEARS) for years in body.lifespan_overrides.values()),
    ]
    if body.uses_per_year is not None:
        checked.append((body.uses_per_year, RECALCULATE_USES_PER_YEAR))
    return all(low <= value <= high for value, (low, high) in checked)


def recalculation(report: Report, assumptions: Assumptions) -> Recalculation:
    """The report's options recalculated with the assumptions, with its request's budget and the
    default baseline, as the report itself was; its lines built as the report's are."""
    comparison, summary = recalculate(
        report.options, report.lca_results, assumptions, report.request.budget
    )
    recalculated = report.model_copy(
        update={"assumptions": assumptions, "comparison": comparison, "evidence_summary": summary}
    )
    lines = ReportLines(
        evidence_summary=evidence_summary_lines_of(recalculated),
        options=option_lines_of(recalculated),
    )
    return Recalculation(
        assumptions=assumptions, comparison=comparison, evidence_summary=summary, lines=lines
    )
