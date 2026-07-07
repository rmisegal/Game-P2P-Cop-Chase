# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Token-bucket rate limiter with FIFO wait queue (glb-quality rules 3, 5).

All limits come from config (rate_limits.json); nothing hardcoded. An injectable
clock keeps tests deterministic and instant.
"""

import threading
import time as _time
from collections import deque

from police_thief.exceptions import RateLimitError

WINDOW_SECONDS = 60.0  # a "requests per minute" window is a minute by definition


class _RealClock:
    time = staticmethod(_time.time)
    sleep = staticmethod(_time.sleep)


class RateLimiter:
    """Sliding-window limiter: blocks (queues) when the window is full."""

    def __init__(self, limits: dict, queue_cfg: dict, clock=None):
        self._rpm = limits["requests_per_minute"]
        self._max_depth = queue_cfg["max_depth"]
        self._drain_interval = queue_cfg["drain_interval_seconds"]
        self._timeout = queue_cfg["timeout_seconds"]
        self._clock = clock or _RealClock()
        self._grants: deque[float] = deque()  # timestamps of recent grants
        self._waiting = 0
        self._lock = threading.Lock()

    @property
    def queue_depth(self) -> int:
        """How many callers are currently queued waiting for a slot."""
        return self._waiting

    def _prune(self, now: float) -> None:
        while self._grants and now - self._grants[0] >= WINDOW_SECONDS:
            self._grants.popleft()

    def _try_grant(self) -> bool:
        with self._lock:
            now = self._clock.time()
            self._prune(now)
            if len(self._grants) < self._rpm:
                self._grants.append(now)
                return True
            return False

    def acquire(self) -> None:
        """Block until a slot frees; raise RateLimitError on overflow/timeout."""
        if self._try_grant():
            return
        with self._lock:
            if self._waiting >= self._max_depth:
                raise RateLimitError(
                    f"Rate-limit queue full (max_depth={self._max_depth})"
                )
            self._waiting += 1
        try:
            deadline = self._clock.time() + self._timeout
            while self._clock.time() < deadline:
                self._clock.sleep(self._drain_interval)
                if self._try_grant():
                    return
            raise RateLimitError(f"Timed out after {self._timeout}s waiting for a rate slot")
        finally:
            with self._lock:
                self._waiting -= 1
