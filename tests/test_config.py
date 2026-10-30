import os
import subprocess
import sys
from pathlib import Path

import pytest

from shopper.config import (
    DEFAULT_MODEL_IDS,
    InvalidSettingError,
    MissingSettingError,
    agents_mode,
    database_url,
    frontend_origins,
    load_env,
    model_ids,
    require,
    sessions_per_day,
    sessions_per_ip_per_hour,
    sources_mode,
    tavily_daily_credit_limit,
    tracing_settings,
    trusted_proxy_hops,
)


def test_a_model_override_is_used_for_its_tier_alone() -> None:
    ids = model_ids({"NEBIUS_MODEL_SMALL": "nvidia/other-small"})

    assert ids == {**DEFAULT_MODEL_IDS, "small": "nvidia/other-small"}


@pytest.mark.parametrize("env", [{}, {"NEBIUS_MODEL_MEDIUM": ""}, {"NEBIUS_MODEL_MEDIUM": "  "}])
def test_an_unset_or_empty_model_override_leaves_the_default(env: dict[str, str]) -> None:
    assert model_ids(env) == DEFAULT_MODEL_IDS


def test_the_models_are_read_from_the_environment_when_the_settings_load(tmp_path: Path) -> None:
    # A process of its own, as the IDs are set once, on import; in a folder with no .env.
    printed = subprocess.run(
        [sys.executable, "-c", "from shopper.config import MODEL_IDS; print(dict(MODEL_IDS))"],
        cwd=tmp_path,
        env={**os.environ, "NEBIUS_MODEL_LARGE": "nvidia/other-large"},
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert "'large': 'nvidia/other-large'" in printed


def test_env_file_values_are_read_and_the_process_environment_wins(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("# comment\nTAVILY_API_KEY=from-file\nNEBIUS_TOKEN_FACTORY = 'quoted' \n\n")

    env = load_env(dotenv, environ={"TAVILY_API_KEY": "from-process"})

    assert env["NEBIUS_TOKEN_FACTORY"] == "quoted"
    assert env["TAVILY_API_KEY"] == "from-process"


def test_a_missing_env_file_is_not_an_error(tmp_path: Path) -> None:
    assert load_env(tmp_path / ".env", environ={"A": "1"}) == {"A": "1"}


def test_missing_key_fails_with_a_message_naming_the_variable() -> None:
    with pytest.raises(MissingSettingError, match="NEBIUS_TOKEN_FACTORY"):
        require({"NEBIUS_TOKEN_FACTORY": ""}, "NEBIUS_TOKEN_FACTORY")


def test_sources_are_live_unless_fixtures_are_chosen() -> None:
    assert sources_mode({}) == "live"
    assert sources_mode({"SHOPPER_SOURCES": "fixtures"}) == "fixtures"


def test_an_unknown_sources_mode_is_a_configuration_error() -> None:
    with pytest.raises(InvalidSettingError, match="SHOPPER_SOURCES"):
        sources_mode({"SHOPPER_SOURCES": "recorded"})


def test_the_agents_are_the_real_ones_unless_the_stubs_are_chosen() -> None:
    assert agents_mode({}) == "real"
    assert agents_mode({"SHOPPER_AGENTS": "stubs"}) == "stubs"


def test_an_unknown_agents_mode_is_a_configuration_error() -> None:
    with pytest.raises(InvalidSettingError, match="SHOPPER_AGENTS"):
        agents_mode({"SHOPPER_AGENTS": "fake"})


def test_the_daily_credit_limit_is_100_unless_set() -> None:
    assert tavily_daily_credit_limit({}) == 100
    assert tavily_daily_credit_limit({"TAVILY_DAILY_CREDIT_LIMIT": "400"}) == 400


def test_a_daily_credit_limit_that_is_not_a_whole_number_is_a_configuration_error() -> None:
    with pytest.raises(InvalidSettingError, match="TAVILY_DAILY_CREDIT_LIMIT"):
        tavily_daily_credit_limit({"TAVILY_DAILY_CREDIT_LIMIT": "ten"})


def test_a_client_ip_may_start_30_sessions_an_hour_unless_set() -> None:
    assert sessions_per_ip_per_hour({}) == 30
    assert sessions_per_ip_per_hour({"SESSIONS_PER_IP_PER_HOUR": "60"}) == 60


def test_all_clients_together_may_start_100_sessions_a_day_unless_set() -> None:
    assert sessions_per_day({}) == 100
    assert sessions_per_day({"SESSIONS_PER_DAY": "10"}) == 10


def test_no_proxy_is_trusted_unless_set() -> None:
    assert trusted_proxy_hops({}) == 0
    assert trusted_proxy_hops({"TRUSTED_PROXY_HOPS": "1"}) == 1


def test_a_limit_or_a_hop_count_that_is_not_a_whole_number_is_a_configuration_error() -> None:
    with pytest.raises(InvalidSettingError, match="SESSIONS_PER_IP_PER_HOUR"):
        sessions_per_ip_per_hour({"SESSIONS_PER_IP_PER_HOUR": "-1"})
    with pytest.raises(InvalidSettingError, match="TRUSTED_PROXY_HOPS"):
        trusted_proxy_hops({"TRUSTED_PROXY_HOPS": "one"})


def test_the_sessions_are_in_sqlite_unless_a_database_url_is_set() -> None:
    assert database_url({}) is None
    assert database_url({"DATABASE_URL": " "}) is None
    assert database_url({"DATABASE_URL": "postgresql://db/sessions"}) == "postgresql://db/sessions"


def test_the_frontend_origins_are_the_local_dev_server_unless_set() -> None:
    assert frontend_origins({}) == ("http://localhost:3000",)
    assert frontend_origins(
        {"FRONTEND_ORIGINS": "https://copilot.example, https://preview.copilot.example,"}
    ) == ("https://copilot.example", "https://preview.copilot.example")


def test_tracing_is_off_unless_set_to_true() -> None:
    assert tracing_settings({}) is None
    assert tracing_settings({"LANGSMITH_TRACING": "false"}) is None


def test_tracing_on_takes_the_key_and_the_project_from_the_settings() -> None:
    env = {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "k", "LANGSMITH_PROJECT": "runs"}

    settings = tracing_settings(env)

    assert settings is not None
    assert (settings.api_key, settings.project) == ("k", "runs")
    assert settings.endpoint == "https://eu.api.smith.langchain.com"


def test_tracing_on_without_a_project_uses_the_default_one() -> None:
    settings = tracing_settings({"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "k"})

    assert settings is not None
    assert settings.project == "true-cost-copilot"


def test_tracing_on_without_a_key_names_the_missing_variable() -> None:
    with pytest.raises(MissingSettingError, match="LANGSMITH_API_KEY"):
        tracing_settings({"LANGSMITH_TRACING": "true"})


def test_a_tracing_value_that_is_not_true_or_false_is_a_configuration_error() -> None:
    with pytest.raises(InvalidSettingError, match="LANGSMITH_TRACING"):
        tracing_settings({"LANGSMITH_TRACING": "yes"})
