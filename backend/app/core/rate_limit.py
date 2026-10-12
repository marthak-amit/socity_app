"""Small in-process sliding-window limiter (per-IP protection). Per-phone OTP limits live in the DB
so they hold across workers; this one is a cheap extra layer for unauthenticated endpoints."""

import time
from collections import defaultdict, deque

from app.core.errors import too_many


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            raise too_many("rate_limited", "Too many requests, try again later")
        q.append(now)

    def reset(self) -> None:
        self._hits.clear()


limiter = SlidingWindowLimiter()
