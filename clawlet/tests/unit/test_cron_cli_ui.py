"""Unit tests for cron CLI commands."""

from __future__ import annotations

from pathlib import Path

import yaml
from clawlet.cli.cron_ui import (
    run_cron_add_command,
    run_cron_edit_command,
    run_cron_list_command,
    run_cron_remove_command,
    run_cron_run_now_command,
    run_cron_runs_command,
    run_cron_set_enabled_command,
)


def _write_workspace_config(workspace: Path) -> None:
    config = {
        "scheduler": {
            "enabled": True,
            "timezone": "UTC",
            "jobs_file": str(workspace / "cron" / "jobs.json"),
            "runs_dir": str(workspace / "cron" / "runs"),
            "state_file": str(workspace / "cron" / "state.json"),
            "tasks": {
                "job_one": {
                    "name": "Job one",
                    "action": "agent",
                    "interval": "30m",
                    "prompt": "Ping status",
                    "session_target": "main",
                    "wake_mode": "now",
                }
            },
        }
    }
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")


def test_cron_list_json(tmp_path, capsys):
    workspace = tmp_path / "ws"
    _write_workspace_config(workspace)
    run_cron_list_command(workspace, as_json=True)
    out = capsys.readouterr().out
    assert "job_one" in out


def test_cron_run_now_json(tmp_path, capsys):
    workspace = tmp_path / "ws"
    _write_workspace_config(workspace)
    run_cron_run_now_command(workspace, "job_one", as_json=True)
    out = capsys.readouterr().out
    assert '"job_id": "job_one"' in out
    assert '"success": true' in out
    run_log = workspace / "cron" / "runs" / "job_one.jsonl"
    assert run_log.exists()


def test_cron_runs_json_with_filter(tmp_path, capsys):
    workspace = tmp_path / "ws"
    _write_workspace_config(workspace)

    run_cron_run_now_command(workspace, "job_one", as_json=True)
    _ = capsys.readouterr()

    run_cron_runs_command(
        workspace,
        "job_one",
        limit=10,
        delivery_status="not-requested",
        as_json=True,
    )
    out = capsys.readouterr().out
    assert '"scope": "job_one"' in out
    assert '"delivery_status": "not-requested"' in out


def test_cron_add_pause_resume_updates_config(tmp_path):
    workspace = tmp_path / "ws"
    _write_workspace_config(workspace)

    run_cron_add_command(
        workspace_path=workspace,
        job_id="job_two",
        name="Job two",
        action="agent",
        interval="45m",
        prompt="Do a proactive check",
        agent_id="agent-1",
        session_key="session-1",
        params_json='{"k":"v"}',
        delete_after_run=True,
        best_effort_delivery=True,
        failure_alert_enabled=True,
        failure_alert_after=5,
        failure_alert_cooldown_seconds=120,
        failure_alert_mode="announce",
        failure_alert_channel="scheduler",
        failure_alert_to="main",
        depends_on="job_one",
        tags="ops,nightly",
        enabled=True,
    )

    raw = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    assert "job_two" in raw["scheduler"]["tasks"]
    assert raw["scheduler"]["tasks"]["job_two"]["enabled"] is True
    assert raw["scheduler"]["tasks"]["job_two"]["params"]["k"] == "v"
    assert raw["scheduler"]["tasks"]["job_two"]["agent_id"] == "agent-1"
    assert raw["scheduler"]["tasks"]["job_two"]["session_key"] == "session-1"
    assert raw["scheduler"]["tasks"]["job_two"]["delete_after_run"] is True
    assert raw["scheduler"]["tasks"]["job_two"]["best_effort_delivery"] is True
    assert raw["scheduler"]["tasks"]["job_two"]["failure_alert"]["enabled"] is True
    assert raw["scheduler"]["tasks"]["job_two"]["failure_alert"]["after"] == 5
    assert raw["scheduler"]["tasks"]["job_two"]["depends_on"] == ["job_one"]
    assert raw["scheduler"]["tasks"]["job_two"]["tags"] == ["ops", "nightly"]

    run_cron_set_enabled_command(workspace, "job_two", enabled=False)
    raw = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    assert raw["scheduler"]["tasks"]["job_two"]["enabled"] is False

    run_cron_set_enabled_command(workspace, "job_two", enabled=True)
    raw = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    assert raw["scheduler"]["tasks"]["job_two"]["enabled"] is True


def test_cron_runs_all_scope(tmp_path, capsys):
    workspace = tmp_path / "ws"
    _write_workspace_config(workspace)
    run_cron_run_now_command(workspace, "job_one", as_json=True)
    _ = capsys.readouterr()

    run_cron_runs_command(
        workspace_path=workspace,
        include_all=True,
        limit=10,
        as_json=True,
    )
    out = capsys.readouterr().out
    assert '"scope": "all"' in out
    assert '"job_id": "job_one"' in out


def test_cron_edit_and_remove(tmp_path):
    workspace = tmp_path / "ws"
    _write_workspace_config(workspace)

    run_cron_edit_command(
        workspace_path=workspace,
        job_id="job_one",
        name="Renamed Job",
        interval="15m",
        wake_mode="next_heartbeat",
        delivery_mode="announce",
        params_json='{"x":1}',
    )
    raw = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    job = raw["scheduler"]["tasks"]["job_one"]
    assert job["name"] == "Renamed Job"
    assert job["interval"] == "15m"
    assert job["wake_mode"] == "next_heartbeat"
    assert job["delivery_mode"] == "announce"
    assert job["params"]["x"] == 1

    run_cron_remove_command(workspace_path=workspace, job_id="job_one")
    raw = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    assert "job_one" not in raw["scheduler"]["tasks"]


def test_cron_edit_accepts_upstream_wake_mode_alias(tmp_path):
    workspace = tmp_path / "ws"
    _write_workspace_config(workspace)

    run_cron_edit_command(
        workspace_path=workspace,
        job_id="job_one",
        wake_mode="next-heartbeat",
    )
    raw = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    assert raw["scheduler"]["tasks"]["job_one"]["wake_mode"] == "next_heartbeat"


def test_cron_edit_updates_advanced_delivery_and_alert_fields(tmp_path):
    workspace = tmp_path / "ws"
    _write_workspace_config(workspace)

    run_cron_edit_command(
        workspace_path=workspace,
        job_id="job_one",
        agent_id="agent-x",
        session_key="session-x",
        best_effort_delivery=True,
        delete_after_run=True,
        failure_alert_enabled=True,
        failure_alert_after=4,
        failure_alert_mode="webhook",
        failure_alert_channel="scheduler",
        failure_alert_to="https://example.com/alert",
    )
    raw = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    job = raw["scheduler"]["tasks"]["job_one"]
    assert job["agent_id"] == "agent-x"
    assert job["session_key"] == "session-x"
    assert job["best_effort_delivery"] is True
    assert job["delete_after_run"] is True
    assert job["failure_alert"]["enabled"] is True
    assert job["failure_alert"]["after"] == 4
    assert job["failure_alert"]["mode"] == "webhook"
