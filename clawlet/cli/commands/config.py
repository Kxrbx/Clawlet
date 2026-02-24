"""
Config command module.
"""

from pathlib import Path
from typing import Optional

import typer
import yaml

from clawlet.cli import SAKURA_PINK, app, console, get_workspace_path, print_section, print_footer


@app.command()
def config(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    key: Optional[str] = typer.Argument(None, help="Config key to show"),
):
    """🌸 View or manage configuration."""
    workspace_path = workspace or get_workspace_path()
    config_path = workspace_path / "config.yaml"
    
    if not config_path.exists():
        console.print(f"[red]Config file not found: {config_path}[/red]")
        raise typer.Exit(1)
    
    with open(config_path) as f:
        config_data = yaml.safe_load(f)
    
    if key:
        # Show specific key
        keys = key.split(".")
        value = config_data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
        
        if value is not None:
            console.print(f"[{SAKURA_PINK}]{key}[/{SAKURA_PINK}]: {value}")
        else:
            console.print(f"[red]Key not found: {key}[/red]")
    else:
        # Show all config
        print_section("Configuration", str(config_path))
        console.print("│")
        
        def print_dict(d, indent=0):
            for k, v in d.items():
                prefix = "│  " + "  " * indent
                if isinstance(v, dict):
                    console.print(f"{prefix}[bold]{k}:[/bold]")
                    print_dict(v, indent + 1)
                else:
                    console.print(f"{prefix}[{SAKURA_PINK}]{k}[/{SAKURA_PINK}]: {v}")
        
        print_dict(config_data)
        print_footer()
