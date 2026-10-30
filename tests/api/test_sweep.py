"""The sweep that deletes a session 7 days after its latest checkpoint, through the saver's own
listing and deletion, on a SQLite file whose checkpoints the test writes at times it sets."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver, empty_checkpoint

from shopper.api.checkpointer import saved_sessions
from shopper.api.sweep import sweep, swept

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


async def saved_at(saver: BaseCheckpointSaver, thread_id: str, at: datetime) -> None:
    """A checkpoint of the thread, written as if at that time."""
    checkpoint = empty_checkpoint() | {"ts": at.isoformat()}
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    await saver.aput(config, checkpoint, {}, {})


async def threads(saver: BaseCheckpointSaver) -> set[str]:
    return {saved.config["configurable"]["thread_id"] async for saved in saver.alist(None)}


def on_saver[T](tmp_path: Path, scenario: Callable[[BaseCheckpointSaver], Awaitable[T]]) -> T:
    async def run() -> T:
        async with saved_sessions(tmp_path / "sessions.sqlite") as saver:
            return await scenario(saver)

    return asyncio.run(run())


def test_the_sweep_deletes_a_session_older_than_7_days_keeps_a_newer_one_and_skips_a_running_one(
    tmp_path: Path,
) -> None:
    async def scenario(saver: BaseCheckpointSaver) -> tuple[tuple[str, ...], set[str]]:
        await saved_at(saver, "old", NOW - timedelta(days=7, minutes=1))
        await saved_at(saver, "new", NOW - timedelta(days=6, hours=23))
        await saved_at(saver, "old-and-running", NOW - timedelta(days=30))
        # Its first checkpoint is old, its newest is not.
        await saved_at(saver, "answered-lately", NOW - timedelta(days=9))
        await saved_at(saver, "answered-lately", NOW - timedelta(days=1))
        deleted = await sweep(saver, running={"old-and-running"}, now=NOW)
        return deleted, await threads(saver)

    deleted, kept = on_saver(tmp_path, scenario)

    assert deleted == ("old",)
    assert kept == {"new", "old-and-running", "answered-lately"}


def test_a_session_is_kept_for_7_days_to_the_minute(tmp_path: Path) -> None:
    async def scenario(saver: BaseCheckpointSaver) -> tuple[str, ...]:
        await saved_at(saver, "seven-days", NOW - timedelta(days=7))
        return await sweep(saver, running=set(), now=NOW)

    assert on_saver(tmp_path, scenario) == ()


def test_a_pass_that_fails_logs_its_code_only_and_does_not_raise(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    async def scenario(saver: BaseCheckpointSaver) -> None:
        await saver.conn.close()
        await swept(saver, running=set(), now=NOW)

    with caplog.at_level(logging.ERROR):
        on_saver(tmp_path, scenario)

    assert [record.getMessage() for record in caplog.records] == [
        "ValueError: code sweep_failed, session none, agent none"
    ]
