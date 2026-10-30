"""Writes the API's OpenAPI schema to a file, with no server and no keys; the frontend's types are
generated from it (docs/service_architecture.md, "API surface").

uv run python -m shopper.api.schema web/lib/api/openapi.json
"""

import json
import sys
from pathlib import Path

from shopper.api.app import openapi_schema


def write_schema(path: Path) -> None:
    """The schema as JSON, with LF line endings and a final newline, so a check that the
    committed file is current compares it byte for byte."""
    text = json.dumps(openapi_schema(), indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print("Usage: python -m shopper.api.schema <file>", file=sys.stderr)
        return 2
    write_schema(Path(arguments[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
