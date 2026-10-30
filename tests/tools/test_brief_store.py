"""The brief store: one stored brief per category, on disk under the sources' cache folder."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fakes import Clock
from shopper.agents.brief.usage_frequency import DEFAULT_FREQUENCIES
from shopper.state import (
    Agent,
    Choice,
    DecisionFactor,
    FactorKind,
    Question,
    Source,
    SourceKind,
    TrailEntry,
    TrailKind,
)
from shopper.tools.brief_store import Brief, brief_store

NOON = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
VERSION = "prompts-and-models-1"


def factor(number: int) -> DecisionFactor:
    return DecisionFactor(
        id=f"researched-{number}",
        name=f"Factor {number}",
        kind=FactorKind.REQUIREMENT,
        why="It decides which options fit.",
        source=Source(kind=SourceKind.URL, reference=f"https://example.org/guide-{number}"),
    )


def brief(factors: int) -> Brief:
    """A brief with this many researched factors and a question about the first, if any."""
    question = Question(
        id="question-researched-1",
        factor_id="researched-1",
        text="Which size do you need?",
        reason="A pan that is too small is replaced early.",
        choices=(Choice(id="choice-1", text="Small"), Choice(id="choice-2", text="Large")),
    )
    return Brief(
        factors=tuple(factor(number) for number in range(1, factors + 1)),
        questions=(question,) if factors else (),
        usage_frequencies=DEFAULT_FREQUENCIES,
        trail=(
            TrailEntry(agent=Agent.BRIEF, kind=TrailKind.FOUND, summary=f"{factors} factors kept"),
        ),
    )


def test_a_stored_brief_is_read_back_with_the_time_it_was_stored(tmp_path: Path) -> None:
    store = brief_store(tmp_path, Clock(NOON))

    store.write("frying pan", VERSION, brief(3))
    stored = store.read("frying pan", VERSION)

    assert stored is not None
    assert stored.brief == brief(3)
    assert stored.researched_at == NOON


def test_a_category_that_was_never_stored_is_missing(tmp_path: Path) -> None:
    store = brief_store(tmp_path, Clock(NOON))

    store.write("frying pan", VERSION, brief(3))

    assert store.read("kettle", VERSION) is None


def test_case_and_spacing_do_not_change_the_category(tmp_path: Path) -> None:
    store = brief_store(tmp_path, Clock(NOON))

    store.write("frying pan", VERSION, brief(3))

    assert store.read("  Frying   PAN ", VERSION) is not None


def test_a_brief_stored_under_another_version_is_missing(tmp_path: Path) -> None:
    store = brief_store(tmp_path, Clock(NOON))

    store.write("frying pan", VERSION, brief(3))

    assert store.read("frying pan", "prompts-and-models-2") is None


def test_a_brief_with_three_factors_does_not_expire(tmp_path: Path) -> None:
    clock = Clock(NOON)
    store = brief_store(tmp_path, clock)

    store.write("frying pan", VERSION, brief(3))
    clock.now = NOON + timedelta(days=400)

    assert store.read("frying pan", VERSION) is not None


@pytest.mark.parametrize("factors", [0, 2])
def test_a_brief_with_fewer_than_three_factors_lasts_one_day(tmp_path: Path, factors: int) -> None:
    clock = Clock(NOON)
    store = brief_store(tmp_path, clock)

    store.write("kettle", VERSION, brief(factors))
    clock.now = NOON + timedelta(hours=23)
    same_day = store.read("kettle", VERSION)
    clock.now = NOON + timedelta(days=1, minutes=1)
    next_day = store.read("kettle", VERSION)

    assert same_day is not None
    assert next_day is None


def test_there_is_one_file_per_category_in_the_brief_folder(tmp_path: Path) -> None:
    store = brief_store(tmp_path, Clock(NOON))

    store.write("frying pan", VERSION, brief(3))
    store.write("frying pan", "prompts-and-models-2", brief(2))
    store.write("kettle", VERSION, brief(3))

    assert len(list((tmp_path / "brief").glob("*.json"))) == 2
    assert store.read("frying pan", "prompts-and-models-2") is not None


@pytest.mark.parametrize(
    "content",
    ['{"category": "frying pan", "an older shape": true}', '{"category": "frying', ""],
    ids=["another shape", "cut off", "empty"],
)
def test_a_file_that_is_no_longer_a_brief_is_missing(tmp_path: Path, content: str) -> None:
    store = brief_store(tmp_path, Clock(NOON))
    store.write("frying pan", VERSION, brief(3))
    (stored,) = (tmp_path / "brief").glob("*.json")

    stored.write_text(content, encoding="utf-8")

    assert store.read("frying pan", VERSION) is None
