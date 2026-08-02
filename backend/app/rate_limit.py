import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request


class RateLimiter:
    """Per-client, in-memory, fixed-window rate limiter.

    In-memory and per-process by design -- MatchIQ's backend runs as a
    single instance (see railway.json), so this doesn't need Redis or any
    shared store to be effective.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._lock = Lock()
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            timestamps = self._hits[key]
            while timestamps and timestamps[0] < cutoff:
                timestamps.pop(0)
            if len(timestamps) >= self._max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests -- limit is {self._max_requests} per {int(self._window_seconds)}s",
                )
            timestamps.append(now)


# The chat endpoint is the one that spends real money (OpenAI API calls per
# request) -- 20/min per IP is generous for a real user asking questions but
# bounds worst-case cost from a scripted client hammering it.
chat_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)


def rate_limit_chat(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    chat_rate_limiter.check(client_ip)
