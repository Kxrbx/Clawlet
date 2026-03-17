"""Session command registration for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import typer

from clawlet.cli.sessions_ui import run_sessions_command


def register_session_commands(app: typer.Typer, *, get_workspace_path_fn: Callable[[], Path]) -> None:
    @app.command()
    def sessions(
        workspace: Optional[Path] = typer.Option(None, "--workspace", help="Workspace directory"),
        export: Optional[Path] = typer.Option(None, "--export", help="Export sessions to JSON file"),
        limit: int = typer.Option(10, "--limit", help="Number of recent sessions to list"),
    ):
        """* List and export conversation sessions from storage."""
        run_sessions_command(workspace_path=workspace or get_workspace_path_fn(), export=export, limit=limit)
