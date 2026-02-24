"""
Validate command module.
"""

from pathlib import Path

import typer

from clawlet.cli import SAKURA_PINK, app, console, get_workspace_path, print_section, print_footer
from clawlet.config import Config


@app.command(name="validate")
def validate(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """🌸 Validate configuration file."""
    workspace_path = workspace or get_workspace_path()
    config_path = workspace_path / "config.yaml"
    
    print_section("Config Validation", f"Checking {config_path}")
    
    if not config_path.exists():
        console.print(f"│  [red]✗[/red] Config file not found")
        console.print("│")
        console.print("│  [dim]Run 'clawlet init' to create a config file[/dim]")
        print_footer()
        raise typer.Exit(1)
    
    try:
        config = Config.from_yaml(config_path)
        
        console.print(f"│  [green]✓[/green] Configuration is valid")
        console.print("│")
        console.print(f"│  [bold]Settings:[/bold]")
        console.print(f"│    Provider: [{SAKURA_PINK}]{config.provider.primary}[/{SAKURA_PINK}]")
        if config.provider.openrouter:
            console.print(f"│    Model: [{SAKURA_PINK}]{config.provider.openrouter.model}[/{SAKURA_PINK}]")
        console.print(f"│    Storage: [{SAKURA_PINK}]{config.storage.backend}[/{SAKURA_PINK}]")
        console.print(f"│    Max Iterations: [{SAKURA_PINK}]{config.agent.max_iterations}[/{SAKURA_PINK}]")
        
        print_footer()
        console.print()
        
    except Exception as e:
        console.print(f"│  [red]✗[/red] Configuration error: {e}")
        print_footer()
        raise typer.Exit(1)
