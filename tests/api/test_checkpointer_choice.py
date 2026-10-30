"""Which checkpointer the sessions are saved with, chosen by `DATABASE_URL` and made without
connecting: offline tests never use Postgres."""

import asyncio
from pathlib import Path

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from shopper.api.checkpointer import Checkpointer, make_checkpointer


def made(database_url: str | None, tmp_path: Path) -> Checkpointer:
    """The checkpointer, made in a running event loop as the lifespan makes it."""

    async def make() -> Checkpointer:
        return make_checkpointer(database_url, tmp_path / "sessions.sqlite")

    return asyncio.run(make())


def test_with_no_database_url_the_sessions_are_saved_in_the_sqlite_file(tmp_path: Path) -> None:
    checkpointer = made(None, tmp_path)

    assert type(checkpointer) is AsyncSqliteSaver
    assert not (tmp_path / "sessions.sqlite").exists()


def test_with_a_database_url_they_are_saved_in_postgres(tmp_path: Path) -> None:
    # No server answers at this address: making the checkpointer must not connect.
    checkpointer = made("postgresql://nobody@127.0.0.1:1/sessions", tmp_path)

    assert type(checkpointer) is AsyncPostgresSaver
