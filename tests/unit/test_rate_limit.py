from __future__ import annotations

import pytest

import clawlet.rate_limit as rate_limit_module
from clawlet.rate_limit import RateLimit, RateLimiter


class FakeClock:
    def __init__(self, now: float = 0.0):
        self.now = now

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.mark.unit
def test_rate_limiter_cleans_stale_entries_before_reaching_capacity(monkeypatch: pytest.MonkeyPatch):
    clock = FakeClock()
    monkeypatch.setattr(rate_limit_module.time, "time", clock.time)

    limiter = RateLimiter(
        default_limit=RateLimit(max_requests=5, window_seconds=5.0),
        tool_limit=RateLimit(max_requests=5, window_seconds=5.0),
        max_entries=2,
    )

    assert limiter.is_allowed("alpha") == (True, 0.0)
    clock.advance(1)
    assert limiter.is_allowed("beta") == (True, 0.0)

    clock.advance(10)
    assert limiter.is_allowed("gamma") == (True, 0.0)
    assert list(limiter._entries.keys()) == ["gamma"]


@pytest.mark.unit
def test_rate_limiter_evicts_least_recently_used_key(monkeypatch: pytest.MonkeyPatch):
    clock = FakeClock()
    monkeypatch.setattr(rate_limit_module.time, "time", clock.time)

    limiter = RateLimiter(
        default_limit=RateLimit(max_requests=5, window_seconds=60.0),
        tool_limit=RateLimit(max_requests=5, window_seconds=60.0),
        max_entries=2,
    )

    assert limiter.is_allowed("alpha") == (True, 0.0)
    clock.advance(1)
    assert limiter.is_allowed("beta") == (True, 0.0)
    clock.advance(1)
    assert limiter.is_allowed("alpha") == (True, 0.0)

    clock.advance(1)
    assert limiter.is_allowed("gamma") == (True, 0.0)
    assert list(limiter._entries.keys()) == ["alpha", "gamma"]


@pytest.mark.unit
def test_rate_limiter_periodic_cleanup_drops_expired_keys(monkeypatch: pytest.MonkeyPatch):
    clock = FakeClock()
    monkeypatch.setattr(rate_limit_module.time, "time", clock.time)

    limiter = RateLimiter(
        default_limit=RateLimit(max_requests=2, window_seconds=5.0),
        tool_limit=RateLimit(max_requests=2, window_seconds=5.0),
        max_entries=10,
    )
    limiter._cleanup_interval = 2.0

    assert limiter.is_allowed("alpha") == (True, 0.0)
    clock.advance(1)
    assert limiter.is_allowed("beta") == (True, 0.0)

    clock.advance(6)
    assert limiter.is_allowed("gamma") == (True, 0.0)
    assert list(limiter._entries.keys()) == ["gamma"]
