"""The lines of a session or a reply, built by the line functions of wording.py; the report's
are in report_lines.py, which these reuse.

The API sends them beside the data and the terminal app prints their text
(docs/adr/0008-api-sends-finished-lines.md). They are built when they are shown and never saved,
so a change of wording reaches old sessions too.
"""

from collections.abc import Sequence

from shopper import wording
from shopper.calc.display import euros
from shopper.graph.sessions import ReplyRead, SessionStart
from shopper.report_lines import declined_line, stated_answer_lines, typical_cost_lines_of
from shopper.state import (
    DecisionFactor,
    DomainModel,
    Question,
    Request,
)
from shopper.wording import Line


class SessionLines(DomainModel):
    """The lines of a session at the pause: what was understood, and the same words as the box's
    first label, the "From your request" lines, the typical yearly costs and, by the question's
    id, the source line under each question about a researched factor. A request that does not
    run has its decline only."""

    understood: Line | None = None
    label: Line | None = None
    declined: Line | None = None
    stated: tuple[Line, ...] = ()
    typical_costs: tuple[Line, ...] = ()
    sources: dict[str, Line] = {}


def session_lines(session: SessionStart) -> SessionLines:
    """The lines of a session's `session` event and of its paused view."""
    declined = declined_line(session.request)
    if declined is not None:
        return SessionLines(declined=declined)
    return SessionLines(
        understood=understood_line(session.request),
        label=box_label_line(session.request),
        stated=stated_answer_lines(session.stated_answers, session.factors),
        typical_costs=typical_cost_lines_of(session.factors),
        sources=question_sources(session.questions, session.factors),
    )


def understood_line(request: Request) -> Line:
    """What was understood, shown as soon as the request is known to run."""
    return wording.understood(request.category, _budget(request))


def box_label_line(request: Request) -> Line:
    """What was understood, as the page's box carries it on its first label."""
    return wording.box_label(request.category, _budget(request))


def question_sources(
    questions: Sequence[Question], factors: Sequence[DecisionFactor]
) -> dict[str, Line]:
    """The source line under each question whose decision factor has a source, by the
    question's id."""
    by_id = {factor.id: factor for factor in factors}
    sourced = {question.id: source_line_of(by_id.get(question.factor_id)) for question in questions}
    return {question_id: line for question_id, line in sourced.items() if line is not None}


def source_line_of(factor: DecisionFactor | None) -> Line | None:
    """The site a researched question's decision factor came from, and who is speaking when it
    matters; none for a question about a factor with no source, the usage question."""
    if factor is None or factor.source is None:
        return None
    return wording.source_line(factor.source.reference, factor.source.stated_by)


def reply_lines(
    read: ReplyRead, request: Request, factors: Sequence[DecisionFactor]
) -> tuple[Line, ...]:
    """The "From your reply" lines, then the thread's line on what the reply changed. `factors`
    are the paused session's; those the reply adds are in `read`."""
    from_reply = stated_answer_lines(read.answers, (*factors, *read.factors))
    in_thread = wording.reply_in_thread(
        request.category,
        _budget(request),
        asks_to_change_request=read.asks_to_change_request,
        changed_an_answer=bool(read.answers or read.factors),
        unanswered=read.unanswered,
    )
    return from_reply if in_thread is None else (*from_reply, in_thread)


def _budget(request: Request) -> str | None:
    return None if request.budget is None else euros(request.budget)
