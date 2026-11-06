"""Twelve Data's per-minute limit: at most 8 credits per wall-clock minute per key (Basic plan).

The window refills at each minute's :00, as Twelve Data's does. Callers queue: `acquire` blocks until the
next minute rather than failing. Background jobs pass `block=False` and skip instead.

In-process on purpose: the app runs as one machine with one process, and the scheduler's worker thread
shares this limiter. Keyed by the owner of the key ("user:<id>", or "dev" for DEV_TWELVE_DATA_KEY), so
one person's refreshes never wait for another's. `clock` and `sleep` are injectable so tests run
instantly.
"""

import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta

from ...models import utcnow

PER_MINUTE = 8
# At most this many requests per key may sit waiting for the next minute; more are refused at once
# (the caller then serves the last known price). Stops one user tying up the server's worker threads.
MAX_WAITERS = 2
SAFETY_SECONDS = 0.25  # our clock and Twelve Data's may differ slightly


class MinuteLimiter:
    def __init__(
        self,
        per_minute: int = PER_MINUTE,
        clock: Callable[[], datetime] = utcnow,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.per_minute = per_minute
        self.clock = clock
        self.sleep = sleep
        self._windows: dict[str, tuple[datetime, int]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self._waiting: dict[str, int] = {}

    def _lock(self, key: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def _window(self, key: str, now: datetime) -> tuple[datetime, int]:
        minute = now.replace(second=0, microsecond=0)
        start, used = self._windows.get(key, (minute, 0))
        return (minute, 0) if start != minute else (start, used)

    def acquire(self, key: str, credits: int = 1, *, block: bool = True) -> float | None:
        """Reserve `credits` in this minute. Returns the seconds waited, or None if `block=False` and full."""
        credits = min(max(credits, 1), self.per_minute)
        if block:
            with self._guard:
                if self._waiting.get(key, 0) >= MAX_WAITERS:
                    return None
                self._waiting[key] = self._waiting.get(key, 0) + 1
        try:
            return self._acquire(key, credits, block)
        finally:
            if block:
                with self._guard:
                    self._waiting[key] -= 1

    def _acquire(self, key: str, credits: int, block: bool) -> float | None:
        waited = 0.0
        with self._lock(key):
            while True:
                now = self.clock()
                start, used = self._window(key, now)
                if used + credits <= self.per_minute:
                    self._windows[key] = (start, used + credits)
                    return waited
                if not block:
                    return None
                delay = (start + timedelta(minutes=1) - now).total_seconds() + SAFETY_SECONDS
                self.sleep(delay)
                waited += delay

    def note_left(self, key: str, left: int | None) -> None:
        """Twelve Data's `api-credits-left` header says the minute is spent: wait for the next one."""
        if left is not None and left <= 0:
            with self._guard:
                start, _ = self._window(key, self.clock())
                self._windows[key] = (start, self.per_minute)

    def used(self, key: str) -> int:
        return self._window(key, self.clock())[1]

    def reset(self) -> None:
        with self._guard:
            self._windows.clear()
