"""Errors as the API logs them: no personal data (docs/service_architecture.md, "Logs")."""

import logging
from typing import Literal

from shopper.api.models import ResponseErrorCode, RunErrorCode
from shopper.state import Agent

# The code of a pass of the session sweep that failed; logged only, never sent.
SweepErrorCode = Literal["sweep_failed"]

_LOG = logging.getLogger(__name__)


def log_error(
    error: BaseException,
    code: ResponseErrorCode | RunErrorCode | SweepErrorCode,
    session_id: str | None,
    agent: Agent | None,
) -> None:
    """Log an error by its class, code, session id and agent, never its message or traceback,
    which can carry the input."""
    _LOG.error(
        "%s: code %s, session %s, agent %s",
        type(error).__name__,
        code,
        session_id or "none",
        agent or "none",
    )
