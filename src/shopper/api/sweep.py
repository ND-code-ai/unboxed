"""The sweep that deletes each session `SESSION_RETENTION_DAYS` after its latest checkpoint, a
thread whose parsing call failed included (docs/eu_market.md, "Personal data"). It runs at
startup and then every `SWEEP_INTERVAL_SECONDS`, through the saver's own listing and deletion,
so both checkpointers share it."""

import asyncio
from collections.abc import Container
from datetime import datetime, timedelta

from langgraph.checkpoint.base import BaseCheckpointSaver

from shopper.api.error_log import log_error
from shopper.config import SESSION_RETENTION_DAYS, SWEEP_INTERVAL_SECONDS
from shopper.tools.results import Clock

RETENTION = timedelta(days=SESSION_RETENTION_DAYS)


async def sweep(
    saver: BaseCheckpointSaver, running: Container[str], now: datetime
) -> tuple[str, ...]:
    """Delete every session whose newest checkpoint is older than the retention, unless it is
    running; the ids deleted."""
    newest: dict[str, datetime] = {}
    async for saved in saver.alist(None):
        session_id = saved.config["configurable"]["thread_id"]
        at = datetime.fromisoformat(saved.checkpoint["ts"])
        newest[session_id] = max(at, newest.get(session_id, at))
    expired = tuple(
        session_id
        for session_id, at in newest.items()
        if now - at > RETENTION and session_id not in running
    )
    for session_id in expired:
        await saver.adelete_thread(session_id)
    return expired


async def swept(saver: BaseCheckpointSaver, running: Container[str], now: datetime) -> None:
    """One pass of the sweep; an error in it is logged by its class and code only, so the next
    pass still runs."""
    try:
        await sweep(saver, running, now)
    except Exception as error:
        log_error(error, "sweep_failed", None, None)


async def sweeping(saver: BaseCheckpointSaver, running: Container[str], clock: Clock) -> None:
    """A pass every interval, until cancelled; the first pass is the lifespan's, at startup."""
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
        await swept(saver, running, clock())
