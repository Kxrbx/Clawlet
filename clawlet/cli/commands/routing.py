"""
Routing command module.
"""

import typer

from clawlet.cli import SAKURA_PINK, app, console, get_workspace_path, print_section, print_footer
from clawlet.config import load_config


@app.command("routing")
def routing_cmd(
    list_routes: bool = typer.Option(False, "--list", "-l", help="List routing rules"),
    enable: bool = typer.Option(False, "--enable", help="Enable routing"),
    disable: bool = typer.Option(False, "--disable", help="Disable routing"),
    add_route: bool = typer.Option(False, "--add", help="Add a route interactively"),
):
    """Manage multi-agent routing configuration."""
    workspace_path = get_workspace_path()
    config_path = workspace_path / "config.yaml"
    
    if not config_path.exists():
        console.print("[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]")
        raise typer.Exit(1)
    
    config = load_config(workspace_path)
    
    # Handle enable/disable
    if enable:
        config.routing.enabled = True
        config.to_yaml(config_path)
        console.print("[green]✓ Multi-agent routing enabled[/green]")
        return
    
    if disable:
        config.routing.enabled = False
        config.to_yaml(config_path)
        console.print("[green]✓ Multi-agent routing disabled[/green]")
        return
    
    # Handle add route
    if add_route:
        console.print("[yellow]Interactive route addition coming soon.[/yellow]")
        console.print("[dim]For now, edit config.yaml directly to add routes.[/dim]")
        return
    
    # Default: show routing status
    print_section("Routing Configuration", "Multi-agent routing settings")
    console.print("¦")
    
    status = "enabled" if config.routing.enabled else "disabled"
    status_color = "green" if config.routing.enabled else "dim"
    console.print(f"¦  Status: [{status_color}]{status}[/{status_color}]")
    console.print(f"¦  Default agent: [{SAKURA_PINK}]{config.routing.default_agent}[/{SAKURA_PINK}]")
    console.print("¦")
    
    if config.routing.routes:
        console.print("¦  [bold]Routes:[/bold]")
        for i, route in enumerate(config.routing.routes):
            conditions = []
            if route.channel:
                conditions.append(f"channel={route.channel}")
            if route.user_id:
                conditions.append(f"user={route.user_id}")
            if route.pattern:
                conditions.append(f"pattern={route.pattern}")
            
            cond_str = ", ".join(conditions) if conditions else "all"
            console.print(f"¦    {i+1}. [{SAKURA_PINK}]{route.agent}[/{SAKURA_PINK}] ({cond_str}) priority={route.priority}")
    else:
        console.print("¦  [dim]No routes configured[/dim]")
    
    print_footer()
    
    console.print()
    console.print("[dim]Edit config.yaml to add or modify routes.[/dim]")
