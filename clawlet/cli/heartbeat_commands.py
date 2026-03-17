"""Heartbeat command registration for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import typer

from clawlet.cli.heartbeat_ui import (
    run_heartbeat_last_command,
    run_heartbeat_set_enabled_command,
    run_heartbeat_status_command,
)


def register_heartbeat_commands(heartbeat_app: typer.Typer, *, get_workspace_path_fn: Callable[[], Path]) -> None:
    @heartbeat_app.command("status")
    def heartbeat_status(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Show heartbeat configuration and last recorded tick."""
        run_heartbeat_status_command(workspace or get_workspace_path_fn())

    @heartbeat_app.command("last")
    def heartbeat_last(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    ):
        """Show the last recorded heartbeat tick."""
        run_heartbeat_last_command(workspace or get_workspace_path_fn(), as_json=json_output)

    @heartbeat_app.command("enable")
    def heartbeat_enable(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Enable heartbeat execution in config."""
        run_heartbeat_set_enabled_command(workspace or get_workspace_path_fn(), enabled=True)

    @heartbeat_app.command("disable")
    def heartbeat_disable(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Disable heartbeat execution in config."""
        run_heartbeat_set_enabled_command(workspace or get_workspace_path_fn(), enabled=False)
