"""
Status command module.
"""

import typer

from clawlet.cli import __version__, app, console, get_workspace_path, print_section, print_footer


@app.command(name="status")
def status():
    """🌸 Show Clawlet workspace status."""
    workspace_path = get_workspace_path()
    
    print_section("Workspace Status", f"Checking {workspace_path}")
    
    # Check workspace
    if workspace_path.exists():
        console.print(f"│  [green]✓[/green] Workspace [dim]{workspace_path}[/dim]")
    else:
        console.print(f"│  [red]✗[/red] Workspace [dim]not initialized[/dim]")
    
    # Check identity files
    for filename in ["SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"]:
        file_path = workspace_path / filename
        if file_path.exists():
            console.print(f"│  [green]✓[/green] {filename}")
        else:
            console.print(f"│  [red]✗[/red] {filename} [dim]missing[/dim]")
    
    # Check config
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        console.print(f"│  [green]✓[/green] config.yaml")
    else:
        console.print(f"│  [red]✗[/red] config.yaml [dim]missing[/dim]")
    
    print_footer()
    
    # Show version
    console.print()
    console.print(f"[dim]🌸 Version: {__version__}[/dim]")
    console.print()
