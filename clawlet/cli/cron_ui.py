"""Cron command helpers for the CLI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
from typing import Optional

import typer
import yaml
from rich.console import Console

from clawlet.config import SchedulerSettings
from clawlet.heartbeat.cron_scheduler import Scheduler, create_task_from_config

console = Console()


def _load_scheduler_settings(workspace_path: Path) -> SchedulerSettings:
    config_path = workspace_path / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    scheduler_raw = raw.get("scheduler")
    if scheduler_raw is None and "tasks" in raw:
        scheduler_raw = {"tasks": raw.get("tasks") or {}}
    scheduler_raw = scheduler_raw or {}
    return SchedulerSettings(**scheduler_raw)


def _load_raw_config(workspace_path: Path) -> tuple[Path, dict]:
    config_path = workspace_path / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return config_path, raw


def _save_raw_config(config_path: Path, raw: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False)


def _parse_csv(raw_value: str) -> list[str]:
    return [v.strip() for v in str(raw_value or "").split(",") if v.strip()]


def _parse_json_object(raw_value: str) -> dict:
    value = str(raw_value or "").strip()
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("params_json must be a JSON object")
    return parsed


def _normalize_wake_mode(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw == "next-heartbeat":
        return "next_heartbeat"
    return raw


def _build_scheduler(workspace_path: Path) -> Scheduler:
    settings = _load_scheduler_settings(workspace_path)
    scheduler = Scheduler(
        timezone=settings.timezone,
        max_concurrent=settings.max_concurrent,
        check_interval=float(settings.check_interval),
        state_file=settings.state_file,
        jobs_file=settings.jobs_file,
        runs_dir=settings.runs_dir,
    )

    for task_id, task_cfg in settings.tasks.items():
        scheduler.add_task(create_task_from_config(task_id, task_cfg))

    if settings.jobs_file:
        scheduler.load_jobs(settings.jobs_file, replace=False)
    if settings.state_file:
        scheduler.load_state(settings.state_file)
    return scheduler


def run_cron_list_command(workspace_path: Path, as_json: bool = False) -> None:
    """List configured and persisted cron jobs."""
    try:
        scheduler = _build_scheduler(workspace_path)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    status = scheduler.get_status()
    tasks = sorted(status.get("tasks", []), key=lambda t: (t.get("next_run") is None, t.get("next_run") or ""))

    if as_json:
        console.print_json(data={"total_tasks": len(tasks), "tasks": tasks})
        return

    if not tasks:
        console.print("[dim]No cron jobs found.[/dim]")
        return

    console.print(f"[bold]Cron Jobs[/bold] ({len(tasks)})")
    for task in tasks:
        next_run = task.get("next_run") or "-"
        enabled = "yes" if task.get("enabled") else "no"
        action = task.get("action") or "unknown"
        console.print(
            f"- {task.get('id')} | enabled={enabled} | action={action} | next_run={next_run}"
        )


def run_cron_run_now_command(workspace_path: Path, job_id: str, as_json: bool = False) -> None:
    """Run one cron job immediately."""
    try:
        scheduler = _build_scheduler(workspace_path)
        result = asyncio.run(scheduler.run_task(job_id))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    payload = {
        "job_id": job_id,
        "success": result.success,
        "status": result.status.value,
        "delivery_mode": result.metadata.get("delivery_mode"),
        "delivery_status": result.metadata.get("delivery_status"),
        "delivery_error": result.metadata.get("delivery_error"),
        "attempt": result.attempt,
        "started_at": result.started_at.isoformat() if result.started_at else None,
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "output": result.output,
        "error": result.error,
    }

    if as_json:
        console.print(json.dumps(payload, indent=2))
    else:
        if result.success:
            console.print(f"[green]Job '{job_id}' completed.[/green]")
            if result.output:
                console.print(f"[dim]{result.output}[/dim]")
        else:
            console.print(f"[red]Job '{job_id}' failed: {result.error}[/red]")
            raise typer.Exit(1)


def run_cron_runs_command(
    workspace_path: Path,
    job_id: Optional[str] = None,
    include_all: bool = False,
    limit: int = 50,
    offset: int = 0,
    status: str = "",
    delivery_status: str = "",
    as_json: bool = False,
) -> None:
    """Show persisted run history for one cron job."""
    try:
        scheduler = _build_scheduler(workspace_path)
        if include_all:
            entries = scheduler.list_all_runs(
                limit=max(1, int(limit)),
                offset=max(0, int(offset)),
                status=status.strip() or None,
                delivery_status=delivery_status.strip() or None,
            )
            run_scope = "all"
        else:
            if not job_id:
                raise ValueError("job_id is required unless --all is set")
            entries = scheduler.list_runs(
                job_id,
                limit=max(1, int(limit)),
                offset=max(0, int(offset)),
                status=status.strip() or None,
                delivery_status=delivery_status.strip() or None,
            )
            run_scope = job_id
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    payload = {"scope": run_scope, "count": len(entries), "runs": entries}
    if as_json:
        console.print(json.dumps(payload, indent=2))
        return

    if not entries:
        console.print(f"[dim]No runs found for '{run_scope}'.[/dim]")
        return

    console.print(f"[bold]Cron Runs[/bold] {run_scope} ({len(entries)})")
    for entry in entries:
        console.print(
            f"- {entry.get('run_id')} | status={entry.get('status')} | "
            f"delivery={entry.get('delivery_status')} | completed_at={entry.get('completed_at')}"
        )


def run_cron_add_command(
    workspace_path: Path,
    job_id: str,
    name: str,
    action: str,
    cron: str = "",
    interval: str = "",
    one_time: str = "",
    prompt: str = "",
    tool: str = "",
    webhook_url: str = "",
    timezone: str = "UTC",
    session_target: str = "main",
    agent_id: str = "",
    session_key: str = "",
    wake_mode: str = "now",
    delivery_mode: str = "none",
    delivery_channel: str = "",
    best_effort_delivery: bool = False,
    delete_after_run: bool = False,
    failure_alert_enabled: bool = False,
    failure_alert_after: int = 3,
    failure_alert_cooldown_seconds: int = 3600,
    failure_alert_mode: str = "announce",
    failure_alert_channel: str = "scheduler",
    failure_alert_to: str = "main",
    params_json: str = "",
    checks: str = "",
    skill: str = "",
    webhook_method: str = "POST",
    priority: str = "normal",
    depends_on: str = "",
    tags: str = "",
    max_attempts: int = 3,
    delay_seconds: float = 60.0,
    backoff_multiplier: float = 2.0,
    max_delay_seconds: float = 3600.0,
    enabled: bool = True,
) -> None:
    """Add a cron job into scheduler.tasks in config.yaml."""
    if not re.match(r"^[A-Za-z0-9_-]+$", job_id):
        console.print("[red]Error: job_id must match [A-Za-z0-9_-]+[/red]")
        raise typer.Exit(1)
    if action not in {"agent", "tool", "webhook", "health_check", "skill", "callback"}:
        console.print("[red]Error: invalid action[/red]")
        raise typer.Exit(1)
    chosen = [bool(cron.strip()), bool(interval.strip()), bool(one_time.strip())]
    if sum(chosen) != 1:
        console.print("[red]Error: choose exactly one schedule: cron, interval, or one_time[/red]")
        raise typer.Exit(1)
    if session_target not in {"main", "isolated"}:
        console.print("[red]Error: session_target must be main|isolated[/red]")
        raise typer.Exit(1)
    wake_mode = _normalize_wake_mode(wake_mode)
    if wake_mode not in {"now", "next_heartbeat"}:
        console.print("[red]Error: wake_mode must be now|next_heartbeat[/red]")
        raise typer.Exit(1)
    if delivery_mode not in {"announce", "none", "webhook"}:
        console.print("[red]Error: delivery_mode must be announce|none|webhook[/red]")
        raise typer.Exit(1)
    if failure_alert_mode not in {"announce", "webhook"}:
        console.print("[red]Error: failure_alert_mode must be announce|webhook[/red]")
        raise typer.Exit(1)
    if priority not in {"low", "normal", "high", "critical"}:
        console.print("[red]Error: priority must be low|normal|high|critical[/red]")
        raise typer.Exit(1)
    try:
        params_payload = _parse_json_object(params_json)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    try:
        config_path, raw = _load_raw_config(workspace_path)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    scheduler_raw = raw.get("scheduler")
    if scheduler_raw is None and "tasks" in raw:
        scheduler_raw = {"tasks": raw.get("tasks") or {}}
    scheduler_raw = scheduler_raw or {}
    tasks = scheduler_raw.get("tasks") or {}
    if job_id in tasks:
        console.print(f"[red]Error: job '{job_id}' already exists[/red]")
        raise typer.Exit(1)

    task = {
        "name": name,
        "action": action,
        "enabled": bool(enabled),
        "agent_id": agent_id.strip() or None,
        "session_key": session_key.strip() or None,
        "timezone": timezone,
        "session_target": session_target,
        "wake_mode": wake_mode,
        "delivery_mode": delivery_mode,
        "webhook_method": webhook_method,
        "best_effort_delivery": bool(best_effort_delivery),
        "delete_after_run": bool(delete_after_run),
        "priority": priority,
        "depends_on": _parse_csv(depends_on),
        "tags": _parse_csv(tags),
        "failure_alert": {
            "enabled": bool(failure_alert_enabled),
            "after": int(failure_alert_after),
            "cooldown_seconds": int(failure_alert_cooldown_seconds),
            "mode": failure_alert_mode,
            "channel": failure_alert_channel,
            "to": failure_alert_to,
        },
        "retry": {
            "max_attempts": int(max_attempts),
            "delay_seconds": float(delay_seconds),
            "backoff_multiplier": float(backoff_multiplier),
            "max_delay_seconds": float(max_delay_seconds),
        },
        "params": params_payload,
    }
    if cron.strip():
        task["cron"] = cron.strip()
    if interval.strip():
        task["interval"] = interval.strip()
    if one_time.strip():
        task["one_time"] = one_time.strip()
    if prompt.strip():
        task["prompt"] = prompt.strip()
    if tool.strip():
        task["tool"] = tool.strip()
    if webhook_url.strip():
        task["webhook_url"] = webhook_url.strip()
    if checks.strip():
        task["checks"] = _parse_csv(checks)
    if skill.strip():
        task["skill"] = skill.strip()
    if delivery_channel.strip():
        task["delivery_channel"] = delivery_channel.strip()

    tasks[job_id] = task
    scheduler_raw["tasks"] = tasks
    raw["scheduler"] = scheduler_raw
    _save_raw_config(config_path, raw)
    console.print(f"[green]Added cron job '{job_id}'.[/green]")


def run_cron_set_enabled_command(
    workspace_path: Path,
    job_id: str,
    enabled: bool,
) -> None:
    """Pause/resume a cron job by toggling scheduler.tasks.<id>.enabled."""
    try:
        config_path, raw = _load_raw_config(workspace_path)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    scheduler_raw = raw.get("scheduler")
    if scheduler_raw is None and "tasks" in raw:
        scheduler_raw = {"tasks": raw.get("tasks") or {}}
    scheduler_raw = scheduler_raw or {}
    tasks = scheduler_raw.get("tasks") or {}
    if job_id not in tasks:
        console.print(f"[red]Error: job '{job_id}' not found in scheduler.tasks[/red]")
        raise typer.Exit(1)
    tasks[job_id]["enabled"] = bool(enabled)
    scheduler_raw["tasks"] = tasks
    raw["scheduler"] = scheduler_raw
    _save_raw_config(config_path, raw)
    state = "resumed" if enabled else "paused"
    console.print(f"[green]Job '{job_id}' {state}.[/green]")


def run_cron_remove_command(workspace_path: Path, job_id: str) -> None:
    """Remove a cron job from scheduler.tasks in config.yaml."""
    try:
        config_path, raw = _load_raw_config(workspace_path)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    scheduler_raw = raw.get("scheduler")
    if scheduler_raw is None and "tasks" in raw:
        scheduler_raw = {"tasks": raw.get("tasks") or {}}
    scheduler_raw = scheduler_raw or {}
    tasks = scheduler_raw.get("tasks") or {}
    if job_id not in tasks:
        console.print(f"[red]Error: job '{job_id}' not found in scheduler.tasks[/red]")
        raise typer.Exit(1)

    del tasks[job_id]
    scheduler_raw["tasks"] = tasks
    raw["scheduler"] = scheduler_raw
    _save_raw_config(config_path, raw)
    console.print(f"[green]Removed cron job '{job_id}'.[/green]")


def run_cron_edit_command(
    workspace_path: Path,
    job_id: str,
    name: Optional[str] = None,
    action: Optional[str] = None,
    cron: Optional[str] = None,
    interval: Optional[str] = None,
    one_time: Optional[str] = None,
    prompt: Optional[str] = None,
    tool: Optional[str] = None,
    webhook_url: Optional[str] = None,
    timezone: Optional[str] = None,
    session_target: Optional[str] = None,
    agent_id: Optional[str] = None,
    session_key: Optional[str] = None,
    wake_mode: Optional[str] = None,
    delivery_mode: Optional[str] = None,
    delivery_channel: Optional[str] = None,
    best_effort_delivery: Optional[bool] = None,
    delete_after_run: Optional[bool] = None,
    failure_alert_enabled: Optional[bool] = None,
    failure_alert_after: Optional[int] = None,
    failure_alert_cooldown_seconds: Optional[int] = None,
    failure_alert_mode: Optional[str] = None,
    failure_alert_channel: Optional[str] = None,
    failure_alert_to: Optional[str] = None,
    priority: Optional[str] = None,
    params_json: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> None:
    """Edit selected fields for one cron job in scheduler.tasks."""
    try:
        config_path, raw = _load_raw_config(workspace_path)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    scheduler_raw = raw.get("scheduler")
    if scheduler_raw is None and "tasks" in raw:
        scheduler_raw = {"tasks": raw.get("tasks") or {}}
    scheduler_raw = scheduler_raw or {}
    tasks = scheduler_raw.get("tasks") or {}
    if job_id not in tasks:
        console.print(f"[red]Error: job '{job_id}' not found in scheduler.tasks[/red]")
        raise typer.Exit(1)

    task = dict(tasks[job_id] or {})

    if action is not None:
        if action not in {"agent", "tool", "webhook", "health_check", "skill", "callback"}:
            console.print("[red]Error: invalid action[/red]")
            raise typer.Exit(1)
        task["action"] = action
    if name is not None:
        task["name"] = name
    if timezone is not None:
        task["timezone"] = timezone
    if session_target is not None:
        if session_target not in {"main", "isolated"}:
            console.print("[red]Error: session_target must be main|isolated[/red]")
            raise typer.Exit(1)
        task["session_target"] = session_target
    if agent_id is not None:
        task["agent_id"] = agent_id.strip() or None
    if session_key is not None:
        task["session_key"] = session_key.strip() or None
    if wake_mode is not None:
        wake_mode = _normalize_wake_mode(wake_mode)
        if wake_mode not in {"now", "next_heartbeat"}:
            console.print("[red]Error: wake_mode must be now|next_heartbeat[/red]")
            raise typer.Exit(1)
        task["wake_mode"] = wake_mode
    if delivery_mode is not None:
        if delivery_mode not in {"announce", "none", "webhook"}:
            console.print("[red]Error: delivery_mode must be announce|none|webhook[/red]")
            raise typer.Exit(1)
        task["delivery_mode"] = delivery_mode
    if delivery_channel is not None:
        task["delivery_channel"] = delivery_channel
    if best_effort_delivery is not None:
        task["best_effort_delivery"] = bool(best_effort_delivery)
    if delete_after_run is not None:
        task["delete_after_run"] = bool(delete_after_run)
    if priority is not None:
        if priority not in {"low", "normal", "high", "critical"}:
            console.print("[red]Error: priority must be low|normal|high|critical[/red]")
            raise typer.Exit(1)
        task["priority"] = priority
    if enabled is not None:
        task["enabled"] = bool(enabled)

    schedule_updates = {
        "cron": cron,
        "interval": interval,
        "one_time": one_time,
    }
    provided = [k for k, v in schedule_updates.items() if v is not None and str(v).strip() != ""]
    if len(provided) > 1:
        console.print("[red]Error: provide at most one of --cron/--interval/--one-time[/red]")
        raise typer.Exit(1)
    if len(provided) == 1:
        for key in ("cron", "interval", "one_time"):
            task.pop(key, None)
        key = provided[0]
        task[key] = str(schedule_updates[key]).strip()

    if prompt is not None:
        task["prompt"] = prompt
    if tool is not None:
        task["tool"] = tool
    if webhook_url is not None:
        task["webhook_url"] = webhook_url
    if params_json is not None:
        try:
            task["params"] = _parse_json_object(params_json)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    if any(
        v is not None
        for v in (
            failure_alert_enabled,
            failure_alert_after,
            failure_alert_cooldown_seconds,
            failure_alert_mode,
            failure_alert_channel,
            failure_alert_to,
        )
    ):
        alert = dict(task.get("failure_alert") or {})
        if failure_alert_enabled is not None:
            alert["enabled"] = bool(failure_alert_enabled)
        if failure_alert_after is not None:
            alert["after"] = int(failure_alert_after)
        if failure_alert_cooldown_seconds is not None:
            alert["cooldown_seconds"] = int(failure_alert_cooldown_seconds)
        if failure_alert_mode is not None:
            if failure_alert_mode not in {"announce", "webhook"}:
                console.print("[red]Error: failure_alert_mode must be announce|webhook[/red]")
                raise typer.Exit(1)
            alert["mode"] = failure_alert_mode
        if failure_alert_channel is not None:
            alert["channel"] = failure_alert_channel
        if failure_alert_to is not None:
            alert["to"] = failure_alert_to
        task["failure_alert"] = alert

    tasks[job_id] = task
    scheduler_raw["tasks"] = tasks
    raw["scheduler"] = scheduler_raw
    _save_raw_config(config_path, raw)
    console.print(f"[green]Updated cron job '{job_id}'.[/green]")
