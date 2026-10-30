"""The app as uvicorn runs it: what its settings reach. A ceiling of 0 refuses a start before any
model call, so nothing here touches a live service."""

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from shopper.api.main import app_from_env


def from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **settings: str) -> FastAPI:
    """The app on these settings, with no .env and its sessions in a folder of the test's."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEBIUS_TOKEN_FACTORY", "test-key")
    monkeypatch.setenv("SHOPPER_SOURCES", "fixtures")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    return app_from_env()


def request(app: FastAPI, method: str, path: str, **sent: object) -> httpx.Response:
    """One request to the app, with its lifespan run here: the ASGI transport does not run it."""

    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        ):
            return await client.request(method, path, **sent)

    return asyncio.run(run())


def test_the_ceiling_per_day_is_the_one_its_setting_gives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = from_env(tmp_path, monkeypatch, SESSIONS_PER_DAY="0")

    response = request(app, "POST", "/sessions", json={"input": "a frying pan"})

    assert response.status_code == 429
    assert response.json()["code"] == "too_many_sessions_today"


def test_health_says_the_runs_are_traced_when_the_setting_turns_it_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = from_env(tmp_path, monkeypatch, LANGSMITH_TRACING="true", LANGSMITH_API_KEY="test-key")

    assert request(app, "GET", "/health").json()["tracing"] is True


def test_health_says_the_runs_are_not_traced_when_it_is_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert request(from_env(tmp_path, monkeypatch), "GET", "/health").json()["tracing"] is False
