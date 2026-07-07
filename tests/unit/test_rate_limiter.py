"""Tests for the token-bucket rate limiter with FIFO overflow queue."""

import pytest

from police_thief.exceptions import RateLimitError
from police_thief.shared.rate_limiter import RateLimiter


def make_limiter(rpm=2, max_depth=3, timeout=0.2, clock=None):
    limits = {"requests_per_minute": rpm, "max_retries": 1, "retry_after_seconds": 0}
    queue_cfg = {"max_depth": max_depth, "drain_interval_seconds": 0.001, "timeout_seconds": timeout}
    return RateLimiter(limits, queue_cfg, clock=clock)


class FakeClock:
    """Deterministic clock so tests never sleep for real."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class TestRateLimiter:
    def test_allows_within_rate(self):
        clock = FakeClock()
        limiter = make_limiter(rpm=2, clock=clock)
        limiter.acquire()
        limiter.acquire()  # both fit in the window

    def test_queues_and_drains_on_window_reset(self):
        clock = FakeClock()
        limiter = make_limiter(rpm=1, timeout=120, clock=clock)
        limiter.acquire()
        limiter.acquire()  # over the limit: waits (fake-sleeps) until window frees
        assert clock.now >= 60.0

    def test_timeout_raises(self):
        clock = FakeClock()
        limiter = make_limiter(rpm=1, timeout=5, clock=clock)
        limiter.acquire()
        with pytest.raises(RateLimitError):
            limiter.acquire()  # can't drain within 5s timeout

    def test_queue_overflow_raises(self):
        clock = FakeClock()
        limiter = make_limiter(rpm=1, max_depth=0, timeout=5, clock=clock)
        limiter.acquire()
        with pytest.raises(RateLimitError):
            limiter.acquire()  # queue depth 0: immediate overflow

    def test_queue_depth_reporting(self):
        clock = FakeClock()
        limiter = make_limiter(rpm=10, clock=clock)
        assert limiter.queue_depth == 0
        limiter.acquire()
        assert limiter.queue_depth == 0  # nothing pending after grant
