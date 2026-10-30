"""The command that writes the API's OpenAPI schema with no server and no keys."""

import asyncio
import json
from pathlib import Path

import httpx

from fakes import fake_chat
from shopper.api.app import create_app
from shopper.api.checkpointer import saved_sessions
from shopper.api.schema import write_schema
from shopper.tools.sources import fixture_sources

FIXTURES = Path(__file__).parent.parent / "fixtures"


def served_schema(tmp_path: Path) -> object:
    """`/openapi.json` as the app built by `create_app` serves it, its lifespan run."""

    async def run() -> object:
        chat, _ = fake_chat(())
        app = create_app(
            chat,
            fixture_sources(FIXTURES, tmp_path / "cache"),
            saved_sessions(tmp_path / "sessions.sqlite"),
        )
        transport = httpx.ASGITransport(app=app)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        ):
            return (await client.get("/openapi.json")).json()

    return asyncio.run(run())


def test_the_schema_written_with_no_server_is_the_one_the_app_serves(tmp_path: Path) -> None:
    written = tmp_path / "openapi.json"

    write_schema(written)

    assert json.loads(written.read_text(encoding="utf-8")) == served_schema(tmp_path)


def test_the_written_schema_has_lf_line_endings_and_ends_with_a_newline(tmp_path: Path) -> None:
    written = tmp_path / "openapi.json"

    write_schema(written)

    data = written.read_bytes()
    assert b"\r" not in data
    assert data.endswith(b"}\n")
