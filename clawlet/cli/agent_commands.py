"""Agent command registration for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import typer

from clawlet.cli.runtime_ui import (
    run_agent_command,
    run_agent_restart_command,
    run_agent_stop_command,
    run_chat_command,
    run_logs_command,
)


def register_agent_commands(
    app: typer.Typer,
    agent_app: typer.Typer,
    *,
    get_workspace_path_fn: Callable[[], Path],
    print_sakura_banner_fn: Callable[[], None],
    sakura_light: str,
) -> None:
    @agent_app.callback(invoke_without_command=True)
    def agent(
        ctx: typer.Context,
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
        channel: str = typer.Option("telegram", "--channel", "-c", help="Channel to use"),
        daemon: bool = typer.Option(False, "--daemon", help="Run agent in background"),
        log_file: Optional[Path] = typer.Option(None, "--log-file", help="File to write logs to"),
        log_level: str = typer.Option("INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"),
    ):
        """* Start the Clawlet agent."""
        if ctx.invoked_subcommand is not None:
            return
        run_agent_command(
            workspace=workspace,
            model=model,
            channel=channel,
            log_file=log_file,
            log_level=log_level,
            daemon=daemon,
            get_workspace_path_fn=get_workspace_path_fn,
            print_sakura_banner_fn=print_sakura_banner_fn,
            sakura_light=sakura_light,
        )

    @agent_app.command("stop")
    def agent_stop(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Stop the running Clawlet agent."""
        run_agent_stop_command(workspace=workspace, get_workspace_path_fn=get_workspace_path_fn)

    @agent_app.command("restart")
    def agent_restart(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
        channel: str = typer.Option("telegram", "--channel", "-c", help="Channel to use"),
        foreground: bool = typer.Option(False, "--foreground", help="Restart in foreground instead of background"),
        log_file: Optional[Path] = typer.Option(None, "--log-file", help="File to write logs to"),
        log_level: str = typer.Option("INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"),
    ):
        """Restart the Clawlet agent."""
        run_agent_restart_command(
            workspace=workspace,
            model=model,
            channel=channel,
            log_file=log_file,
            log_level=log_level,
            daemon=not foreground,
            get_workspace_path_fn=get_workspace_path_fn,
            print_sakura_banner_fn=print_sakura_banner_fn,
            sakura_light=sakura_light,
        )

    @app.command()
    def chat(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    ):
        """* Start a local interactive chat session in the terminal."""
        run_chat_command(workspace=workspace, model=model, get_workspace_path_fn=get_workspace_path_fn)

    @app.command()
    def logs(
        log_file: Path = typer.Option(get_workspace_path_fn() / "clawlet.log", "--log-file", "-f", help="Log file to read"),
        lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to display"),
        follow: bool = typer.Option(False, "--follow", help="Follow log output (tail -f)"),
    ):
        """* Tail the Clawlet agent logs."""
        run_logs_command(log_file=log_file, lines=lines, follow=follow)
