"""Cron command registration for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import typer

from clawlet.cli.cron_ui import (
    run_cron_add_command,
    run_cron_edit_command,
    run_cron_list_command,
    run_cron_remove_command,
    run_cron_run_now_command,
    run_cron_runs_command,
    run_cron_set_enabled_command,
)


def register_cron_commands(cron_app: typer.Typer, *, get_workspace_path_fn: Callable[[], Path]) -> None:
    @cron_app.command("list")
    def cron_list(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    ):
        """List cron jobs from scheduler config + persisted jobs file."""
        run_cron_list_command(workspace_path=workspace or get_workspace_path_fn(), as_json=json_output)

    @cron_app.command("run-now")
    def cron_run_now(
        job_id: str = typer.Argument(..., help="Job ID"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    ):
        """Run one cron job immediately."""
        run_cron_run_now_command(
            workspace_path=workspace or get_workspace_path_fn(),
            job_id=job_id,
            as_json=json_output,
        )

    @cron_app.command("runs")
    def cron_runs(
        job_id: Optional[str] = typer.Argument(None, help="Job ID (optional with --all)"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        include_all: bool = typer.Option(False, "--all", help="Show runs across all jobs"),
        limit: int = typer.Option(50, "--limit", min=1, max=5000, help="Max run entries"),
        offset: int = typer.Option(0, "--offset", min=0, max=100000, help="Offset into run entries"),
        status: str = typer.Option("", "--status", help="Filter by run status (completed|failed|pending)"),
        delivery_status: str = typer.Option(
            "",
            "--delivery-status",
            help="Filter by delivery status (delivered|not-delivered|unknown|not-requested)",
        ),
        json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    ):
        """Show persisted run history for one cron job."""
        run_cron_runs_command(
            workspace_path=workspace or get_workspace_path_fn(),
            job_id=job_id,
            include_all=include_all,
            limit=limit,
            offset=offset,
            status=status,
            delivery_status=delivery_status,
            as_json=json_output,
        )

    @cron_app.command("add")
    def cron_add(
        job_id: str = typer.Argument(..., help="Job ID"),
        name: str = typer.Option(..., "--name", help="Display name"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        action: str = typer.Option("agent", "--action", help="agent|tool|webhook|health_check|skill|callback"),
        cron: str = typer.Option("", "--cron", help="Cron expression"),
        interval: str = typer.Option("", "--interval", help="Interval (e.g. 30m)"),
        one_time: str = typer.Option("", "--one-time", help="ISO datetime"),
        prompt: str = typer.Option("", "--prompt", help="Agent prompt"),
        tool: str = typer.Option("", "--tool", help="Tool name"),
        webhook_url: str = typer.Option("", "--webhook-url", help="Webhook URL"),
        timezone: str = typer.Option("UTC", "--timezone", help="Timezone"),
        session_target: str = typer.Option("main", "--session-target", help="main|isolated"),
        agent_id: str = typer.Option("", "--agent-id", help="Optional agent identifier"),
        session_key: str = typer.Option("", "--session-key", help="Optional session key for routing"),
        wake_mode: str = typer.Option("now", "--wake-mode", help="now|next_heartbeat"),
        delivery_mode: str = typer.Option("none", "--delivery-mode", help="announce|none|webhook"),
        delivery_channel: str = typer.Option("", "--delivery-channel", help="Announce channel or webhook URL"),
        best_effort_delivery: bool = typer.Option(False, "--best-effort-delivery", help="Do not fail job when delivery fails"),
        delete_after_run: bool = typer.Option(False, "--delete-after-run", help="Delete job after successful run"),
        failure_alert_enabled: bool = typer.Option(False, "--failure-alert-enabled", help="Enable repeated-failure alerts"),
        failure_alert_after: int = typer.Option(3, "--failure-alert-after", min=1, max=100),
        failure_alert_cooldown_seconds: int = typer.Option(3600, "--failure-alert-cooldown-seconds", min=0, max=604800),
        failure_alert_mode: str = typer.Option("announce", "--failure-alert-mode", help="announce|webhook"),
        failure_alert_channel: str = typer.Option("scheduler", "--failure-alert-channel", help="Alert channel"),
        failure_alert_to: str = typer.Option("main", "--failure-alert-to", help="Alert destination"),
        params_json: str = typer.Option("", "--params-json", help="JSON object for task params"),
        checks: str = typer.Option("", "--checks", help="Comma-separated health checks"),
        skill: str = typer.Option("", "--skill", help="Skill name for action=skill"),
        webhook_method: str = typer.Option("POST", "--webhook-method", help="Webhook method"),
        priority: str = typer.Option("normal", "--priority", help="low|normal|high|critical"),
        depends_on: str = typer.Option("", "--depends-on", help="Comma-separated dependency job IDs"),
        tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
        max_attempts: int = typer.Option(3, "--max-attempts", min=1, max=10),
        delay_seconds: float = typer.Option(60.0, "--delay-seconds", min=0.0, max=86400.0),
        backoff_multiplier: float = typer.Option(2.0, "--backoff-multiplier", min=1.0, max=10.0),
        max_delay_seconds: float = typer.Option(3600.0, "--max-delay-seconds", min=0.0, max=86400.0),
        enabled: bool = typer.Option(True, "--enabled", help="Create job enabled/disabled"),
    ):
        """Add one cron job to scheduler config."""
        run_cron_add_command(
            workspace_path=workspace or get_workspace_path_fn(),
            job_id=job_id,
            name=name,
            action=action,
            cron=cron,
            interval=interval,
            one_time=one_time,
            prompt=prompt,
            tool=tool,
            webhook_url=webhook_url,
            timezone=timezone,
            session_target=session_target,
            agent_id=agent_id,
            session_key=session_key,
            wake_mode=wake_mode,
            delivery_mode=delivery_mode,
            delivery_channel=delivery_channel,
            best_effort_delivery=best_effort_delivery,
            delete_after_run=delete_after_run,
            failure_alert_enabled=failure_alert_enabled,
            failure_alert_after=failure_alert_after,
            failure_alert_cooldown_seconds=failure_alert_cooldown_seconds,
            failure_alert_mode=failure_alert_mode,
            failure_alert_channel=failure_alert_channel,
            failure_alert_to=failure_alert_to,
            params_json=params_json,
            checks=checks,
            skill=skill,
            webhook_method=webhook_method,
            priority=priority,
            depends_on=depends_on,
            tags=tags,
            max_attempts=max_attempts,
            delay_seconds=delay_seconds,
            backoff_multiplier=backoff_multiplier,
            max_delay_seconds=max_delay_seconds,
            enabled=enabled,
        )

    @cron_app.command("pause")
    def cron_pause(
        job_id: str = typer.Argument(..., help="Job ID"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Pause one cron job."""
        run_cron_set_enabled_command(
            workspace_path=workspace or get_workspace_path_fn(),
            job_id=job_id,
            enabled=False,
        )

    @cron_app.command("resume")
    def cron_resume(
        job_id: str = typer.Argument(..., help="Job ID"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Resume one cron job."""
        run_cron_set_enabled_command(
            workspace_path=workspace or get_workspace_path_fn(),
            job_id=job_id,
            enabled=True,
        )

    @cron_app.command("remove")
    def cron_remove(
        job_id: str = typer.Argument(..., help="Job ID"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Remove one cron job."""
        run_cron_remove_command(workspace_path=workspace or get_workspace_path_fn(), job_id=job_id)

    @cron_app.command("edit")
    def cron_edit(
        job_id: str = typer.Argument(..., help="Job ID"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        name: Optional[str] = typer.Option(None, "--name"),
        action: Optional[str] = typer.Option(None, "--action"),
        cron: Optional[str] = typer.Option(None, "--cron"),
        interval: Optional[str] = typer.Option(None, "--interval"),
        one_time: Optional[str] = typer.Option(None, "--one-time"),
        prompt: Optional[str] = typer.Option(None, "--prompt"),
        tool: Optional[str] = typer.Option(None, "--tool"),
        webhook_url: Optional[str] = typer.Option(None, "--webhook-url"),
        timezone: Optional[str] = typer.Option(None, "--timezone"),
        session_target: Optional[str] = typer.Option(None, "--session-target"),
        agent_id: Optional[str] = typer.Option(None, "--agent-id"),
        session_key: Optional[str] = typer.Option(None, "--session-key"),
        wake_mode: Optional[str] = typer.Option(None, "--wake-mode"),
        delivery_mode: Optional[str] = typer.Option(None, "--delivery-mode"),
        delivery_channel: Optional[str] = typer.Option(None, "--delivery-channel"),
        best_effort_delivery: Optional[bool] = typer.Option(None, "--best-effort-delivery", help="Set to true/false"),
        delete_after_run: Optional[bool] = typer.Option(None, "--delete-after-run", help="Set to true/false"),
        failure_alert_enabled: Optional[bool] = typer.Option(None, "--failure-alert-enabled", help="Set to true/false"),
        failure_alert_after: Optional[int] = typer.Option(None, "--failure-alert-after", min=1, max=100),
        failure_alert_cooldown_seconds: Optional[int] = typer.Option(None, "--failure-alert-cooldown-seconds", min=0, max=604800),
        failure_alert_mode: Optional[str] = typer.Option(None, "--failure-alert-mode"),
        failure_alert_channel: Optional[str] = typer.Option(None, "--failure-alert-channel"),
        failure_alert_to: Optional[str] = typer.Option(None, "--failure-alert-to"),
        priority: Optional[str] = typer.Option(None, "--priority"),
        params_json: Optional[str] = typer.Option(None, "--params-json"),
        enabled: Optional[bool] = typer.Option(None, "--enabled", help="Set to true/false"),
    ):
        """Edit one cron job."""
        run_cron_edit_command(
            workspace_path=workspace or get_workspace_path_fn(),
            job_id=job_id,
            name=name,
            action=action,
            cron=cron,
            interval=interval,
            one_time=one_time,
            prompt=prompt,
            tool=tool,
            webhook_url=webhook_url,
            timezone=timezone,
            session_target=session_target,
            agent_id=agent_id,
            session_key=session_key,
            wake_mode=wake_mode,
            delivery_mode=delivery_mode,
            delivery_channel=delivery_channel,
            best_effort_delivery=best_effort_delivery,
            delete_after_run=delete_after_run,
            failure_alert_enabled=failure_alert_enabled,
            failure_alert_after=failure_alert_after,
            failure_alert_cooldown_seconds=failure_alert_cooldown_seconds,
            failure_alert_mode=failure_alert_mode,
            failure_alert_channel=failure_alert_channel,
            failure_alert_to=failure_alert_to,
            priority=priority,
            params_json=params_json,
            enabled=enabled,
        )
