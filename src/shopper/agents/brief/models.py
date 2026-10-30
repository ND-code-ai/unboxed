"""What the brief agent's model calls return, and what its steps hand to each other.

The pydantic models are the schemas of the model calls; the tuples carry results between the
steps in `agent.py`.
"""

from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, field_validator

from shopper.llm import Completion
from shopper.state import (
    Answer,
    DecisionFactor,
    Question,
    StatedBy,
    StatedIn,
    TrailEntry,
    Warning,
)
from shopper.tools.brief_store import Brief
from shopper.tools.results import SearchResult


class ReadFactor(BaseModel):
    """One decision factor as the model returns it: what it is, and the result it cites. A
    recurring-cost factor may also quote its amount, interval and pack count from that result;
    code reads the yearly cost from them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: Literal["compatibility", "requirement", "recurring_cost", "care"]
    why: str
    result: int
    quote: str
    stated_by: StatedBy
    amount_quote: str | None
    interval_quote: str | None
    pack_count_quote: str | None


class Gap(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    what: str
    reason: str


class Reading(BaseModel):
    """The fields the model fills when it reads the search results, and nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    factors: list[ReadFactor]
    gaps: list[Gap]
    follow_up_query: str | None


class Phrased(BaseModel):
    """One factor as the model phrased it: a question with its reason and choices, or for a care
    factor the statement alone."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    factor: int
    text: str
    reason: str | None
    choices: list[str]


class Phrasing(BaseModel):
    """The fields the model fills in the phrasing call, and nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    questions: list[Phrased]
    usage_frequencies: list[str]


class StatedRequirement(BaseModel):
    """One requirement the request states, as the model returns it: the factor it is about by
    its number, or "new", and the request's own words it is taken from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    factor: int | Literal["new"]
    choice: int | None
    value: str | None
    frequency: str | None
    phrase: str


class StatedReading(BaseModel):
    """The fields the model fills when it reads what the request states, and nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirements: list[StatedRequirement]


class ReplyRequirement(StatedRequirement):
    """One thing the reply says, as the model returns it: a stated requirement, or that the user
    does not know or mind, or that the phrase asks to change the category or the budget."""

    not_sure: bool
    changes: Literal["budget", "category"] | None


class ReplyReading(BaseModel):
    """The fields the model fills when it reads the reply, and nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirements: list[ReplyRequirement]


class LocalTerm(BaseModel):
    """The field the model fills when it gives the local category term, and nothing else. A term
    with no letter in it ("...", which the model wrote now and then in task 1.15) is invalid
    output, so the model is asked again."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    local_term: str

    @field_validator("local_term")
    @classmethod
    def _has_a_letter(cls, term: str) -> str:
        if not any(character.isalpha() for character in term):
            raise ValueError("the local term holds no word")
        return term


class FoundTerm(NamedTuple):
    """The local category term that passed the check, missing when none did, its trail entries,
    and whether the call succeeded."""

    term: str | None
    trail: tuple[TrailEntry, ...]
    succeeded: bool


class Cited(NamedTuple):
    """A researched factor with the search result it cites, and the read's factor it came
    from."""

    factor: DecisionFactor
    result: SearchResult
    read: ReadFactor


class ReadResult(NamedTuple):
    """What a read gave: the factors that pass the checks, and its trail entries.

    `summary` is the entry for the read itself, `details` one entry per factor and per gap.
    `reply` is the model's reply; it is missing when there was nothing to read or the call failed.
    """

    cited: tuple[Cited, ...]
    summary: tuple[TrailEntry, ...]
    details: tuple[TrailEntry, ...]
    reply: Completion[Reading] | None


class PhrasingResult(NamedTuple):
    """What the phrasing call gave: the questions that pass the checks, the usage frequencies
    to offer, and its trail entries."""

    questions: tuple[Question, ...]
    frequencies: tuple[str, ...]
    trail: tuple[TrailEntry, ...]
    succeeded: bool


class Followed(NamedTuple):
    """The read that stands after the follow-up search, and the trail entries of that search."""

    read: ReadResult
    trail: tuple[TrailEntry, ...]
    second_read_failed: bool = False


class Researched(NamedTuple):
    """A category's brief as it was just researched.

    It is stored only when both template searches, every read and the phrasing succeeded.
    """

    brief: Brief
    every_step_succeeded: bool
    phrasing_failed: bool


class Said(NamedTuple):
    """The words requirements are read from: the request's, or the reply's to the questions."""

    text: str
    stated_in: StatedIn


class OwnFactor(NamedTuple):
    """A factor of the user's own, and the stated answer that settles it."""

    factor: DecisionFactor
    answer: Answer


class Stated(NamedTuple):
    """What the request states: an answer per factor it settles, the trail entries, the warning
    when it could not be read, and the user's own factors, which its answers settle too."""

    answers: tuple[Answer, ...]
    trail: tuple[TrailEntry, ...]
    warnings: tuple[Warning, ...] = ()
    factors: tuple[DecisionFactor, ...] = ()
