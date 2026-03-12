"""Workspace status/health/config validation helpers for the CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from clawlet.cli.common_ui import print_footer, print_section

SAKURA_PINK = "#FF69B4"
console = Console()


def run_status(workspace_path: Path, version: str) -> None:
    """Render workspace status summary."""
    print_section("Workspace Status", f"Checking {workspace_path}")

    if workspace_path.exists():
        console.print(f"|  [green]OK[/green] Workspace [dim]{workspace_path}[/dim]")
    else:
        console.print("|  [red]x[/red] Workspace [dim]not initialized[/dim]")

    for filename in ["SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"]:
        file_path = workspace_path / filename
        if file_path.exists():
            console.print(f"|  [green]OK[/green] {filename}")
        else:
            console.print(f"|  [red]x[/red] {filename} [dim]missing[/dim]")

    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        console.print("|  [green]OK[/green] config.yaml")
    else:
        console.print("|  [red]x[/red] config.yaml [dim]missing[/dim]")

    print_footer()
    console.print()
    console.print(f"[dim]* Version: {version}[/dim]")
    console.print()


def run_health() -> None:
    """Run health checks and render summary."""
    from clawlet.health import quick_health_check

    print_section("Health Checks", "Checking system components")

    async def run_checks():
        return await quick_health_check()

    result = asyncio.run(run_checks())
    for check in result.get("checks", []):
        status = check["status"]
        if status == "healthy":
            console.print(f"|  [green]OK[/green] {check['name']}: {check['message']}")
        elif status == "degraded":
            console.print(f"|  [yellow]![/yellow] {check['name']}: {check['message']}")
        else:
            console.print(f"|  [red]x[/red] {check['name']}: {check['message']}")

    print_footer()

    overall = result.get("status", "unknown")
    console.print()
    if overall == "healthy":
        console.print("[green]OK All systems operational[/green]")
    elif overall == "degraded":
        console.print("[yellow]! Some systems degraded[/yellow]")
    else:
        console.print("[red]x Some systems unhealthy[/red]")
    console.print()


def run_validate(workspace_path: Path, migration: bool = False) -> None:
    """Validate workspace config and optional migration compatibility."""
    from clawlet.config import Config

    config_path = workspace_path / "config.yaml"
    print_section("Config Validation", f"Checking {config_path}")

    if not config_path.exists():
        console.print("|  [red]x[/red] Config file not found")
        console.print("|")
        console.print("|  [dim]Run 'clawlet init' to create a config file[/dim]")
        print_footer()
        raise typer.Exit(1)

    try:
        config = Config.from_yaml(config_path)
        provider_issue = config.primary_provider_issue()

        console.print("|  [green]OK[/green] Configuration is valid")
        if provider_issue:
            console.print(f"|  [red]x[/red] {provider_issue}")
            print_footer()
            raise typer.Exit(1)
        console.print("|")
        console.print("|  [bold]Settings:[/bold]")
        console.print(f"|    Provider: [{SAKURA_PINK}]{config.provider.primary}[/{SAKURA_PINK}]")
        if config.provider.openrouter:
            console.print(f"|    Model: [{SAKURA_PINK}]{config.provider.openrouter.model}[/{SAKURA_PINK}]")
        console.print(f"|    Storage: [{SAKURA_PINK}]{config.storage.backend}[/{SAKURA_PINK}]")
        console.print(f"|    Max Iterations: [{SAKURA_PINK}]{config.agent.max_iterations}[/{SAKURA_PINK}]")

        if migration:
            from clawlet.config_migration import analyze_config_migration

            report = analyze_config_migration(config_path)
            console.print("|")
            console.print(f"|  [bold]Migration Analysis:[/bold] {len(report.issues)} issue(s)")
            for issue in report.issues:
                marker = "?"
                if issue.severity == "error":
                    marker = "[red]x[/red]"
                elif issue.severity == "warning":
                    marker = "[yellow]![/yellow]"
                else:
                    marker = "[cyan]i[/cyan]"
                auto = " [dim](autofixable)[/dim]" if issue.can_autofix else ""
                console.print(
                    f"|    {marker} {issue.severity.upper()} {issue.path}: {issue.message}{auto}"
                )
                console.print(f"|      hint: {issue.hint}")
            if report.has_blockers:
                print_footer()
                raise typer.Exit(2)

        print_footer()
        console.print()
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"|  [red]x[/red] Configuration error: {e}")
        print_footer()
        raise typer.Exit(1)
