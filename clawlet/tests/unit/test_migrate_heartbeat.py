"""Unit tests for heartbeat migration helper."""

from __future__ import annotations

import yaml

from clawlet.cli.migration_ui import run_migrate_heartbeat


def test_migrate_heartbeat_every_and_active_hours(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    config = {
        "provider": {"primary": "openrouter", "openrouter": {"api_key": "k", "model": "m"}},
        "heartbeat": {
            "enabled": True,
            "every": "90m",
            "active_hours": {"start": 8, "end": 20},
        },
    }
    (workspace / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    run_migrate_heartbeat(workspace, write=True)
    migrated = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    hb = migrated["heartbeat"]
    assert hb["interval_minutes"] == 90
    assert hb["quiet_hours_start"] == 20
    assert hb["quiet_hours_end"] == 8
    assert "every" not in hb
    assert "active_hours" not in hb
