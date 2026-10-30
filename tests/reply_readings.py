"""The model's readings of a reply, written by hand, and the replies to the stub brief's
questions that the session and API tests send."""

import json
from collections.abc import Mapping
from dataclasses import replace

from shopper.agents.brief.reply import read_reply
from shopper.agents.stubs import STUB_AGENTS

# The stub agents, with the reply read by the real reader.
REPLY_AGENTS = replace(STUB_AGENTS, reply=read_reply)
# The reading numbers the stub brief's factors: the hob 1, the seasoning oil 2, usage 3.
STUB_HOB_NUMBER, STUB_USAGE_NUMBER = 1, 3


def reading(*requirements: Mapping[str, object]) -> str:
    """The model's reply to the call that reads the reply, written by hand."""
    return json.dumps({"requirements": list(requirements)})


def said(
    factor: int | str,
    phrase: str,
    *,
    choice: int | None = None,
    value: str | None = None,
    frequency: str | None = None,
    not_sure: bool = False,
    changes: str | None = None,
) -> dict[str, object]:
    """One thing the reply says: about a factor by its number in the prompt, or "new"."""
    return {
        "factor": factor,
        "choice": choice,
        "value": value,
        "frequency": frequency,
        "phrase": phrase,
        "not_sure": not_sure,
        "changes": changes,
    }


INDUCTION_WEEKLY = "I cook on induction, about once a week"
READ_INDUCTION_WEEKLY = reading(
    said(STUB_HOB_NUMBER, "on induction", choice=3),
    said(STUB_USAGE_NUMBER, "about once a week", frequency="about_once_a_week"),
)
# A reply that names nothing the session can use: its one phrase holds the category.
NOTHING_NAMED = "a frying pan please"
READ_NOTHING_NAMED = reading(said("new", NOTHING_NAMED))
