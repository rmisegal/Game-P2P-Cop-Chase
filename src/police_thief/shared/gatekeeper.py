# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""ApiGatekeeper: the single doorway for ALL external calls (glb-quality rule 3).

Every LLM / email / network call goes through execute(): rate limiting (config),
FIFO queuing on overflow, retry on transient provider errors, and call logging.
"""

import logging
from collections.abc import Callable
from typing import Any

from police_thief.exceptions import ProviderError
from police_thief.shared.config import ConfigManager
from police_thief.shared.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class ApiGatekeeper:
    """Centralized API call manager with rate limiting and queuing."""

    def __init__(self, config: ConfigManager, service: str):
        self._service = service
        limits = config.service_limits(service)
        self._max_retries = limits.get("max_retries", 1)
        self._retry_after = limits.get("retry_after_seconds", 0)
        self._limiter = RateLimiter(limits, config.rate_limits["queue"])
        self._calls_total = 0
        self._failures_total = 0

    def execute(self, api_call: Callable, *args: Any, **kwargs: Any) -> Any:
        """Run an external call under rate control with transient-error retry."""
        last_error: ProviderError | None = None
        for attempt in range(1, self._max_retries + 1):
            self._limiter.acquire()
            self._calls_total += 1
            try:
                result = api_call(*args, **kwargs)
                logger.debug("gatekeeper[%s] call ok (attempt %d)", self._service, attempt)
                return result
            except ProviderError as exc:
                self._failures_total += 1
                last_error = exc
                logger.warning(
                    "gatekeeper[%s] attempt %d/%d failed: %s",
                    self._service, attempt, self._max_retries, exc,
                )
        assert last_error is not None
        raise last_error

    def get_queue_status(self) -> dict:
        """Current queue depth and processing stats."""
        return {
            "service": self._service,
            "queue_depth": self._limiter.queue_depth,
            "calls_total": self._calls_total,
            "failures_total": self._failures_total,
        }
