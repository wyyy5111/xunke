"""Small in-process abuse controls for public authentication endpoints.

The nginx deployment also applies an IP request rate, but the application must
remain protected when developers run Uvicorn directly.  These limits are keyed
only by the ASGI peer address; untrusted ``X-Forwarded-For`` values are never
used by the application.
"""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class SlidingWindowLimiter:
    """Thread-safe bounded sliding-window counter.

    It is deliberately dependency-free and suitable for the single-process
    competition/demo deployment. A distributed production deployment should
    move this state to Redis or an equivalent shared limiter.
    """

    def __init__(self, max_events: int, window_seconds: int, max_keys: int = 10_000):
        self.max_events = max(1, int(max_events))
        self.window_seconds = max(1, int(window_seconds))
        self.max_keys = max(100, int(max_keys))
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, events: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()

    def retry_after(self, key: str) -> int:
        now = monotonic()
        with self._lock:
            events = self._events.get(key)
            if not events:
                return 0
            self._prune(events, now)
            if not events:
                self._events.pop(key, None)
                return 0
            if len(events) < self.max_events:
                return 0
            return max(1, int(self.window_seconds - (now - events[0])) + 1)

    def hit(self, key: str) -> int:
        now = monotonic()
        with self._lock:
            if len(self._events) >= self.max_keys and key not in self._events:
                # Bound memory without weakening an existing key's protection.
                stale = next(iter(self._events), None)
                if stale is not None:
                    self._events.pop(stale, None)
            events = self._events[key]
            self._prune(events, now)
            events.append(now)
            if len(events) < self.max_events:
                return 0
            return max(1, int(self.window_seconds - (now - events[0])) + 1)

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

