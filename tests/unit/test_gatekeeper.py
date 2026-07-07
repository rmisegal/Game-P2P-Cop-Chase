"""Tests for ApiGatekeeper: routing, retry, queue status, logging."""

import pytest

from police_thief.exceptions import ProviderCliError, RateLimitError
from police_thief.shared.gatekeeper import ApiGatekeeper


@pytest.fixture
def gatekeeper(config):
    return ApiGatekeeper(config, service="claude")


class TestApiGatekeeper:
    def test_executes_call_and_returns_result(self, gatekeeper):
        assert gatekeeper.execute(lambda x: x * 2, 21) == 42

    def test_retries_transient_failure(self, gatekeeper):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise ProviderCliError("transient")
            return "ok"

        assert gatekeeper.execute(flaky) == "ok"
        assert calls["n"] == 2

    def test_raises_after_max_retries(self, gatekeeper):
        def always_fails():
            raise ProviderCliError("boom")

        with pytest.raises(ProviderCliError):
            gatekeeper.execute(always_fails)

    def test_non_provider_errors_not_retried(self, gatekeeper):
        calls = {"n": 0}

        def bug():
            calls["n"] += 1
            raise ValueError("logic bug")

        with pytest.raises(ValueError):
            gatekeeper.execute(bug)
        assert calls["n"] == 1

    def test_queue_status_shape(self, gatekeeper):
        status = gatekeeper.get_queue_status()
        assert status["service"] == "claude"
        assert status["queue_depth"] == 0
        assert status["calls_total"] == 0
        gatekeeper.execute(lambda: None)
        assert gatekeeper.get_queue_status()["calls_total"] == 1

    def test_rate_limit_error_propagates(self, config):
        gk = ApiGatekeeper(config, service="claude")
        gk._limiter.acquire = lambda: (_ for _ in ()).throw(RateLimitError("full"))
        with pytest.raises(RateLimitError):
            gk.execute(lambda: 1)
