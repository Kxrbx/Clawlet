"""Deterministic replay checks for CI quality gates."""

from __future__ import annotations

from pathlib import Path

from clawlet.runtime.events import RuntimeEvent, RuntimeEventStore


def run_determinism_smokecheck(workdir: Path) -> bool:
    """Return True if replay signatures remain stable for identical event streams."""
    path = workdir / "determinism-events.jsonl"
    if path.exists():
        path.unlink()

    store = RuntimeEventStore(path)
    store.append(RuntimeEvent(event_type="RunStarted", run_id="det", session_id="s", payload={"x": 1}))
    store.append(RuntimeEvent(event_type="ToolCompleted", run_id="det", session_id="s", payload={"tool": "list_dir"}))
    sig1 = store.get_run_signature("det")
    sig2 = store.get_run_signature("det")
    return bool(sig1) and sig1 == sig2


def run_determinism_trials(workdir: Path, trials: int = 10) -> float:
    """Return determinism replay pass-rate percentage across repeated trials."""
    trials = max(1, int(trials))
    passed = 0
    path = workdir / "determinism-events-trials.jsonl"
    if path.exists():
        path.unlink()

    store = RuntimeEventStore(path)
    for i in range(trials):
        run_id = f"det-{i}"
        store.append(
            RuntimeEvent(
                event_type="RunStarted",
                run_id=run_id,
                session_id="s",
                payload={"x": i},
            )
        )
        store.append(
            RuntimeEvent(
                event_type="ToolStarted",
                run_id=run_id,
                session_id="s",
                payload={"tool": "list_dir"},
            )
        )
        store.append(
            RuntimeEvent(
                event_type="ToolCompleted",
                run_id=run_id,
                session_id="s",
                payload={"tool": "list_dir", "ok": True},
            )
        )
        store.append(
            RuntimeEvent(
                event_type="RunCompleted",
                run_id=run_id,
                session_id="s",
                payload={"is_error": False},
            )
        )
        sig1 = store.get_run_signature(run_id)
        sig2 = store.get_run_signature(run_id)
        if bool(sig1) and sig1 == sig2:
            passed += 1

    return (passed / trials) * 100.0
