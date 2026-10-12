"""Tasks command registration for the CLI (per-task orchestration profiles)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import typer

from clawlet.cli.tasks_ui import (
    run_tasks_list_command,
    run_tasks_show_command,
    run_tasks_test_routing_command,
)


def register_tasks_commands(
    tasks_app: typer.Typer, *, get_workspace_path_fn: Callable[[], Path]
) -> None:
    @tasks_app.command("list")
    def tasks_list(
        workspace: Path = typer.Option(
            None, "--workspace", "-w", help="Workspace directory"
        ),
        json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    ):
        """List resolved execution profiles for every task kind."""
        run_tasks_list_command(
            workspace_path=workspace or get_workspace_path_fn(), as_json=json_output
        )

    @tasks_app.command("show")
    def tasks_show(
        kind: str = typer.Argument(..., help="Task kind (code, plan, research, ...)"),
        workspace: Path = typer.Option(
            None, "--workspace", "-w", help="Workspace directory"
        ),
        json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    ):
        """Show the resolved profile for one task kind."""
        run_tasks_show_command(
            workspace_path=workspace or get_workspace_path_fn(),
            kind=kind,
            as_json=json_output,
        )

    @tasks_app.command("test-routing")
    def tasks_test_routing(
        text: str = typer.Argument(..., help="Sample user message to classify"),
        json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    ):
        """Classify a sample message (rules pass, no network)."""
        run_tasks_test_routing_command(text=text, as_json=json_output)
