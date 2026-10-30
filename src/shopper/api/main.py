"""The API as uvicorn runs it, in one worker process: the SQLite file, the cache, the credit ledger
and the running sessions are each per process.

uv run uvicorn shopper.api.main:app_from_env --factory --workers 1 --no-access-log
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from langgraph.checkpoint.base import BaseCheckpointSaver

from shopper.agents.default import DEFAULT_AGENTS
from shopper.agents.stubs import STUB_AGENTS
from shopper.api.app import create_app
from shopper.api.checkpointer import saved_sessions
from shopper.config import (
    NEBIUS_KEY_NAME,
    SESSIONS_DATABASE,
    agents_mode,
    database_url,
    frontend_origins,
    load_env,
    require,
    sessions_per_day,
    sessions_per_ip_per_hour,
    tracing_settings,
    trusted_proxy_hops,
)
from shopper.llm import nebius_chat
from shopper.tools.sources import sources_from_env
from shopper.tracing import tracer


def app_from_env() -> FastAPI:
    """The app on the real model, the agents `SHOPPER_AGENTS` chooses, the sources
    `SHOPPER_SOURCES` chooses, the sessions saved in Postgres at `DATABASE_URL` or else in
    `SESSIONS_DATABASE`, and the limits of sessions per client IP and per day its settings set."""
    env = load_env()
    client = httpx.AsyncClient()
    chat = nebius_chat(require(env, NEBIUS_KEY_NAME))
    tracing_on = tracing_settings(env)
    return create_app(
        chat,
        sources_from_env(env, client),
        _sessions_closing(client, database_url(env)),
        agents=STUB_AGENTS if agents_mode(env) == "stubs" else DEFAULT_AGENTS,
        origins=frontend_origins(env),
        trace=tracer(tracing_on),
        tracing=tracing_on is not None,
        sessions_per_hour=sessions_per_ip_per_hour(env),
        sessions_per_day=sessions_per_day(env),
        trusted_proxy_hops=trusted_proxy_hops(env),
    )


@asynccontextmanager
async def _sessions_closing(
    client: httpx.AsyncClient, database_url: str | None
) -> AsyncGenerator[BaseCheckpointSaver]:
    """The saved sessions; the HTTP client the sources use closes with them, at shutdown."""
    async with client, saved_sessions(SESSIONS_DATABASE, database_url) as saver:
        yield saver
