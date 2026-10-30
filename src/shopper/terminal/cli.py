"""Terminal entry point: a tool for testing, kept simple (docs/terminal_app.md).

It shows what was understood, asks the questions and prints the report.

uv run python -m shopper.terminal.cli "I need a new frying pan, budget 50 euro"
uv run python -m shopper.terminal.cli --skip-all "I need a new frying pan, budget 50 euro"
"""

import asyncio
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from uuid import uuid4

import httpx

from shopper import wording
from shopper.agents.bundle import AgentBundle
from shopper.agents.default import DEFAULT_AGENTS
from shopper.agents.supervisor.agent import InputTooLongError, ModelCallError
from shopper.config import (
    NEBIUS_KEY_NAME,
    InvalidSettingError,
    MissingSettingError,
    load_env,
    require,
    tracing_settings,
)
from shopper.graph.graph import ProgressStatus, build_graph, memory_checkpointer
from shopper.graph.sessions import resume_session, start_session
from shopper.lines import session_lines, source_line_of, understood_line
from shopper.llm import ChatModel, nebius_chat
from shopper.state import Agent, Answer, AnswerStatus, DecisionFactor, Question, Request
from shopper.terminal.report_text import printed_report
from shopper.tools.http import RejectedKeyError
from shopper.tools.sources import Sources, sources_from_env
from shopper.tools.usage import USAGE_LOGGER
from shopper.tracing import RecordReport, traced
from shopper.wording import plain_text

USAGE = 'Usage: uv run python -m shopper.terminal.cli [--skip-all] "<what you are looking for>"'
SKIP_ALL_FLAG = "--skip-all"
PROMPT = "> "
NOT_SURE = "n"
SKIP = ""
SKIP_ALL = "skip all"

Read = Callable[[str], str]


async def run(
    input_text: str,
    chat: ChatModel,
    sources: Sources,
    read: Read = input,
    *,
    skip_all: bool = False,
    agents: AgentBundle = DEFAULT_AGENTS,
    record_report: RecordReport | None = None,
) -> int:
    """Run one session and print it; returns the exit status.

    `read` shows a prompt and returns the line typed, as `input` does. A test passes the agents
    it wants. `record_report` is given the report's printed lines, for the trace (`tracing.py`).
    """
    graph = build_graph(chat, memory_checkpointer(), sources, agents)
    try:
        session = await start_session(
            graph, uuid4().hex, input_text, show_understood, show_progress
        )
    except InputTooLongError:
        print(wording.INPUT_TOO_LONG)
        return 1
    except ModelCallError as error:
        print(wording.MODEL_CALL_FAILED)
        print(f"({error})", file=sys.stderr)
        return 1
    lines = session_lines(session)
    if lines.declined is not None:
        print(plain_text(lines.declined))
        return 0
    for warning in session.warnings:
        print(warning.message)
    for line in (*lines.stated, *lines.typical_costs):
        print(plain_text(line))
    answers = () if skip_all else ask(session.questions, session.factors, read)
    print()
    report = await resume_session(graph, session.session_id, answers, show_progress)
    print()
    printed = printed_report(report)
    for line in printed:
        print(line)
    if record_report is not None:
        record_report(printed)
    return 0


def show_understood(request: Request) -> None:
    """What was understood, shown as soon as the request is known to run."""
    print(plain_text(understood_line(request)))


def show_progress(agent: Agent, status: ProgressStatus) -> None:
    """One line as each agent starts; an agent finishing shows nothing."""
    if status is ProgressStatus.STARTED:
        print(wording.STARTED[agent])


def ask(
    questions: Sequence[Question], factors: Sequence[DecisionFactor], read: Read
) -> tuple[Answer, ...]:
    """Show each question and return the answers given; a skipped question has none.

    The keys are in docs/terminal_app.md ("The questions").
    """
    by_id = {factor.id: factor for factor in factors}
    answers: list[Answer] = []
    if questions:
        print()
        print(wording.KEYS)
    for question in questions:
        print()
        for line in question_lines(question, by_id.get(question.factor_id)):
            print(line)
        try:
            typed = _typed(question, read)
        except EOFError:
            break
        if typed == SKIP_ALL:
            break
        if typed == SKIP:
            continue
        answers.append(_answer(question, typed))
    return tuple(answers)


def _typed(question: Question, read: Read) -> str:
    """What was typed, once it is one of the question's keys; asks again until it is."""
    numbers = {str(number) for number in range(1, len(question.choices) + 1)}
    while True:
        typed = read(PROMPT).strip().lower()
        if typed in numbers | {NOT_SURE, SKIP, SKIP_ALL}:
            return typed
        print(wording.ask_again(len(question.choices)))


def _answer(question: Question, typed: str) -> Answer:
    """The answer for "n" or for the number of a choice."""
    if typed == NOT_SURE:
        return Answer(factor_id=question.factor_id, status=AnswerStatus.NOT_SURE)
    choice = question.choices[int(typed) - 1]
    return Answer(factor_id=question.factor_id, status=AnswerStatus.CHOSEN, choice_id=choice.id)


def question_lines(question: Question, factor: DecisionFactor | None) -> tuple[str, ...]:
    """A question with its reason and its choices, numbered from 1, and under a researched
    question the site its decision factor came from."""
    choices = (f"{number}. {choice.text}" for number, choice in enumerate(question.choices, 1))
    source = source_line_of(factor)
    sourced = () if source is None else (plain_text(source),)
    return (question.text, question.reason, *choices, *sourced)


def parse_arguments(arguments: Sequence[str]) -> tuple[str, bool] | None:
    """The input text and whether --skip-all was given; missing unless there is one text."""
    texts = [argument for argument in arguments if argument != SKIP_ALL_FLAG]
    if len(texts) != 1:
        return None
    return texts[0], SKIP_ALL_FLAG in arguments


def main(arguments: list[str]) -> int:
    parsed = parse_arguments(arguments)
    if parsed is None:
        print(USAGE)
        return 2
    input_text, skip_all = parsed
    try:
        return asyncio.run(_run_with_services(input_text, load_env(), skip_all))
    except (MissingSettingError, InvalidSettingError, RejectedKeyError) as error:
        print(error)
        return 1


async def _run_with_services(input_text: str, env: Mapping[str, str], skip_all: bool) -> int:
    """Run with the real model and the sources `SHOPPER_SOURCES` chooses, traced in LangSmith
    when `LANGSMITH_TRACING` is on."""
    chat = nebius_chat(require(env, NEBIUS_KEY_NAME))
    async with httpx.AsyncClient() as client:
        with traced(tracing_settings(env), input_text) as record_report:
            sources = sources_from_env(env, client)
            return await run(
                input_text, chat, sources, skip_all=skip_all, record_report=record_report
            )


if __name__ == "__main__":
    # Piped output on Windows defaults to cp1252, which cannot encode the euro sign reliably.
    sys.stdout.reconfigure(encoding="utf-8")
    # PowerShell starts piped input with a byte-order mark, which would make the first answer
    # unreadable.
    sys.stdin.reconfigure(encoding="utf-8-sig")
    # The credits each agent used, one line per agent, on the error stream.
    usage_log = logging.getLogger(USAGE_LOGGER)
    usage_log.addHandler(logging.StreamHandler(sys.stderr))
    usage_log.setLevel(logging.INFO)
    sys.exit(main(sys.argv[1:]))
