"""Heartbeat operator helpers for the CLI."""

from __future__ import annotations

import json
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
    state_path = _heartbeat_state_path(workspace_path)
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        console.print(f"|  Last tick: {state.get('timestamp', 'unknown')}")
        console.print(f"|  Last status: {state.get('status', 'unknown')}")
        console.print(f"|  Last reason: {state.get('reason', 'unknown')}")
    else:
        console.print("|  Last tick: none recorded")
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
