"""LangSmith tracing of one session: a developer tool, off unless .env turns it on.

LangSmith takes its settings from here, never from the environment on its own: the context is
set either way, so tracing stays off even when the process environment asks LangSmith for it.
The trace holds what the user typed, so the deployed app traces only by the developer's choice
and with a notice (docs/eu_market.md, "Personal data").
"""

import threading
from collections.abc import Callable, Generator, Sequence
from contextlib import AbstractContextManager, contextmanager

import langsmith

from shopper.config import TracingSettings

SESSION_RUN_NAME = "session"

# Takes the report's printed lines; with tracing on they become the session run's output.
RecordReport = Callable[[Sequence[str]], None]
# Traces what runs inside as one trace, given the input it started with.
Tracer = Callable[[str], AbstractContextManager[RecordReport]]
# Hands what a trace still holds to LangSmith, once the trace has ended.
Flush = Callable[[langsmith.Client], None]


def _flush_now(client: langsmith.Client) -> None:
    """For the terminal app: it exits next, so it waits."""
    client.flush()


def _flush_aside(client: langsmith.Client) -> None:
    """For the API: `flush` blocks and a run ends on the event loop every stream shares, so it
    gets a thread of its own, which never holds up a shutdown."""
    threading.Thread(target=client.flush, daemon=True).start()


@contextmanager
def traced(
    settings: TracingSettings | None,
    input_text: str,
    client: langsmith.Client | None = None,
    flush: Flush = _flush_now,
) -> Generator[RecordReport]:
    """Trace everything run inside as one trace, or nothing when `settings` is None.

    The graph's nodes become runs under it and each model call a child run of its node. Gives a
    function that records the printed report as the session's output. `client` replaces the one
    built from the settings; a test passes a fake.
    """
    if settings is None:
        with langsmith.tracing_context(enabled=False, client=client):
            yield _not_recorded
        return
    client = client or langsmith.Client(api_url=settings.endpoint, api_key=settings.api_key)
    try:
        with (
            langsmith.tracing_context(enabled=True, client=client, project_name=settings.project),
            langsmith.trace(SESSION_RUN_NAME, inputs={"input": input_text}) as session,
        ):
            yield lambda lines: session.add_outputs({"report": "\n".join(lines)})
    finally:
        flush(client)


def tracer(settings: TracingSettings | None, client: langsmith.Client | None = None) -> Tracer:
    """What the API traces each run in: `traced` with these settings, given the run's input."""
    return lambda input_text: traced(settings, input_text, client, _flush_aside)


def _not_recorded(lines: Sequence[str]) -> None:
    """With tracing off there is no session run to record the report on."""


# Tracing off, whatever the process environment asks of LangSmith.
UNTRACED = tracer(None)
