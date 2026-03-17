"""Recovery command registration for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import typer

from clawlet.cli.recovery_ui import (
    run_recovery_cleanup,
    run_recovery_list,
    run_recovery_resume_payload,
    run_recovery_show,
)


def register_recovery_commands(recovery_app: typer.Typer, *, get_workspace_path_fn: Callable[[], Path]) -> None:
    @recovery_app.command("list")
    def recovery_list(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        limit: int = typer.Option(20, "--limit", min=1, max=500, help="Maximum checkpoints"),
    ):
        """List interrupted runs with available checkpoints."""
        run_recovery_list(workspace_path=workspace or get_workspace_path_fn(), limit=limit)

    @recovery_app.command("show")
    def recovery_show(
        run_id: str = typer.Argument(..., help="Run ID"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Show checkpoint details for one run id."""
        run_recovery_show(workspace_path=workspace or get_workspace_path_fn(), run_id=run_id)

    @recovery_app.command("resume-payload")
    def recovery_resume_payload(
        run_id: str = typer.Argument(..., help="Run ID"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Render recovery inbound payload for manual resume orchestration."""
        run_recovery_resume_payload(workspace_path=workspace or get_workspace_path_fn(), run_id=run_id)

    @recovery_app.command("cleanup")
    def recovery_cleanup(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        retention_days: int = typer.Option(
            0,
            "--retention-days",
            min=0,
            help="Override runtime.replay.retention_days (0 uses config value)",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="Preview cleanup without modifying files",
        ),
    ):
        """Prune replay events/checkpoints older than retention policy."""
        run_recovery_cleanup(
            workspace_path=workspace or get_workspace_path_fn(),
            retention_days=retention_days,
            dry_run=dry_run,
        )
