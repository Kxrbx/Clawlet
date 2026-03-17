"""Replay command registration for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import typer

from clawlet.cli.replay_ui import run_replay_command


def register_replay_commands(app: typer.Typer, *, get_workspace_path_fn: Callable[[], Path]) -> None:
    @app.command("replay")
    def replay(
        run_id: str = typer.Argument(..., help="Run ID to inspect"),
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        limit: int = typer.Option(500, "--limit", min=1, max=5000, help="Max events to display"),
        show_signature: bool = typer.Option(False, "--signature", help="Show deterministic replay signature"),
        verify: bool = typer.Option(False, "--verify", help="Verify deterministic signature stability and event flow"),
        verify_resume: bool = typer.Option(
            False,
            "--verify-resume",
            help="Verify recovery resume-chain equivalence assertions for this run",
        ),
        reliability: bool = typer.Option(
            False,
            "--reliability",
            help="Print run-level reliability report from runtime events",
        ),
        reexecute: bool = typer.Option(
            False,
            "--reexecute",
            help="Re-execute recorded tool requests and compare deterministic outcomes",
        ),
        allow_write_reexecute: bool = typer.Option(
            False,
            "--allow-write-reexecute",
            help="Allow workspace-write tool reexecution (still blocks elevated actions)",
        ),
        fail_on_mismatch: bool = typer.Option(
            True,
            "--fail-on-mismatch",
            help="Exit non-zero when replay reexecution detects mismatches",
        ),
    ):
        """Inspect structured runtime events for a run."""
        run_replay_command(
            run_id=run_id,
            workspace_path=workspace or get_workspace_path_fn(),
            limit=limit,
            show_signature=show_signature,
            verify=verify,
            verify_resume=verify_resume,
            reliability=reliability,
            reexecute=reexecute,
            allow_write_reexecute=allow_write_reexecute,
            fail_on_mismatch=fail_on_mismatch,
        )
