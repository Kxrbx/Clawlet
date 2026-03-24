"""
Clawlet CLI commands.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from clawlet import __version__
from clawlet.cli.benchmark_utils import (
    corpus_comparison_payload,
    load_benchmarks_settings,
    print_corpus_comparison_summary,
    print_regressions,
)
from clawlet.cli.agent_commands import register_agent_commands
from clawlet.cli.benchmark_commands import register_benchmark_commands
from clawlet.cli.config_ui import run_config_command
from clawlet.cli.cron_commands import register_cron_commands
from clawlet.cli.dashboard_ui import run_dashboard_command
from clawlet.cli.heartbeat_commands import register_heartbeat_commands
from clawlet.cli.common_ui import _filter_breach_lines, print_command, print_footer, print_section
from clawlet.cli.migration_ui import run_migrate_config, run_migrate_heartbeat, run_migration_matrix
from clawlet.cli.models_ui import run_models_command
from clawlet.cli.plugin_commands import register_plugin_commands
from clawlet.cli.recovery_commands import register_recovery_commands
from clawlet.cli.replay_commands import register_replay_commands
from clawlet.cli.release_ui import run_release_readiness_command
from clawlet.cli.runtime_paths import get_default_workspace_path
from clawlet.cli.session_commands import register_session_commands
from clawlet.cli.templates import (
    get_config_template,
    get_heartbeat_template,
    get_memory_template,
    get_queue_template,
    get_soul_template,
    get_user_template,
)
from clawlet.cli.workspace_ui import run_doctor, run_health, run_status, run_validate

# Sakura color scheme
SAKURA_PINK = "#FF69B4"
SAKURA_LIGHT = "#FFB7C5"

app = typer.Typer(
    name="clawlet",
    help="* Clawlet - A lightweight AI agent framework",
    no_args_is_help=False,
)
benchmark_app = typer.Typer(help="Performance and regression benchmark commands")
plugin_app = typer.Typer(help="Plugin SDK v2 commands")
recovery_app = typer.Typer(help="Interrupted-run recovery commands")
cron_app = typer.Typer(help="Cron scheduler commands")
heartbeat_app = typer.Typer(help="Heartbeat commands")
agent_app = typer.Typer(help="Agent runtime commands", invoke_without_command=True, no_args_is_help=False)
app.add_typer(agent_app, name="agent")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(plugin_app, name="plugin")
app.add_typer(recovery_app, name="recovery")
app.add_typer(cron_app, name="cron")
app.add_typer(heartbeat_app, name="heartbeat")

console = Console()


from clawlet.config import get_default_config_path


def get_workspace_path() -> Path:
    """Get the default workspace path."""
    return get_default_workspace_path()


def print_sakura_banner():
    """Print ASCII art banner."""
    console.print(
        """
[bold cyan]
  _____ _          __          ___      ______ _______
 / ____| |        /\\ \\        / / |    |  ____|__   __|
| |    | |       /  \\ \\  /\\  / /| |    | |__     | |
| |    | |      / /\\ \\ \\/  \\/ / | |    |  __|    | |
| |____| |____ / ____ \\  /\\  /  | |____| |____   | |
 \\_____|______/_/    \\_\\/  \\/   |______|______|  |_|
[/bold cyan]
[bold magenta]* A lightweight AI agent framework with identity awareness[/bold magenta]
"""
    )

MAIN_MENU_COMMANDS = [
    ("onboard", "Interactive setup wizard (recommended)", "clawlet onboard"),
    ("init", "Quick workspace initialization", "clawlet init"),
    ("agent", "Start your AI agent", "clawlet agent"),
    ("chat", "Start a local terminal chat session", "clawlet chat"),
    ("tui", "Launch the full-screen terminal ops console", "clawlet tui"),
    ("logs", "Tail the Clawlet agent logs", "clawlet logs"),
    ("models", "Manage AI models", "clawlet models"),
    ("dashboard", "Launch web dashboard", "clawlet dashboard"),
    ("heartbeat", "Inspect heartbeat state and controls", "clawlet heartbeat status"),
    ("cron", "List and run scheduled jobs", "clawlet cron list"),
    ("benchmark", "Run performance regression suite", "clawlet benchmark run"),
    ("replay", "Inspect deterministic run events", "clawlet replay <run_id>"),
    ("sessions", "List and export stored sessions", "clawlet sessions"),
    ("status", "Check workspace status", "clawlet status"),
    ("health", "Run health checks", "clawlet health"),
    ("doctor", "Inspect runtime failures and stale state", "clawlet doctor"),
    ("validate", "Validate configuration", "clawlet validate"),
    ("config", "View/edit configuration", "clawlet config"),
]


def _registered_top_level_command_names() -> set[str]:
    names: set[str] = set()
    for command in app.registered_commands:
        callback = getattr(command, "callback", None)
        callback_name = getattr(callback, "__name__", "")
        explicit_name = str(getattr(command, "name", "") or "").strip()
        if explicit_name:
            names.add(explicit_name)
        elif callback_name:
            names.add(callback_name.replace("_", "-"))
    for group in getattr(app, "registered_groups", []):
        group_name = str(getattr(group, "name", "") or "").strip()
        if group_name:
            names.add(group_name)
    return names


def print_main_menu():
    """Print the main menu when clawlet is invoked without args."""
    print_sakura_banner()
    
    print_section("Commands", "What would you like to do?")
    available = _registered_top_level_command_names()
    for name, description, example in MAIN_MENU_COMMANDS:
        if name in available:
            print_command(name, description, example)
    
    print_footer()
    
    console.print()
    console.print(f"[dim]* Run 'clawlet <command> --help' for more info[/dim]")
    console.print(f"[dim]* Version: {__version__} | https://github.com/Kxrbx/Clawlet[/dim]")
    console.print()


register_agent_commands(
    app,
    agent_app,
    get_workspace_path_fn=get_workspace_path,
    print_sakura_banner_fn=print_sakura_banner,
    sakura_light=SAKURA_LIGHT,
)
register_heartbeat_commands(heartbeat_app, get_workspace_path_fn=get_workspace_path)
register_replay_commands(app, get_workspace_path_fn=get_workspace_path)
register_recovery_commands(recovery_app, get_workspace_path_fn=get_workspace_path)
register_plugin_commands(plugin_app, get_workspace_path_fn=get_workspace_path)
register_session_commands(app, get_workspace_path_fn=get_workspace_path)
register_cron_commands(cron_app, get_workspace_path_fn=get_workspace_path)
register_benchmark_commands(
    benchmark_app,
    get_workspace_path_fn=get_workspace_path,
    load_benchmarks_settings_fn=load_benchmarks_settings,
    print_corpus_comparison_summary_fn=print_corpus_comparison_summary,
    corpus_comparison_payload_fn=corpus_comparison_payload,
    print_regressions_fn=print_regressions,
    filter_breach_lines_fn=_filter_breach_lines,
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
):
    """* Clawlet - A lightweight AI agent framework with identity awareness."""
    if version:
        console.print(f"[magenta]* clawlet version {__version__}[/magenta]")
        raise typer.Exit()
    
    # If no command provided, show custom sakura menu
    if ctx.invoked_subcommand is None:
        print_main_menu()
        raise typer.Exit()


@app.command()
def init(
    workspace: Path = typer.Option(
        None, "--workspace", "-w", help="Workspace directory"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
):
    """* Quick workspace initialization.
    
    For guided setup, use 'clawlet onboard' instead.
    """
    workspace_path = workspace or get_workspace_path()
    
    # If workspace doesn't exist, suggest onboard
    if not workspace_path.exists():
        print_section("Quick Setup", "Creating workspace with defaults")
        console.print("|  [dim]Tip: For guided setup, use: clawlet onboard[/dim]")
    else:
        print_section("Quick Setup", f"Updating {workspace_path}")
    
    console.print("|")
    
    # Create workspace directory
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "memory").mkdir(exist_ok=True)
    (workspace_path / "tasks").mkdir(exist_ok=True)
    
    # Create identity files
    identity_files = {
        "SOUL.md": get_soul_template(),
        "USER.md": get_user_template(),
        "MEMORY.md": get_memory_template(),
        "HEARTBEAT.md": get_heartbeat_template(),
    }
    
    for filename, content in identity_files.items():
        file_path = workspace_path / filename
        if file_path.exists() and not force:
            console.print(f"|  [yellow]->[/yellow] {filename} [dim](exists, skipped)[/dim]")
        else:
            file_path.write_text(content)
            console.print(f"|  [green]OK[/green] {filename}")

    queue_path = workspace_path / "tasks" / "QUEUE.md"
    if queue_path.exists() and not force:
        console.print(f"|  [yellow]->[/yellow] tasks/QUEUE.md [dim](exists, skipped)[/dim]")
    else:
        queue_path.write_text(get_queue_template(), encoding="utf-8")
        console.print(f"|  [green]OK[/green] tasks/QUEUE.md")
    
    # Create config file
    config_path = workspace_path / "config.yaml"
    if not config_path.exists() or force:
        config_path.write_text(get_config_template(), encoding="utf-8")
        try:
            os.chmod(config_path, 0o600)
        except OSError:
            pass
        console.print(f"|  [green]OK[/green] config.yaml")
    
    print_footer()
    
    console.print()
    console.print(f"[bold green]OK Workspace ready![/bold green]")
    console.print(f"  Location: [{SAKURA_PINK}]{workspace_path}[/{SAKURA_PINK}]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Edit [{SAKURA_PINK}]config.yaml[/{SAKURA_PINK}] to configure a provider")
    console.print(f"  2. Run [{SAKURA_PINK}]clawlet validate[/{SAKURA_PINK}] to check the workspace")
    console.print(f"  3. Run [{SAKURA_PINK}]clawlet agent[/{SAKURA_PINK}] to start")
    console.print()


@app.command()
def onboard():
    """* Interactive onboarding with guided setup (recommended for first-time users)."""
    try:
        from clawlet.cli.onboard import run_onboarding
        asyncio.run(run_onboarding())
    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled.[/yellow]")
    except ImportError as e:
        console.print(f"[red]Error loading onboarding: {e}[/red]")
        console.print("[yellow]Try running 'pip install questionary' first.[/yellow]")
        raise typer.Exit(1)


@app.command()
def dashboard(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run on"),
    frontend_port: int = typer.Option(5173, "--frontend-port", "-f", help="Frontend dev server port"),
    open_browser: bool = typer.Option(True, "--open-browser", help="Open browser automatically"),
    no_frontend: bool = typer.Option(False, "--no-frontend", help="Don't start frontend dev server"),
):
    """Start the Clawlet dashboard.

    Starts both the API server and the React frontend dev server.
    """
    run_dashboard_command(
        workspace=workspace,
        port=port,
        frontend_port=frontend_port,
        open_browser=open_browser,
        no_frontend=no_frontend,
        get_workspace_path_fn=get_workspace_path,
    )


@app.command()
def status():
    """* Show Clawlet workspace status."""
    run_status(get_workspace_path(), __version__)




@app.command()
def tui(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
):
    """* Launch the full-screen terminal UI for Clawlet."""
    workspace_path = workspace or get_workspace_path()
    if not workspace_path.exists():
        console.print("[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]")
        raise typer.Exit(1)
    try:
        from clawlet.tui import run_tui_app
    except ImportError as e:
        console.print(f"[red]Error: TUI dependencies are not installed: {e}[/red]")
        console.print("Install with: [magenta]pip install -e .[/magenta]")
        raise typer.Exit(1)
    run_tui_app(workspace=workspace_path, model=model)


@app.command()
def health():
    """* Run health checks on all components."""
    run_health()


@app.command()
def doctor(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """* Inspect recent runtime failures, stale heartbeat state, and prompt artifacts."""
    run_doctor(workspace or get_workspace_path())


@app.command()
def validate(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    migration: bool = typer.Option(False, "--migration", help="Run legacy migration compatibility analysis"),
):
    """* Validate configuration file."""
    run_validate(workspace or get_workspace_path(), migration=migration)


@app.command()
def config(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    key: Optional[str] = typer.Argument(None, help="Config key to show"),
):
    """* View or manage configuration."""
    run_config_command(workspace or get_workspace_path(), key=key)


@app.command("migrate-config")
def migrate_config(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    write: bool = typer.Option(False, "--write", help="Apply autofix changes to config.yaml"),
    backup: bool = typer.Option(True, "--backup", help="Create .bak backup when writing"),
):
    """Analyze and optionally autofix legacy config keys."""
    run_migrate_config(workspace or get_workspace_path(), write=write, backup=backup)


@app.command("migration-matrix")
def migration_matrix(
    root: Path = typer.Option(Path("."), "--root", help="Root directory containing workspaces"),
    pattern: str = typer.Option("config.yaml", "--pattern", help="Config filename/pattern to scan"),
    max_workspaces: int = typer.Option(200, "--max-workspaces", min=1, max=5000, help="Maximum configs to scan"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON output report path"),
    fail_on_errors: bool = typer.Option(
        False,
        "--fail-on-errors",
        help="Exit non-zero if any scanned workspace has migration blocking errors",
    ),
):
    """Scan many workspaces and report migration compatibility readiness."""
    run_migration_matrix(
        root=root,
        pattern=pattern,
        max_workspaces=max_workspaces,
        report_path=report_path,
        fail_on_errors=fail_on_errors,
    )


@app.command("migrate-heartbeat")
def migrate_heartbeat(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    write: bool = typer.Option(False, "--write", help="Apply heartbeat migration changes"),
):
    """Normalize legacy heartbeat keys to canonical schema."""
    run_migrate_heartbeat(workspace or get_workspace_path(), write=write)


@app.command("release-readiness")
def release_readiness(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Primary workspace directory"),
    local_iterations: int = typer.Option(25, "--local-iterations", min=1, max=500),
    corpus_iterations: int = typer.Option(10, "--corpus-iterations", min=1, max=200),
    baseline_report: Optional[Path] = typer.Option(None, "--baseline-report"),
    target_improvement_pct: float = typer.Option(35.0, "--target-improvement-pct", min=0.0, max=100.0),
    require_comparison: bool = typer.Option(False, "--require-comparison"),
    migration_root: Optional[Path] = typer.Option(None, "--migration-root", help="Root path for migration matrix scan"),
    migration_pattern: str = typer.Option("config.yaml", "--migration-pattern"),
    migration_max_workspaces: int = typer.Option(200, "--migration-max-workspaces", min=1, max=5000),
    check_remote_health: bool = typer.Option(False, "--check-remote-health"),
    breach_category: Optional[str] = typer.Option(
        None,
        "--breach-category",
        help="Filter displayed gate breaches by category: local|corpus|lane|context|coding|rust|comparison|other",
    ),
    max_breaches: int = typer.Option(
        8,
        "--max-breaches",
        min=1,
        max=100,
        help="Maximum number of breach lines to display",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    fail_on_not_ready: bool = typer.Option(True, "--fail-on-not-ready"),
):
    """Run consolidated release readiness checks across benchmarks/migration/plugins."""
    run_release_readiness_command(
        workspace=workspace,
        local_iterations=local_iterations,
        corpus_iterations=corpus_iterations,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        require_comparison=require_comparison,
        migration_root=migration_root,
        migration_pattern=migration_pattern,
        migration_max_workspaces=migration_max_workspaces,
        check_remote_health=check_remote_health,
        breach_category=breach_category,
        max_breaches=max_breaches,
        json_output=json_output,
        report_path=report_path,
        fail_on_not_ready=fail_on_not_ready,
        get_workspace_path_fn=get_workspace_path,
    )


@app.command()
def models(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    list_models: bool = typer.Option(False, "--list", "-l", help="List all available models"),
    current: bool = typer.Option(False, "--current", "-c", help="Show current model"),
):
    """* Manage AI models for the active provider.
    
    Interactive model selection with search and browse capabilities.
    The command refreshes the provider model list before showing results.
    
    Examples:
        clawlet models              # Interactive model selection
        clawlet models --list       # List all available models
        clawlet models --current    # Show current model
    """
    workspace_path = workspace or get_workspace_path()
    run_models_command(
        workspace_path=workspace_path,
        config_path=workspace_path / "config.yaml",
        current=current,
        list_models=list_models,
    )

# "?"? Plugin SDK commands "?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?

if __name__ == "__main__":
    app()
