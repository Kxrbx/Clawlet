"""Heartbeat operator helpers for the CLI."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer
import yaml

from clawlet.cli.common_ui import console, print_footer, print_section
from clawlet.config import load_config


def _config_path(workspace_path: Path) -> Path:
    return workspace_path / "config.yaml"


def _heartbeat_state_path(workspace_path: Path) -> Path:
    return workspace_path / ".runtime" / "heartbeat_last.json"


def _heartbeat_memory_state_path(workspace_path: Path) -> Path:
    return workspace_path / "memory" / "heartbeat-state.json"


def _agent_pid_path(workspace_path: Path) -> Path:
    return workspace_path / ".runtime" / "agent.pid"


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_agent_pid(workspace_path: Path) -> int | None:
    path = _agent_pid_path(workspace_path)
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _parse_timestamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_raw_config(workspace_path: Path) -> dict:
    path = _config_path(workspace_path)
    if not path.exists():
        raise typer.Exit(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise typer.Exit(f"Invalid config structure in {path}")
    return raw


def _write_raw_config(workspace_path: Path, raw: dict) -> None:
    path = _config_path(workspace_path)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def run_heartbeat_status_command(workspace_path: Path) -> None:
    cfg = load_config(workspace_path)
    hb = cfg.heartbeat
    print_section("Heartbeat", f"Checking {workspace_path}")
    console.print(f"|  Enabled: {'yes' if hb.enabled else 'no'}")
    console.print(f"|  Interval: {hb.interval_minutes} min")
    console.print(f"|  Target: {hb.target}")
    console.print(f"|  Ack limit: {hb.ack_max_chars}")
    quiet = "disabled" if hb.quiet_hours_start == hb.quiet_hours_end else f"{hb.quiet_hours_start}:00-{hb.quiet_hours_end}:00 UTC"
    console.print(f"|  Quiet hours: {quiet}")
    pid = _read_agent_pid(workspace_path)
    runtime_running = bool(pid and _pid_is_running(pid))
    runtime_status = f"running (pid {pid})" if runtime_running else "not running"
    console.print(f"|  Runtime: {runtime_status}")
    state_path = _heartbeat_state_path(workspace_path)
    last_tick_at = None
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        console.print(f"|  Last tick: {state.get('timestamp', 'unknown')}")
        console.print(f"|  Last status: {state.get('status', 'unknown')}")
        console.print(f"|  Last reason: {state.get('reason', 'unknown')}")
        last_tick_at = _parse_timestamp(state.get("timestamp", ""))
    else:
        console.print("|  Last tick: none recorded")
    if hb.enabled:
        stale_after = timedelta(minutes=max(int(hb.interval_minutes or 30) * 2, 5))
        now = datetime.now(timezone.utc)
        if not runtime_running:
            console.print("|  [yellow]! Heartbeat cannot trigger while the agent runtime is stopped[/yellow]")
        elif last_tick_at is None:
            console.print("|  [yellow]! No heartbeat tick has been recorded yet[/yellow]")
        elif now - last_tick_at > stale_after:
            console.print("|  [yellow]! Heartbeat looks stale compared to configured interval[/yellow]")
    memory_state_path = _heartbeat_memory_state_path(workspace_path)
    if memory_state_path.exists():
        memory_state = json.loads(memory_state_path.read_text(encoding="utf-8"))
        console.print(f"|  Last result: {memory_state.get('last_result_at', 'unknown') or 'unknown'}")
        console.print(f"|  Last action: {memory_state.get('last_action_at', 'none') or 'none'}")
        console.print(f"|  Last outreach: {memory_state.get('last_outreach_at', 'none') or 'none'}")
        due_checks = ", ".join(memory_state.get("last_due_checks") or []) or "none"
        console.print(f"|  Due checks: {due_checks}")
    print_footer()


def run_heartbeat_last_command(workspace_path: Path, as_json: bool = False) -> None:
    state_path = _heartbeat_state_path(workspace_path)
    if not state_path.exists():
        raise typer.Exit("No recorded heartbeat state yet.")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    if as_json:
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print_section("Heartbeat Last", str(state_path))
    console.print(f"|  Timestamp: {payload.get('timestamp', 'unknown')}")
    console.print(f"|  Status: {payload.get('status', 'unknown')}")
    console.print(f"|  Reason: {payload.get('reason', 'unknown')}")
    route = payload.get("route") or {}
    if route:
        console.print(f"|  Route: {route.get('channel', '?')}/{route.get('chat_id', '?')}")
    prompt = str(payload.get("prompt", "") or "").strip()
    if prompt:
        console.print("|")
        console.print("|  Prompt:")
        console.print(f"|    {prompt}")
    memory_state_path = _heartbeat_memory_state_path(workspace_path)
    if memory_state_path.exists():
        memory_payload = json.loads(memory_state_path.read_text(encoding="utf-8"))
        console.print("|")
        console.print(f"|  State file: {memory_state_path}")
        console.print(f"|  Last result: {memory_payload.get('last_result_at', 'unknown') or 'unknown'}")
        console.print(f"|  Last result text: {str(memory_payload.get('last_result', '') or '')[:180]}")
        console.print(f"|  Last outreach: {memory_payload.get('last_outreach_at', 'none') or 'none'}")
        recent_actions = memory_payload.get("recent_actions") or []
        if recent_actions:
            console.print(f"|  Recent action: {recent_actions[0]}")
    print_footer()


def run_heartbeat_set_enabled_command(workspace_path: Path, enabled: bool) -> None:
    raw = _load_raw_config(workspace_path)
    heartbeat = raw.setdefault("heartbeat", {})
    if not isinstance(heartbeat, dict):
        raise typer.Exit("config heartbeat section is not a mapping")
    heartbeat["enabled"] = bool(enabled)
    _write_raw_config(workspace_path, raw)
    print_section("Heartbeat", f"{'Enabled' if enabled else 'Disabled'} in config")
    console.print(f"|  Config: {_config_path(workspace_path)}")
    print_footer()
