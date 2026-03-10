"""Tests for quick health automation signals."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import yaml

from clawlet.health import quick_health_check


def test_quick_health_includes_automation_check(monkeypatch, tmp_path):
    home = tmp_path / "home"
    workspace = home / ".clawlet"
    runs_dir = workspace / "cron" / "runs"
    queue_file = workspace / "tasks" / "QUEUE.md"
    runs_dir.mkdir(parents=True, exist_ok=True)
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text("- [ ] task one\n", encoding="utf-8")

    cfg = {
        "provider": {"primary": "openrouter", "openrouter": {"api_key": "k", "model": "m"}},
        "heartbeat": {"proactive_queue_path": "tasks/QUEUE.md"},
        "scheduler": {"runs_dir": str(runs_dir), "tasks": {"a": {"name": "A", "action": "agent", "interval": "30m"}}},
    }
    (workspace / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with open(runs_dir / "a.jsonl", "w", encoding="utf-8") as f:
        for i in range(3):
            f.write(json.dumps({"run_id": f"r{i}", "status": "failed"}))
            f.write("\n")

    monkeypatch.setattr(Path, "home", lambda: home)
    out = asyncio.run(quick_health_check())
    names = {c["name"] for c in out["checks"]}
    assert "automation" in names
    assert out["status"] in {"healthy", "degraded"}
