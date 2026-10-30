"""The brief store: what category research produced, kept so a category is researched once.

One file per category in the `brief` folder of the sources' cache folder, so live and recorded
research never mix. A brief with enough factors does not expire; a thin one lasts a day. Rules:
docs/architecture/data_sources.md ("Cache and fixtures").
"""

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from shopper.config import ENOUGH_RESEARCHED_FACTORS, THIN_BRIEF_MAX_AGE
from shopper.state import DecisionFactor, DomainModel, Question, TrailEntry
from shopper.tools.cache import normalised_query
from shopper.tools.results import Clock

BRIEF_FOLDER = "brief"
_NOT_IN_A_FILE_NAME = re.compile(r"[^a-z0-9]+")


class Brief(DomainModel):
    """What category research produced for one category.

    The researched factors, a question for each one that could be phrased, the usage
    frequencies picked for the category, the local category term (missing when none passed its
    check) and the trail entries of the research.
    """

    factors: tuple[DecisionFactor, ...] = ()
    questions: tuple[Question, ...] = ()
    usage_frequencies: tuple[str, ...]
    local_term: str | None = None
    trail: tuple[TrailEntry, ...] = ()


class StoredBrief(DomainModel):
    """A brief as it is kept. `version` changes when what produced the brief changes."""

    category: str
    version: str
    researched_at: datetime
    brief: Brief


class BriefStore(Protocol):
    """Where the brief agent keeps a category's brief; passed to it as a tool."""

    def read(self, category: str, version: str) -> StoredBrief | None: ...

    def write(self, category: str, version: str, brief: Brief) -> None: ...


@dataclass(frozen=True)
class BriefStoreOnDisk:
    """The store's two operations, bound to a folder and a clock by `brief_store`."""

    read: Callable[[str, str], StoredBrief | None]
    write: Callable[[str, str, Brief], None]


def brief_store(cache_folder: Path, clock: Clock) -> BriefStore:
    """The store in the sources' cache folder, stamping and ageing briefs with their clock."""
    folder = cache_folder / BRIEF_FOLDER
    return BriefStoreOnDisk(
        read=lambda category, version: read_brief(folder, category, version, clock()),
        write=lambda category, version, brief: write_brief(
            folder, category, version, brief, clock()
        ),
    )


def read_brief(folder: Path, category: str, version: str, now: datetime) -> StoredBrief | None:
    """The category's brief, unless none is stored, its version differs or it has expired.

    A file that no longer reads as a brief, cut off or of an older shape, is missing too: it is
    researched again and replaced.
    """
    path = _path(folder, normalised_query(category))
    if not path.is_file():
        return None
    try:
        stored = StoredBrief.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError:
        return None
    if stored.category != normalised_query(category) or stored.version != version:
        return None
    is_thin = len(stored.brief.factors) < ENOUGH_RESEARCHED_FACTORS
    if is_thin and now - stored.researched_at > THIN_BRIEF_MAX_AGE:
        return None
    return stored


def write_brief(folder: Path, category: str, version: str, brief: Brief, now: datetime) -> None:
    """Store the brief as the category's one file, replacing an earlier one."""
    stored = StoredBrief(
        category=normalised_query(category), version=version, researched_at=now, brief=brief
    )
    path = _path(folder, stored.category)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stored.model_dump_json(indent=2), encoding="utf-8")


def _path(folder: Path, category: str) -> Path:
    """A readable file name; the hash keeps two categories that read alike apart."""
    readable = _NOT_IN_A_FILE_NAME.sub("-", category).strip("-") or "category"
    digest = hashlib.sha256(category.encode("utf-8")).hexdigest()[:8]
    return folder / f"{readable}-{digest}.json"
