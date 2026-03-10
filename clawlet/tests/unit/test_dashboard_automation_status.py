"""Unit tests for dashboard automation status helper."""

from __future__ import annotations

import json

import yaml

from clawlet.dashboard.api import _read_automation_status


def test_read_automation_status_counts_runs_and_tasks(tmp_path):
    workspace = tmp_path / "ws"
    runs_dir = workspace / "cron" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "heartbeat": {
            "enabled": True,
            "interval_minutes": 30,
            "target": "main",
            "quiet_hours_start": 1,
            "quiet_hours_end": 6,
        },
        "scheduler": {
            "enabled": True,
            "timezone": "UTC",
            "runs_dir": str(runs_dir),
            "tasks": {
                "job_a": {"name": "A", "action": "agent", "interval": "30m", "enabled": True},
                "job_b": {"name": "B", "action": "agent", "interval": "60m", "enabled": False},
            },
        },
    }
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    run_file = runs_dir / "job_a.jsonl"
    entries = [
        {"run_id": "r1", "status": "completed", "completed_at": "2026-03-05T10:00:00+00:00"},
        {"run_id": "r2", "status": "failed", "completed_at": "2026-03-05T11:00:00+00:00"},
    ]
    with open(run_file, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry))
            f.write("\n")

    status = _read_automation_status(workspace)
    assert status["heartbeat"]["enabled"] is True
    assert status["scheduler"]["enabled"] is True
    assert status["scheduler"]["total_tasks"] == 2
    assert status["scheduler"]["enabled_tasks"] == 1
    assert status["scheduler"]["total_runs"] == 2
    assert status["scheduler"]["failed_runs"] == 1
