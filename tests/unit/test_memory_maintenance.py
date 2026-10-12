"""Unit tests for automatic memory consolidation gating."""

from datetime import UTC, datetime, timedelta

from clawlet.agent.memory_maintenance import maybe_run_memory_maintenance


class FakeMemory:
    def __init__(self, promoted):
        self.promoted = promoted
        self.calls = 0

    async def curate_from_recent_daily_notes(self):
        self.calls += 1
        return list(self.promoted)


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_first_run_curates_and_persists_state(tmp_path):
    mem = FakeMemory(["k: v"])
    out = _run(maybe_run_memory_maintenance(mem, tmp_path))
    assert out == ["k: v"]
    assert mem.calls == 1
    assert (tmp_path / "maintenance-state.json").exists()


def test_second_run_within_interval_skips(tmp_path):
    mem = FakeMemory(["k: v"])
    _run(maybe_run_memory_maintenance(mem, tmp_path))
    out = _run(maybe_run_memory_maintenance(mem, tmp_path))
    assert out == []
    assert mem.calls == 1


def test_stale_state_runs_again(tmp_path):
    mem = FakeMemory([])
    now = datetime.now(UTC)
    _run(maybe_run_memory_maintenance(mem, tmp_path, now=now))
    out = _run(
        maybe_run_memory_maintenance(mem, tmp_path, now=now + timedelta(hours=25))
    )
    assert out == []
    assert mem.calls == 2


def test_failure_never_raises_and_does_not_mark_state(tmp_path):
    class Broken:
        async def curate_from_recent_daily_notes(self):
            raise RuntimeError("db gone")

    out = _run(maybe_run_memory_maintenance(Broken(), tmp_path))
    assert out == []
    assert not (tmp_path / "maintenance-state.json").exists()
