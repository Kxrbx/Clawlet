"""Plugin command registration for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import typer

from clawlet.cli.plugin_ui import (
    run_plugin_conformance,
    run_plugin_init,
    run_plugin_matrix,
    run_plugin_publish,
    run_plugin_test,
)


def register_plugin_commands(plugin_app: typer.Typer, *, get_workspace_path_fn: Callable[[], Path]) -> None:
    @plugin_app.command("init")
    def plugin_init(
        name: str = typer.Argument(..., help="Plugin name"),
        directory: Path = typer.Option(Path("."), "--dir", help="Base directory for plugin"),
    ):
        """Initialize a plugin SDK v2 skeleton."""
        run_plugin_init(name=name, directory=directory)

    @plugin_app.command("test")
    def plugin_test(
        path: Path = typer.Option(..., "--path", help="Plugin directory containing plugin.py"),
        strict: bool = typer.Option(
            True,
            "--strict",
            help="Fail on conformance errors",
        ),
    ):
        """Load and validate a plugin package."""
        run_plugin_test(path=path, strict=strict)

    @plugin_app.command("conformance")
    def plugin_conformance(
        path: Path = typer.Option(..., "--path", help="Plugin directory containing plugin.py"),
    ):
        """Run Plugin SDK v2 conformance checks."""
        run_plugin_conformance(path=path)

    @plugin_app.command("matrix")
    def plugin_matrix(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
        fail_on_errors: bool = typer.Option(
            False,
            "--fail-on-errors",
            help="Exit non-zero when plugin conformance errors are detected",
        ),
    ):
        """Scan plugin directories and summarize conformance compatibility."""
        run_plugin_matrix(
            workspace_path=workspace or get_workspace_path_fn(),
            report_path=report_path,
            fail_on_errors=fail_on_errors,
        )

    @plugin_app.command("publish")
    def plugin_publish(
        path: Path = typer.Option(..., "--path", help="Plugin directory to package"),
        out_dir: Path = typer.Option(Path("dist"), "--out-dir", help="Output directory"),
    ):
        """Package a plugin directory as a distributable tarball."""
        run_plugin_publish(path=path, out_dir=out_dir)
