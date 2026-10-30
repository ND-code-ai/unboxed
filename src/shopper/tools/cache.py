"""The on-disk cache: one file per stored response, named by a hash of its key.

Clearing the cache is deleting the folder. Only successes are written (data_sources.md, "Cache
and fixtures").
"""

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from shopper.tools.results import Service, StoredResponse


def normalised_query(search_query: str) -> str:
    """Trimmed, lower-cased, whitespace collapsed."""
    return " ".join(search_query.lower().split())


def search_key(search_query: str, parameters: Mapping[str, Any]) -> str:
    """The normalised search query plus every parameter that changes the results."""
    return json.dumps(
        {"search_query": normalised_query(search_query), "parameters": dict(parameters)},
        sort_keys=True,
    )


def read_cached(
    folder: Path, service: Service, key: str, max_age: timedelta | None, now: datetime
) -> StoredResponse | None:
    """The stored response for the key, unless there is none or it is older than `max_age`."""
    path = _path(folder, service, key)
    if not path.is_file():
        return None
    stored = StoredResponse.model_validate_json(path.read_text(encoding="utf-8"))
    if max_age is not None and now - stored.retrieved_at > max_age:
        return None
    return stored


def write_cached(folder: Path, key: str, stored: StoredResponse) -> None:
    path = _path(folder, stored.service, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stored.model_dump_json(indent=2), encoding="utf-8")


def _path(folder: Path, service: Service, key: str) -> Path:
    name = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return folder / service / f"{name}.json"
