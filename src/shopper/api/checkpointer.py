"""The checkpointer the sessions are saved with: Postgres when `DATABASE_URL` is set, otherwise
the SQLite file (docs/architecture/sessions.md). Both with the state's serde."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from shopper.graph.graph import state_serde

Checkpointer = AsyncSqliteSaver | AsyncPostgresSaver
# What the Postgres saver needs of each connection, as its own `from_conn_string` sets it.
_POSTGRES_CONNECTION = {"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}


def make_checkpointer(database_url: str | None, database: Path) -> Checkpointer:
    """The checkpointer, over a connection not opened yet, so making it connects to nothing;
    `saved_sessions` opens it. Made inside the running event loop, as both savers ask.

    aiosqlite logs every statement with its parameters at debug level, and those hold the saved
    input, so its logger is kept at info.
    """
    if database_url is not None:
        pool = AsyncConnectionPool(database_url, open=False, kwargs=_POSTGRES_CONNECTION)
        return AsyncPostgresSaver(pool, serde=state_serde())
    logging.getLogger("aiosqlite").setLevel(logging.INFO)
    return AsyncSqliteSaver(aiosqlite.connect(database), serde=state_serde())


@asynccontextmanager
async def saved_sessions(
    database: Path, database_url: str | None = None
) -> AsyncGenerator[Checkpointer]:
    """The checkpointer `make_checkpointer` chooses, its connection open and its tables made;
    closed at the end."""
    checkpointer = make_checkpointer(database_url, database)
    if database_url is None:
        database.parent.mkdir(parents=True, exist_ok=True)
    async with checkpointer.conn:
        await checkpointer.setup()
        yield checkpointer
