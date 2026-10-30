"""The limit of sessions a client IP may start in an hour and the site-wide ceiling on sessions
started in a day, beside the daily credit limit: the deployment runs without endpoint auth, which
a browser could not hold a token for, so anyone with the URL can spend.

Counted in memory only; an IP is never saved, logged or put in a thread
(docs/eu_market.md, "Personal data").
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
# The key of a request whose connection has no address, which ASGI allows.
NO_ADDRESS = ""
# The code of a start refused by the ceiling; its message is fixed.
DayCeilingReached = Literal["too_many_sessions_today"]


@dataclass(frozen=True)
class StartLimit:
    """The sessions each client started in the last hour, by its IP, as the times they started,
    and the times of every session started in the last day. One worker process, so one count, kept
    up to date in place as `running` is."""

    per_hour: int
    trusted_proxy_hops: int
    started: dict[str, list[datetime]]
    per_day: int
    started_by_anyone: list[datetime]


@dataclass(frozen=True)
class TooManySessions:
    """A start refused: the client started as many sessions as the limit in the last hour, and
    the oldest of them leaves the hour after `wait`."""

    wait: timedelta


def client_address(hops: int, connection: str | None, forwarded_for: Sequence[str]) -> str:
    """The client's IP: the connection's own address when no proxy is trusted; behind `hops`
    trusted proxies, the `hops`th `X-Forwarded-For` entry from the right, which the nearest of
    them wrote. An entry left of it is the client's own writing, so it is never used: with fewer
    entries than proxies, the connection's address is."""
    entries = [entry.strip() for header in forwarded_for for entry in header.split(",")]
    entries = [entry for entry in entries if entry]
    if hops == 0 or len(entries) < hops:
        return connection or NO_ADDRESS
    return entries[-hops]


def admitted(
    limit: StartLimit, client: str, now: datetime
) -> TooManySessions | DayCeilingReached | None:
    """Count a session the client starts now; refused when it has started as many as the limit
    in the last hour, or when as many as the ceiling were started by anyone in the last day. A
    start refused by either counts towards neither. Every start older than its window is cleared
    first, for every client."""
    for address, times in list(limit.started.items()):
        times[:] = [time for time in times if now - time < HOUR]
        if not times:
            del limit.started[address]
    limit.started_by_anyone[:] = [time for time in limit.started_by_anyone if now - time < DAY]
    times = limit.started.get(client, [])
    if len(times) >= limit.per_hour:
        return TooManySessions(wait=times[0] + HOUR - now)
    if len(limit.started_by_anyone) >= limit.per_day:
        return "too_many_sessions_today"
    limit.started[client] = [*times, now]
    limit.started_by_anyone.append(now)
    return None


def limit_line(limit: StartLimit) -> str:
    """What startup logs of the limit: whether a proxy is trusted, and no IP."""
    hops = limit.trusted_proxy_hops
    if hops == 0:
        read = "the connection's own address"
    else:
        proxies = "1 proxy" if hops == 1 else f"{hops} proxies"
        read = f"read from X-Forwarded-For, {proxies} trusted"
    return f"Sessions per client IP: {limit.per_hour} an hour; the client IP is {read}"
