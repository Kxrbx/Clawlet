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
