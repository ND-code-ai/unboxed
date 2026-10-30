from decimal import Decimal

from shopper.graph.sessions import ReplyRead, SessionStart
from shopper.lines import (
    SessionLines,
    declined_line,
    reply_lines,
    session_lines,
    source_line_of,
    stated_answer_lines,
    typical_cost_lines_of,
    understood_line,
)
from shopper.state import (
    Answer,
    AnswerStatus,
    Choice,
    DecisionFactor,
    FactorKind,
    Question,
    Request,
    Scope,
    Source,
    SourceKind,
    StatedBy,
    StatedIn,
)
from shopper.wording import ControlPart, Line, LinkPart, TextPart, plain_text

PAN = Request(
    original_text="a frying pan, budget 49.995 euro",
    category="frying pan",
    budget=Decimal("49.995"),
    scope=Scope.TUNED,
)
MAKER = Source(
    kind=SourceKind.URL,
    reference="https://www.tefal.nl/pannen",
    stated_by=StatedBy.MANUFACTURER,
)
HOB = DecisionFactor(
    id="hob", name="Hob compatibility", kind=FactorKind.COMPATIBILITY, why="w", source=MAKER
)
OIL_SOURCE = Source(kind=SourceKind.URL, reference="https://www.rtings.com/oil")
OIL = DecisionFactor(
    id="oil",
    name="Seasoning oil",
    kind=FactorKind.RECURRING_COST,
    why="w",
    source=OIL_SOURCE,
    typical_yearly_cost=Decimal("6.125"),
    typical_yearly_cost_source=OIL_SOURCE,
)
OWN = DecisionFactor(
    id="user-1",
    name="oven safe",
    kind=FactorKind.REQUIREMENT,
    why="You asked for this.",
    source=Source(kind=SourceKind.USER, reference="user"),
)
HOB_QUESTION = Question(
    id="question-hob",
    factor_id="hob",
    text="Which hob do you cook on?",
    reason="w",
    choices=(Choice(id="gas", text="Gas"), Choice(id="induction", text="Induction")),
)
ON_INDUCTION = Answer(
    factor_id="hob",
    status=AnswerStatus.STATED,
    choice_id="induction",
    stated_value="Induction",
    stated_phrase="on induction",
)


def text(line: Line | None) -> str | None:
    return None if line is None else plain_text(line)


def test_the_understood_line_writes_the_budget_and_ends_in_the_edit_control() -> None:
    assert understood_line(PAN) == Line(
        parts=(TextPart(text="Looking for: frying pan · Budget: €50"), ControlPart(key="edit"))
    )


def test_a_session_whose_request_does_not_run_has_its_decline_only() -> None:
    groceries = Request(original_text="groceries", category="groceries", scope=Scope.NOT_A_PRODUCT)

    lines = session_lines(SessionStart(session_id="s", request=groceries))

    assert text(lines.declined) == (
        "This app covers durable products such as cookware, appliances and tools. "
        """It can't help with "groceries"."""
    )
    assert lines.model_copy(update={"declined": None}) == SessionLines()


def test_a_paused_session_has_what_was_understood_stated_and_costs_and_each_source() -> None:
    session = SessionStart(
        session_id="s",
        request=PAN,
        factors=(HOB, OIL),
        questions=(HOB_QUESTION,),
        stated_answers=(ON_INDUCTION,),
    )

    lines = session_lines(session)

    assert text(lines.understood) == "Looking for: frying pan · Budget: €50"
    assert text(lines.label) == "frying pan · €50"
    assert lines.declined is None
    assert [text(line) for line in lines.stated] == [
        'From your request: Hob compatibility: Induction ("on induction")'
    ]
    assert [text(line) for line in lines.typical_costs] == [
        "Seasoning oil: typically €6.13 a year (rtings.com)."
    ]
    assert lines.sources == {
        "question-hob": Line(
            parts=(
                TextPart(text="Source: "),
                LinkPart(text="tefal.nl", url="https://www.tefal.nl/pannen"),
                TextPart(text=" (the manufacturer states)"),
            )
        )
    }


def test_a_reply_that_adds_a_factor_of_the_users_own_shows_it_from_the_reply() -> None:
    oven_safe = Answer(
        factor_id="user-1",
        status=AnswerStatus.STATED,
        stated_value="oven safe",
        stated_phrase="oven safe",
        stated_in=StatedIn.REPLY,
    )
    read = ReplyRead(answers=(oven_safe,), factors=(OWN,))

    assert [text(line) for line in reply_lines(read, PAN, (HOB,))] == [
        'From your reply: "oven safe"'
    ]


def test_a_reply_that_only_adds_a_factor_of_the_users_own_does_not_say_it_added_nothing() -> None:
    assert reply_lines(ReplyRead(factors=(OWN,)), PAN, (HOB,)) == ()


def test_a_reply_that_asks_to_change_the_request_ends_with_what_the_results_are_still_for() -> None:
    gas = Answer(
        factor_id="hob",
        status=AnswerStatus.STATED,
        choice_id="gas",
        stated_value="Gas",
        stated_phrase="gas",
        stated_in=StatedIn.REPLY,
    )
    read = ReplyRead(answers=(gas,), asks_to_change_request=True)

    assert [text(line) for line in reply_lines(read, PAN, (HOB,))] == [
        'From your reply: Hob compatibility: Gas ("gas")',
        "A reply can't change what you're looking for or the budget, so the results are still "
        "for frying pan, budget €50. To change either, press Edit.",
    ]


def test_a_reply_that_changed_no_answer_says_so_whether_or_not_it_answered_what_was_answered() -> (
    None
):
    for read in (ReplyRead(), ReplyRead(answered_already=True)):
        assert [text(line) for line in reply_lines(read, PAN, (HOB,))] == [
            "Nothing you wrote changed an answer or added a requirement."
        ]


def test_a_reply_that_ended_unanswered_says_only_that_it_cannot_change_the_request() -> None:
    unanswered = ReplyRead(unanswered=True, answered_already=True)
    asked_for_more = unanswered.model_copy(update={"asks_to_change_request": True})

    assert reply_lines(unanswered, PAN, (HOB,)) == ()
    assert [text(line) for line in reply_lines(asked_for_more, PAN, (HOB,))] == [
        "A reply can't change what you're looking for or the budget. To change either, press Edit."
    ]


def test_a_request_that_runs_has_no_decline_and_one_naming_two_products_asks_for_one() -> None:
    two = Request(original_text="a pan and a kettle", scope=Scope.SEVERAL_PRODUCTS)

    assert declined_line(PAN) is None
    assert text(declined_line(two)) == (
        "That looks like more than one product. "
        "Name one to start, for example 'a frying pan, budget €50'."
    )


def test_a_question_about_a_factor_with_no_source_has_no_source_line() -> None:
    usage = DecisionFactor(id="usage-1", name="Usage frequency", kind=FactorKind.USAGE, why="w")

    assert source_line_of(usage) is None
    assert source_line_of(None) is None
    assert text(source_line_of(HOB)) == "Source: tefal.nl (the manufacturer states)"


def test_the_requests_answers_come_before_the_replys_and_a_not_sure_keeps_its_phrase() -> None:
    no_idea = Answer(
        factor_id="hob",
        status=AnswerStatus.NOT_SURE,
        stated_phrase="no idea which hob",
        stated_in=StatedIn.REPLY,
    )
    chosen = Answer(factor_id="hob", status=AnswerStatus.CHOSEN, choice_id="gas")

    lines = stated_answer_lines((no_idea, chosen, ON_INDUCTION), (HOB,))

    assert [text(line) for line in lines] == [
        'From your request: Hob compatibility: Induction ("on induction")',
        'From your reply: Hob compatibility: not sure ("no idea which hob")',
    ]


def test_a_typical_yearly_cost_converted_at_a_fixed_rate_says_so() -> None:
    converted = OIL.model_copy(update={"typical_yearly_cost_converted_from": "USD"})

    assert [text(line) for line in typical_cost_lines_of((HOB, converted))] == [
        "Seasoning oil: typically €6.13 a year (rtings.com), converted from USD at a fixed rate."
    ]
