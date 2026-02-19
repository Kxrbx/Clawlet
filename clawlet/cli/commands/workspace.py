"""
Workspace commands module.
"""

from typing import Optional

import typer
from rich.table import Table

from clawlet.cli import SAKURA_LIGHT, SAKURA_PINK, app, console, get_workspace_path, print_section, print_footer
from clawlet.agent.workspace import WorkspaceManager


workspace_app = typer.Typer(
    name="workspace",
    help="Manage multiple agent workspaces",
)

app.add_typer(workspace_app, name="workspace")


@workspace_app.command("list")
def workspace_list():
    """List all workspaces."""
    manager = WorkspaceManager(get_workspace_path())
    workspaces = manager.list_workspace_statuses()
    
    print_section("Workspaces", "Available agent workspaces")
    console.print("¦")
    
    if not workspaces:
        console.print("¦  [dim]No workspaces found[/dim]")
        console.print("¦")
        console.print("¦  [dim]Create one with: clawlet workspace create <name>[/dim]")
    else:
        # Create table
        table = Table(show_header=True, header_style=f"bold {SAKURA_PINK}", box=None)
        table.add_column("Name", style=SAKURA_LIGHT)
        table.add_column("Status", style="dim")
        table.add_column("Config", style="dim")
        table.add_column("Identity", style="dim")
        
        for ws in workspaces:
            status_icon = "[green]running[/green]" if ws.is_running else "[dim]stopped[/dim]"
            config_icon = "[green]✓[/green]" if ws.has_config else "[red]✗[/red]"
            identity_icon = "[green]✓[/green]" if ws.has_identity else "[red]✗[/red]"
            
            table.add_row(
                ws.name,
                status_icon,
                config_icon,
                identity_icon
            )
        
        for line in table.to_string().split("\n"):
            console.print(f"¦  {line}")
    
    print_footer()
    
    # Show routing status
    console.print()
    from clawlet.config import load_config
    try:
        config = load_config(get_workspace_path())
        if config.routing.enabled:
            console.print(f"[green]✓ Multi-agent routing enabled[/green]")
            console.print(f"  Default agent: [{SAKURA_PINK}]{config.routing.default_agent}[/{SAKURA_PINK}]")
            console.print(f"  Routes: {len(config.routing.routes)}")
        else:
            console.print("[dim]Multi-agent routing disabled[/dim]")
    except Exception:
        pass


@workspace_app.command("create")
def workspace_create(
    name: str = typer.Argument(..., help="Workspace name"),
    agent_name: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent name"),
    user_name: Optional[str] = typer.Option(None, "--user", "-u", help="User name"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing"),
):
    """Create a new workspace."""
    manager = WorkspaceManager(get_workspace_path())
    
    # Check if exists
    existing = manager.get_workspace(name)
    if existing and existing.exists() and not force:
        console.print(f"[red]Error: Workspace '{name}' already exists[/red]")
        console.print(f"  Use --force to overwrite")
        raise typer.Exit(1)
    
    print_section("Create Workspace", f"Creating workspace '{name}'")
    console.print("¦")
    
    try:
        workspace = manager.create_workspace(
            name=name,
            agent_name=agent_name,
            user_name=user_name,
        )
        
        console.print(f"¦  [green]✓[/green] Created workspace at [{SAKURA_PINK}]{workspace.path}[/{SAKURA_PINK}]")
        console.print("¦")
        console.print(f"¦  [dim]Files created:[/dim]")
        console.print(f"¦    [dim]config.yaml[/dim]")
        console.print(f"¦    [dim]SOUL.md[/dim]")
        console.print(f"¦    [dim]USER.md[/dim]")
        console.print(f"¦    [dim]MEMORY.md[/dim]")
        console.print(f"¦    [dim]HEARTBEAT.md[/dim]")
        
        print_footer()
        
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print(f"  1. Edit [{SAKURA_PINK}]{workspace.path}/config.yaml[/{SAKURA_PINK}] to configure")
        console.print(f"  2. Edit [{SAKURA_PINK}]{workspace.path}/SOUL.md[/{SAKURA_PINK}] to customize agent")
        console.print(f"  3. Add routing rules to main config.yaml")
        console.print()
        
    except Exception as e:
        console.print(f"¦  [red]✗ Error creating workspace: {e}[/red]")
        print_footer()
        raise typer.Exit(1)


@workspace_app.command("delete")
def workspace_delete(
    name: str = typer.Argument(..., help="Workspace name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a workspace."""
    manager = WorkspaceManager(get_workspace_path())
    workspace = manager.get_workspace(name)
    
    if not workspace or not workspace.exists():
        console.print(f"[red]Error: Workspace '{name}' not found[/red]")
        raise typer.Exit(1)
    
    if workspace._running:
        console.print(f"[red]Error: Workspace '{name}' is running. Stop it first.[/red]")
        raise typer.Exit(1)
    
    # Confirm
    if not yes:
        console.print(f"[yellow]Warning: This will delete all files in {workspace.path}[/yellow]")
        confirm = typer.confirm(f"Delete workspace '{name}'?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)
    
    print_section("Delete Workspace", f"Deleting workspace '{name}'")
    console.print("¦")
    
    if manager.delete_workspace(name):
        console.print(f"¦  [green]✓[/green] Workspace '{name}' deleted")
        print_footer()
    else:
        console.print(f"¦  [red]✗ Failed to delete workspace[/red]")
        print_footer()
        raise typer.Exit(1)


@workspace_app.command("show")
def workspace_show(
    name: str = typer.Argument(..., help="Workspace name"),
):
    """Show workspace details."""
    manager = WorkspaceManager(get_workspace_path())
    workspace = manager.get_workspace(name)
    
    if not workspace or not workspace.exists():
        console.print(f"[red]Error: Workspace '{name}' not found[/red]")
        raise typer.Exit(1)
    
    status = workspace.get_status()
    
    print_section(f"Workspace: {name}", str(workspace.path))
    console.print("¦")
    
    console.print(f"¦  [bold]Path:[/bold] {status.path}")
    console.print(f"¦  [bold]Exists:[/bold] {'[green]Yes[/green]' if status.exists else '[red]No[/red]'}")
    console.print(f"¦  [bold]Config:[/bold] {'[green]Yes[/green]' if status.has_config else '[red]No[/red]'}")
    console.print(f"¦  [bold]Identity:[/bold] {'[green]Yes[/green]' if status.has_identity else '[red]No[/red]'}")
    console.print(f"¦  [bold]Running:[/bold] {'[green]Yes[/green]' if status.is_running else '[dim]No[/dim]'}")
    
    print_footer()
    
    # Show files
    console.print()
    console.print("[bold]Files:[/bold]")
    
    for filename in ["config.yaml", "SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"]:
        file_path = workspace.path / filename
        if file_path.exists():
            size = file_path.stat().st_size
            console.print(f"  [green]✓[/green] {filename} [dim]({size} bytes)[/dim]")
        else:
            console.print(f"  [red]✗[/red] {filename} [dim](missing)[/dim]")


@workspace_app.command("start")
def workspace_start(
    name: str = typer.Argument(..., help="Workspace name"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
):
    """Start a workspace agent."""
    console.print("[yellow]Note: This command requires integration with the agent loop.[/yellow]")
    console.print("[dim]For now, use 'clawlet agent' to start the default agent.[/dim]")
    console.print()
    console.print(f"To start workspace '{name}' with routing:")
    console.print(f"  1. Enable routing in config.yaml")
    console.print(f"  2. Add route for the workspace")
    console.print(f"  3. Run 'clawlet agent'")


@workspace_app.command("stop")
def workspace_stop(
    name: str = typer.Argument(..., help="Workspace name"),
):
    """Stop a workspace agent."""
    console.print("[yellow]Note: This command requires integration with the agent loop.[/yellow]")
    console.print("[dim]For now, use Ctrl+C to stop the running agent.[/dim]")
