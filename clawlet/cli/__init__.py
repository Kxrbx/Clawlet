"""
Clawlet CLI commands.
"""

from __future__ import annotations

import asyncio
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
from clawlet.cli.benchmark_ui import (
    run_benchmark_compare,
    run_benchmark_competitive_report,
    run_benchmark_coding_loop,
    run_benchmark_corpus,
    run_benchmark_context_cache,
    run_benchmark_equivalence,
    run_benchmark_lanes,
    run_benchmark_publish_report,
    run_benchmark_release_gate,
    run_benchmark_remote_health,
    run_benchmark_remote_parity,
    run_benchmark_run,
)
from clawlet.cli.config_ui import run_config_command
from clawlet.cli.dashboard_ui import run_dashboard_command
from clawlet.cli.common_ui import _filter_breach_lines, print_command, print_footer, print_section
from clawlet.cli.migration_ui import run_migrate_config, run_migration_matrix
from clawlet.cli.models_ui import run_models_command
from clawlet.cli.plugin_ui import (
    run_plugin_conformance,
    run_plugin_init,
    run_plugin_matrix,
    run_plugin_publish,
    run_plugin_test,
)
from clawlet.cli.recovery_ui import (
    run_recovery_cleanup,
    run_recovery_list,
    run_recovery_resume_payload,
    run_recovery_show,
)
from clawlet.cli.replay_ui import run_replay_command
from clawlet.cli.release_ui import run_release_readiness_command
from clawlet.cli.runtime_ui import run_agent_command, run_chat_command, run_logs_command
from clawlet.cli.sessions_ui import run_sessions_command
from clawlet.cli.templates import (
    get_config_template,
    get_heartbeat_template,
    get_memory_template,
    get_soul_template,
    get_user_template,
)
from clawlet.cli.workspace_ui import run_health, run_status, run_validate

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
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(plugin_app, name="plugin")
app.add_typer(recovery_app, name="recovery")

console = Console()


from clawlet.config import get_default_config_path


def get_workspace_path() -> Path:
    """Get the default workspace path."""
    return Path.home() / ".clawlet"


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

def print_main_menu():
    """Print the main menu when clawlet is invoked without args."""
    print_sakura_banner()
    
    print_section("Commands", "What would you like to do?")
    
    print_command("onboard", "Interactive setup wizard (recommended)", "clawlet onboard")
    print_command("init", "Quick workspace initialization", "clawlet init")
    print_command("agent", "Start your AI agent", "clawlet agent")
    print_command("models", "Manage AI models", "clawlet models")
    print_command("dashboard", "Launch web dashboard", "clawlet dashboard")
    print_command("benchmark", "Run performance regression suite", "clawlet benchmark run")
    print_command("replay", "Inspect deterministic run events", "clawlet replay <run_id>")
    print_command("plugin", "Manage plugin SDK extensions", "clawlet plugin init")
    print_command("recovery", "Inspect and recover interrupted runs", "clawlet recovery list")
    print_command("status", "Check workspace status", "clawlet status")
    print_command("health", "Run health checks", "clawlet health")
    print_command("validate", "Validate configuration", "clawlet validate")
    print_command("config", "View/edit configuration", "clawlet config")
    print_command("migrate-config", "Analyze/autofix legacy config keys", "clawlet migrate-config")
    print_command("migration-matrix", "Scan migration readiness across workspaces", "clawlet migration-matrix")
    print_command("release-readiness", "Run consolidated release readiness checks", "clawlet release-readiness")
    
    print_footer()
    
    console.print()
    console.print(f"[dim]* Run 'clawlet <command> --help' for more info[/dim]")
    console.print(f"[dim]* Version: {__version__} | https://github.com/Kxrbx/Clawlet[/dim]")
    console.print()


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
    
    # Create config file
    config_path = workspace_path / "config.yaml"
    if not config_path.exists() or force:
        config_path.write_text(get_config_template())
        console.print(f"|  [green]OK[/green] config.yaml")
    
    print_footer()
    
    console.print()
    console.print(f"[bold green]OK Workspace ready![/bold green]")
    console.print(f"  Location: [{SAKURA_PINK}]{workspace_path}[/{SAKURA_PINK}]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Edit [{SAKURA_PINK}]config.yaml[/{SAKURA_PINK}] to add API keys")
    console.print(f"  2. Run [{SAKURA_PINK}]clawlet agent[/{SAKURA_PINK}] to start")
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
def agent(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    channel: str = typer.Option("telegram", "--channel", "-c", help="Channel to use"),
    log_file: Optional[Path] = typer.Option(None, "--log-file", help="File to write logs to"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"),
):
    """* Start the Clawlet agent."""
    run_agent_command(
        workspace=workspace,
        model=model,
        channel=channel,
        log_file=log_file,
        log_level=log_level,
        get_workspace_path_fn=get_workspace_path,
        print_sakura_banner_fn=print_sakura_banner,
        sakura_light=SAKURA_LIGHT,
    )


@app.command()
def chat(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
):
    """* Start a local interactive chat session in the terminal."""
    run_chat_command(workspace=workspace, model=model, get_workspace_path_fn=get_workspace_path)


@app.command()
def logs(
    log_file: Path = typer.Option(Path.home() / ".clawlet" / "clawlet.log", "--log-file", "-f", help="Log file to read"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to display"),
    follow: bool = typer.Option(False, "--follow", help="Follow log output (tail -f)"),
):
    """* Tail the Clawlet agent logs."""
    run_logs_command(log_file=log_file, lines=lines, follow=follow)


@app.command()
def dashboard(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run on"),
    frontend_port: int = typer.Option(5173, "--frontend-port", "-f", help="Frontend dev server port"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser automatically"),
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
def health():
    """* Run health checks on all components."""
    run_health()


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
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create .bak backup when writing"),
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
    fail_on_not_ready: bool = typer.Option(True, "--fail-on-not-ready/--no-fail-on-not-ready"),
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
    """* Manage AI models for OpenRouter.
    
    Interactive model selection with search and browse capabilities.
    
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

# Benchmark and replay commands

@benchmark_app.command("run")
def benchmark_run(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    iterations: int = typer.Option(25, "--iterations", min=5, max=500, help="Benchmark iterations"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    fail_on_gate: bool = typer.Option(False, "--fail-on-gate", help="Exit non-zero when quality gates fail"),
):
    """Run local performance benchmark and evaluate quality gates."""
    run_benchmark_run(
        workspace=workspace,
        iterations=iterations,
        report_path=report_path,
        fail_on_gate=fail_on_gate,
        get_workspace_path_fn=get_workspace_path,
        load_benchmarks_settings_fn=load_benchmarks_settings,
    )


@benchmark_app.command("equivalence")
def benchmark_equivalence(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    strict_rust: bool = typer.Option(
        False,
        "--strict-rust",
        help="Fail if Rust extension is unavailable",
    ),
):
    """Run Python vs Rust execution equivalence checks."""
    run_benchmark_equivalence(workspace=workspace, strict_rust=strict_rust, get_workspace_path_fn=get_workspace_path)


@benchmark_app.command("remote-health")
def benchmark_remote_health(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Check configured remote worker health endpoint."""
    run_benchmark_remote_health(workspace=workspace, get_workspace_path_fn=get_workspace_path)


@benchmark_app.command("remote-parity")
def benchmark_remote_parity(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Run remote/local execution parity smokecheck."""
    run_benchmark_remote_parity(workspace=workspace, get_workspace_path_fn=get_workspace_path)


@benchmark_app.command("lanes")
def benchmark_lanes(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
):
    """Run lane scheduling benchmark (serial vs parallel)."""
    run_benchmark_lanes(workspace=workspace, report_path=report_path, get_workspace_path_fn=get_workspace_path)


@benchmark_app.command("context-cache")
def benchmark_context_cache(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
):
    """Run context-engine warm-cache vs cold-cache benchmark."""
    run_benchmark_context_cache(
        workspace=workspace,
        report_path=report_path,
        get_workspace_path_fn=get_workspace_path,
    )


@benchmark_app.command("coding-loop")
def benchmark_coding_loop(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    iterations: int = typer.Option(10, "--iterations", min=1, max=200, help="Benchmark iterations"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
):
    """Run coding-loop benchmark (inspect -> patch -> verify -> summarize)."""
    run_benchmark_coding_loop(
        workspace=workspace,
        iterations=iterations,
        report_path=report_path,
        get_workspace_path_fn=get_workspace_path,
    )


@benchmark_app.command("corpus")
def benchmark_corpus(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    iterations: int = typer.Option(10, "--iterations", min=1, max=200, help="Iterations per scenario"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    baseline_report: Optional[Path] = typer.Option(
        None,
        "--baseline-report",
        help="Optional baseline report JSON (OpenClaw or previous Clawlet run)",
    ),
    target_improvement_pct: float = typer.Option(
        35.0,
        "--target-improvement-pct",
        min=0.0,
        max=100.0,
        help="Required p95 improvement percent vs baseline",
    ),
    fail_on_gate: bool = typer.Option(False, "--fail-on-gate", help="Exit non-zero when quality gates fail"),
    fail_on_regression: bool = typer.Option(
        False,
        "--fail-on-regression",
        help="Exit non-zero on baseline regressions or target miss",
    ),
    publish_report: bool = typer.Option(
        False,
        "--publish-report",
        help="Generate a publishable markdown report (requires --baseline-report)",
    ),
    publish_report_path: Optional[Path] = typer.Option(
        None,
        "--publish-report-path",
        help="Output markdown report path (default: benchmark-openclaw-report.md in workspace)",
    ),
):
    """Run OpenClaw-matched corpus and optional baseline comparison."""
    run_benchmark_corpus(
        workspace=workspace,
        iterations=iterations,
        report_path=report_path,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        fail_on_gate=fail_on_gate,
        fail_on_regression=fail_on_regression,
        publish_report=publish_report,
        publish_report_path=publish_report_path,
        get_workspace_path_fn=get_workspace_path,
        load_benchmarks_settings_fn=load_benchmarks_settings,
        print_corpus_comparison_summary_fn=print_corpus_comparison_summary,
    )


@benchmark_app.command("compare")
def benchmark_compare(
    current_report: Path = typer.Option(..., "--current-report", help="Current corpus report JSON"),
    baseline_report: Path = typer.Option(..., "--baseline-report", help="Baseline corpus report JSON"),
    target_improvement_pct: float = typer.Option(
        35.0,
        "--target-improvement-pct",
        min=0.0,
        max=100.0,
        help="Required p95 improvement percent vs baseline",
    ),
    fail_on_regression: bool = typer.Option(
        True,
        "--fail-on-regression/--no-fail-on-regression",
        help="Exit non-zero on regressions or target miss",
    ),
    publish_report_path: Optional[Path] = typer.Option(
        None,
        "--publish-report-path",
        help="Optional markdown report output path",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
):
    """Compare two saved OpenClaw-matched corpus reports."""
    run_benchmark_compare(
        current_report=current_report,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        fail_on_regression=fail_on_regression,
        publish_report_path=publish_report_path,
        json_output=json_output,
        print_corpus_comparison_summary_fn=print_corpus_comparison_summary,
        corpus_comparison_payload_fn=corpus_comparison_payload,
    )

@benchmark_app.command("publish-report")
def benchmark_publish_report(
    current_report: Path = typer.Option(..., "--current-report", help="Current corpus report JSON"),
    baseline_report: Path = typer.Option(..., "--baseline-report", help="Baseline corpus report JSON"),
    out: Path = typer.Option(Path("benchmark-openclaw-report.md"), "--out", help="Output markdown report path"),
    target_improvement_pct: float = typer.Option(
        35.0,
        "--target-improvement-pct",
        min=0.0,
        max=100.0,
        help="Required p95 improvement percent vs baseline",
    ),
    fail_on_regression: bool = typer.Option(
        True,
        "--fail-on-regression/--no-fail-on-regression",
        help="Exit non-zero on regressions or target miss",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
):
    """Generate publishable markdown report from current/baseline corpus reports."""
    run_benchmark_publish_report(
        current_report=current_report,
        baseline_report=baseline_report,
        out=out,
        target_improvement_pct=target_improvement_pct,
        fail_on_regression=fail_on_regression,
        json_output=json_output,
        print_regressions_fn=print_regressions,
        corpus_comparison_payload_fn=corpus_comparison_payload,
    )

@benchmark_app.command("competitive-report")
def benchmark_competitive_report(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    iterations: int = typer.Option(10, "--iterations", min=1, max=200, help="Iterations per scenario"),
    baseline_report: Path = typer.Option(..., "--baseline-report", help="Baseline corpus report JSON"),
    target_improvement_pct: float = typer.Option(
        35.0,
        "--target-improvement-pct",
        min=0.0,
        max=100.0,
        help="Required p95 improvement percent vs baseline",
    ),
    corpus_report_out: Optional[Path] = typer.Option(
        None,
        "--corpus-report-out",
        help="Optional current corpus report JSON output path",
    ),
    bundle_out: Optional[Path] = typer.Option(
        None,
        "--bundle-out",
        help="Optional machine-readable competitive bundle JSON output path",
    ),
    markdown_out: Optional[Path] = typer.Option(
        None,
        "--markdown-out",
        help="Optional publishable markdown output path",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
    fail_on_gate: bool = typer.Option(True, "--fail-on-gate/--no-fail-on-gate"),
    fail_on_regression: bool = typer.Option(True, "--fail-on-regression/--no-fail-on-regression"),
):
    """Run corpus benchmark + baseline comparison and emit publishable artifacts."""
    run_benchmark_competitive_report(
        workspace=workspace,
        iterations=iterations,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        corpus_report_out=corpus_report_out,
        bundle_out=bundle_out,
        markdown_out=markdown_out,
        json_output=json_output,
        fail_on_gate=fail_on_gate,
        fail_on_regression=fail_on_regression,
        get_workspace_path_fn=get_workspace_path,
        load_benchmarks_settings_fn=load_benchmarks_settings,
        print_regressions_fn=print_regressions,
    )


@benchmark_app.command("release-gate")
def benchmark_release_gate(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    local_iterations: int = typer.Option(
        25,
        "--local-iterations",
        min=1,
        max=500,
        help="Iterations for local runtime benchmark",
    ),
    corpus_iterations: int = typer.Option(
        10,
        "--corpus-iterations",
        min=1,
        max=200,
        help="Iterations per corpus scenario",
    ),
    baseline_report: Optional[Path] = typer.Option(
        None,
        "--baseline-report",
        help="Optional baseline corpus report for superiority comparison",
    ),
    target_improvement_pct: float = typer.Option(
        35.0,
        "--target-improvement-pct",
        min=0.0,
        max=100.0,
        help="Required p95 improvement vs baseline",
    ),
    require_comparison: bool = typer.Option(
        False,
        "--require-comparison",
        help="Fail gate when --baseline-report is not provided",
    ),
    report_path: Optional[Path] = typer.Option(
        None,
        "--report",
        help="Optional JSON report output path",
    ),
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
    fail_on_gate: bool = typer.Option(
        True,
        "--fail-on-gate/--no-fail-on-gate",
        help="Exit non-zero when any release gate fails",
    ),
):
    """Run consolidated benchmark release gates in one command."""
    run_benchmark_release_gate(
        workspace=workspace,
        local_iterations=local_iterations,
        corpus_iterations=corpus_iterations,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        require_comparison=require_comparison,
        report_path=report_path,
        breach_category=breach_category,
        max_breaches=max_breaches,
        json_output=json_output,
        fail_on_gate=fail_on_gate,
        get_workspace_path_fn=get_workspace_path,
        load_benchmarks_settings_fn=load_benchmarks_settings,
        filter_breach_lines_fn=_filter_breach_lines,
    )


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
        "--fail-on-mismatch/--no-fail-on-mismatch",
        help="Exit non-zero when replay reexecution detects mismatches",
    ),
):
    """Inspect structured runtime events for a run."""
    run_replay_command(
        run_id=run_id,
        workspace_path=workspace or get_workspace_path(),
        limit=limit,
        show_signature=show_signature,
        verify=verify,
        verify_resume=verify_resume,
        reliability=reliability,
        reexecute=reexecute,
        allow_write_reexecute=allow_write_reexecute,
        fail_on_mismatch=fail_on_mismatch,
    )


# "?"? Recovery commands "?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?

@recovery_app.command("list")
def recovery_list(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    limit: int = typer.Option(20, "--limit", min=1, max=500, help="Maximum checkpoints"),
):
    """List interrupted runs with available checkpoints."""
    run_recovery_list(workspace_path=workspace or get_workspace_path(), limit=limit)


@recovery_app.command("show")
def recovery_show(
    run_id: str = typer.Argument(..., help="Run ID"),
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Show checkpoint details for one run id."""
    run_recovery_show(workspace_path=workspace or get_workspace_path(), run_id=run_id)


@recovery_app.command("resume-payload")
def recovery_resume_payload(
    run_id: str = typer.Argument(..., help="Run ID"),
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Render recovery inbound payload for manual resume orchestration."""
    run_recovery_resume_payload(workspace_path=workspace or get_workspace_path(), run_id=run_id)


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
        workspace_path=workspace or get_workspace_path(),
        retention_days=retention_days,
        dry_run=dry_run,
    )


# "?"? Plugin SDK commands "?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?

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
        "--strict/--no-strict",
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
        workspace_path=workspace or get_workspace_path(),
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


# "?"? Sessions management "?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?

@app.command()
def sessions(
    workspace: Optional[Path] = typer.Option(None, "--workspace", help="Workspace directory"),
    export: Optional[Path] = typer.Option(None, "--export", help="Export sessions to JSON file"),
    limit: int = typer.Option(10, "--limit", help="Number of recent sessions to list"),
):
    """* List and export conversation sessions from storage."""
    run_sessions_command(workspace_path=workspace or get_workspace_path(), export=export, limit=limit)


if __name__ == "__main__":
    app()





