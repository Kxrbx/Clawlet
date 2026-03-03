"""Config display helpers for CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

from clawlet.cli.common_ui import print_footer, print_section

SAKURA_PINK = "#FF69B4"
console = Console()


def run_config_command(workspace_path: Path, key: Optional[str]) -> None:
    """View or inspect config values."""
    config_path = workspace_path / "config.yaml"
    if not config_path.exists():
        console.print(f"[red]Config file not found: {config_path}[/red]")
        raise typer.Exit(1)

    with open(config_path, encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    if key:
        keys = key.split(".")
        value = config_data
        for item in keys:
            if isinstance(value, dict):
                value = value.get(item)
            else:
                value = None
                break
        if value is not None:
            console.print(f"[{SAKURA_PINK}]{key}[/{SAKURA_PINK}]: {value}")
        else:
            console.print(f"[red]Key not found: {key}[/red]")
        return

    print_section("Configuration", str(config_path))
    console.print("|")

    def print_dict(data: dict, indent: int = 0) -> None:
        for name, val in data.items():
            prefix = "|  " + "  " * indent
            if isinstance(val, dict):
                console.print(f"{prefix}[bold]{name}:[/bold]")
                print_dict(val, indent + 1)
            else:
                console.print(f"{prefix}[{SAKURA_PINK}]{name}[/{SAKURA_PINK}]: {val}")

    print_dict(config_data)
    print_footer()
