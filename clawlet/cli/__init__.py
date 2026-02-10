"""
Clawlet CLI commands.
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from clawlet import __version__

app = typer.Typer(
    name="clawlet",
    help="🦞 Clawlet - A lightweight AI agent framework",
    no_args_is_help=True,
)

console = Console()


def get_workspace_path() -> Path:
    """Get the default workspace path."""
    return Path.home() / ".clawlet"


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit"
    )
):
    """Clawlet - A lightweight AI agent framework with identity awareness."""
    if version:
        console.print(f"clawlet version {__version__}")
        raise typer.Exit()


@app.command()
def init(
    workspace: Path = typer.Option(
        None, "--workspace", "-w", help="Workspace directory"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
):
    """Initialize a new Clawlet workspace (quick setup).
    
    For guided setup with all options, use 'clawlet onboard' instead.
    """
    workspace_path = workspace or get_workspace_path()
    
    # If workspace doesn't exist, suggest onboard
    if not workspace_path.exists():
        console.print()
        console.print("[dim]💡 Tip: For a guided setup experience, try:[/dim]")
        console.print("[cyan]    clawlet onboard[/cyan]")
        console.print()
    
    console.print(Panel.fit(
        "🦞 [bold cyan]Clawlet Quick Setup[/bold cyan]",
        subtitle="Creating your workspace..."
    ))
    
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
            console.print(f"  [yellow]⏭️  {filename} already exists, skipping[/yellow]")
        else:
            file_path.write_text(content)
            console.print(f"  [green]✓ Created {filename}[/green]")
    
    # Create config file
    config_path = workspace_path / "config.yaml"
    if not config_path.exists() or force:
        config_path.write_text(get_config_template())
        console.print(f"  [green]✓ Created config.yaml[/green]")
    
    console.print()
    console.print(Panel(
        f"[bold green]Workspace initialized![/bold green]\n\n"
        f"Location: [cyan]{workspace_path}[/cyan]\n\n"
        f"Next steps:\n"
        f"  1. Edit [cyan]{workspace_path}/SOUL.md[/cyan] to define who your agent is\n"
        f"  2. Edit [cyan]{workspace_path}/USER.md[/cyan] with your info\n"
        f"  3. Add your API keys to [cyan]{workspace_path}/config.yaml[/cyan]\n"
        f"  4. Run [cyan]clawlet agent[/cyan] to start!",
        title="🎉 Done",
    ))


@app.command()
def onboard():
    """Interactive onboarding with guided setup (recommended for first-time users)."""
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
):
    """Start the Clawlet agent."""
    workspace_path = workspace or get_workspace_path()
    
    if not workspace_path.exists():
        console.print("[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]")
        raise typer.Exit(1)
    
    console.print(Panel.fit(
        f"🦞 [bold cyan]Starting Clawlet Agent[/bold cyan]\n"
        f"Workspace: [dim]{workspace_path}[/dim]"
    ))
    
    # Import and run the agent
    from clawlet.agent.loop import AgentLoop
    from clawlet.agent.identity import IdentityLoader
    from clawlet.bus.queue import MessageBus
    
    try:
        # Load identity
        identity = IdentityLoader(workspace_path)
        console.print(f"[green]✓ Loaded identity from {workspace_path}[/green]")
        
        # Start the agent loop
        console.print(f"[cyan]Starting agent with {channel} channel...[/cyan]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        
        asyncio.run(run_agent(workspace_path, model, channel))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Agent stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


async def run_agent(workspace: Path, model: Optional[str], channel: str):
    """Run the agent loop."""
    from clawlet.agent.loop import AgentLoop
    from clawlet.agent.identity import IdentityLoader
    from clawlet.bus.queue import MessageBus
    
    # Load identity
    identity = IdentityLoader(workspace)
    
    # Create message bus
    bus = MessageBus()
    
    # Create agent loop
    agent = AgentLoop(
        bus=bus,
        workspace=workspace,
        identity=identity,
        model=model,
    )
    
    # Run the agent
    await agent.run()


@app.command()
def dashboard(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run on"),
):
    """Start the Clawlet dashboard."""
    workspace_path = workspace or get_workspace_path()
    
    console.print(Panel.fit(
        f"🦞 [bold cyan]Starting Clawlet Dashboard[/bold cyan]\n"
        f"Workspace: [dim]{workspace_path}[/dim]\n"
        f"Port: [dim]{port}[/dim]"
    ))
    
    console.print("[yellow]Dashboard coming soon![/yellow]")
    console.print("For now, use 'clawlet agent' to run your agent.")


@app.command()
def status():
    """Show Clawlet status."""
    workspace_path = get_workspace_path()
    
    table = Table(title="🦞 Clawlet Status")
    table.add_column("Item", style="cyan")
    table.add_column("Status", style="green")
    
    # Check workspace
    if workspace_path.exists():
        table.add_row("Workspace", f"✓ {workspace_path}")
    else:
        table.add_row("Workspace", "✗ Not initialized")
    
    # Check identity files
    for filename in ["SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"]:
        file_path = workspace_path / filename
        if file_path.exists():
            table.add_row(filename, "✓ Present")
        else:
            table.add_row(filename, "✗ Missing")
    
    # Check config
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        table.add_row("Config", "✓ Present")
    else:
        table.add_row("Config", "✗ Missing")
    
    console.print(table)
    
    # Show version
    console.print(f"\n[dim]Version: {__version__}[/dim]")


@app.command()
def health():
    """Run health checks on all components."""
    console.print(Panel.fit(
        "🦞 [bold cyan]Clawlet Health Check[/bold cyan]"
    ))
    
    import asyncio
    from clawlet.health import quick_health_check
    
    async def run_checks():
        result = await quick_health_check()
        return result
    
    result = asyncio.run(run_checks())
    
    # Display results
    table = Table(title="Health Check Results")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Message", style="dim")
    
    status_color = {
        "healthy": "[green]✓ Healthy[/green]",
        "degraded": "[yellow]⚠ Degraded[/yellow]",
        "unhealthy": "[red]✗ Unhealthy[/red]",
    }
    
    for check in result.get("checks", []):
        status_str = status_color.get(check["status"], check["status"])
        table.add_row(check["name"], status_str, check["message"])
    
    console.print(table)
    
    # Overall status
    overall = result.get("status", "unknown")
    if overall == "healthy":
        console.print("\n[green]✓ All systems operational[/green]")
    elif overall == "degraded":
        console.print("\n[yellow]⚠ Some systems degraded[/yellow]")
    else:
        console.print("\n[red]✗ Some systems unhealthy[/red]")


@app.command()
def validate(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Validate configuration file."""
    workspace_path = workspace or get_workspace_path()
    config_path = workspace_path / "config.yaml"
    
    console.print(Panel.fit(
        "🦞 [bold cyan]Validating Configuration[/bold cyan]"
    ))
    
    if not config_path.exists():
        console.print(f"[red]✗ Config file not found: {config_path}[/red]")
        console.print("\n[yellow]Run 'clawlet init' to create a config file.[/yellow]")
        raise typer.Exit(1)
    
    try:
        from clawlet.config import Config
        
        config = Config.from_yaml(config_path)
        
        console.print("[green]✓ Configuration is valid![/green]")
        
        # Show config summary
        table = Table(title="Configuration Summary")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Provider", config.provider.primary)
        if config.provider.openrouter:
            model = config.provider.openrouter.model
            table.add_row("Model", model)
        table.add_row("Storage", config.storage.backend)
        table.add_row("Max Iterations", str(config.agent.max_iterations))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]✗ Configuration error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def config(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    key: Optional[str] = typer.Argument(None, help="Config key to show"),
):
    """Show or manage configuration."""
    workspace_path = workspace or get_workspace_path()
    config_path = workspace_path / "config.yaml"
    
    if not config_path.exists():
        console.print(f"[red]Config file not found: {config_path}[/red]")
        raise typer.Exit(1)
    
    import yaml
    
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
            console.print(f"[cyan]{key}[/cyan]: {value}")
        else:
            console.print(f"[red]Key not found: {key}[/red]")
    else:
        # Show all config
        console.print_yaml(config_data)


# Template functions

def get_soul_template() -> str:
    return """# SOUL.md - Who You Are

This file defines your agent's core identity, personality, and values.

## Name
Clawlet

## Purpose
I am a lightweight AI assistant designed to be helpful, honest, and harmless.

## Personality
- Warm and supportive
- Clear and concise
- Curious and eager to help
- Respectful of boundaries

## Values
1. **Helpfulness**: I strive to provide genuinely useful assistance
2. **Honesty**: I'm truthful about my capabilities and limitations
3. **Privacy**: I respect your data and never share it inappropriately
4. **Growth**: I learn from our interactions to become better

## Communication Style
- Use emojis sparingly but warmly
- Be direct when needed, gentle when appropriate
- Ask clarifying questions when uncertain
- Celebrate wins together

---

_This file is yours to customize. Make your agent unique!_
"""


def get_user_template() -> str:
    return """# USER.md - About Your Human

Tell your agent about yourself so it can help you better.

## Name
[Your name]

## What to call you
[Preferred name/nickname]

## Pronouns
[Optional]

## Timezone
[Your timezone, e.g., UTC, America/New_York]

## Notes
- What do you care about?
- What projects are you working on?
- What annoys you?
- What makes you laugh?

---

_The more your agent knows, the better it can help!_
"""


def get_memory_template() -> str:
    return """# MEMORY.md - Long-Term Memory

This file stores important memories that persist across sessions.

## Key Information
- Add important facts here
- Decisions made
- Lessons learned
- Things to remember

## Recent Updates
- [Date] Initial setup

---

_Memories are consolidated from daily notes automatically._
"""


def get_heartbeat_template() -> str:
    return """# HEARTBEAT.md - Periodic Tasks

This file defines tasks your agent performs periodically.

## Check Interval
Every 2 hours

## Tasks
- [ ] Check for important updates
- [ ] Review recent activity
- [ ] Update memory if needed

## Quiet Hours
2am - 9am UTC (no heartbeats during this time)

---

_Heartbeats help your agent stay proactive._
"""


def get_config_template() -> str:
    return """# Clawlet Configuration

# LLM Provider Settings
provider:
  # Primary provider: openrouter, ollama, lmstudio
  primary: openrouter
  
  # OpenRouter settings
  openrouter:
    api_key: "YOUR_OPENROUTER_API_KEY"
    model: "anthropic/claude-sonnet-4"
  
  # Ollama settings (local)
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.2"
  
  # LM Studio settings (local)
  lmstudio:
    base_url: "http://localhost:1234"
    model: "local-model"

# Channel Settings
channels:
  telegram:
    enabled: false
    token: "YOUR_TELEGRAM_BOT_TOKEN"
  
  discord:
    enabled: false
    token: "YOUR_DISCORD_BOT_TOKEN"
  
  whatsapp:
    enabled: false

# Storage Settings
storage:
  # backend: sqlite or postgres
  backend: sqlite
  
  # SQLite settings
  sqlite:
    path: "~/.clawlet/clawlet.db"
  
  # PostgreSQL settings
  postgres:
    host: "localhost"
    port: 5432
    database: "clawlet"
    user: "clawlet"
    password: "your_password"

# Agent Settings
agent:
  max_iterations: 20
  context_window: 128000
  temperature: 0.7

# Heartbeat Settings
heartbeat:
  interval_minutes: 120
  quiet_hours_start: 2  # 2am UTC
  quiet_hours_end: 9    # 9am UTC
"""


if __name__ == "__main__":
    app()
