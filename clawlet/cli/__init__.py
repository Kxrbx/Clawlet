"""
Clawlet CLI commands.
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.text import Text
from rich.table import Table

from clawlet import __version__

# Sakura color scheme
SAKURA_PINK = "#FF69B4"
SAKURA_LIGHT = "#FFB7C5"

app = typer.Typer(
    name="clawlet",
    help="🌸 Clawlet - A lightweight AI agent framework",
    no_args_is_help=True,
)

console = Console()


def get_workspace_path() -> Path:
    """Get the default workspace path."""
    return Path.home() / ".clawlet"


def print_sakura_banner():
    """Print ASCII art banner."""
    console.print("""
[bold magenta]     *  . 　　 　　　✦ 　　 　 ‍ ‍ ‍ ‍ 　. 　　　　 　　　[/bold magenta]
[bold cyan]
_______    .---.        ____    .--.      .--.  .---.       .-''-.
   /   __  \\   | ,_|      .'  __ `. |  |_     |  |  | ,_|     .'_ _   \\\\        
  | ,_/  \\__),-./  )     /   '  \\  \\| _( )_   |  |,-./  )    / ( ` )   '`--.  ,---' 
,-./  )      \\  '_ '`)   |___|  /  ||(_ o _)  |  |\\  '_ '`) . (_ o _)  |   |   \\    
\\  '_ '`)     > (_)  )      _.-`   || (_,_) \\ |  | > (_)  ) |  (_,_)___|   :_ _:    
 > (_)  )  __(  .  .-'   .'   _    ||  |/    \\|  |(  .  .-' '  \\   .---.   (_I_)    
(  .  .-'_/  )`-'`-'|___ |  _( )_  ||  '  /\\  `  | `-'`-'|___\\  `-'    /  (_(=)_)   
 `-'`-'     /  |        \\\\ (_ o _) /|    /  \\    |  |        \\\\       /    (_I_)    
   `._____.'   `--------` '.(_,_).' `---'    `---`  `--------` `'-..-'     '---'    
[/bold cyan]
[bold magenta]🌸 A lightweight AI agent framework with identity awareness[/bold magenta]
""")


def print_section(title: str, subtitle: str = None):
    """Print a section header with sakura styling."""
    console.print()
    text = Text()
    text.append("┌─ ", style=f"bold {SAKURA_PINK}")
    text.append(title, style=f"bold {SAKURA_LIGHT}")
    console.print(text)
    
    if subtitle:
        console.print(f"│  [dim]{subtitle}[/dim]")


def print_command(name: str, description: str, shortcut: str = None):
    """Print a command in menu style."""
    if shortcut:
        console.print(f"│  [bold {SAKURA_PINK}]{name:15}[/bold {SAKURA_PINK}] {description} [dim]({shortcut})[/dim]")
    else:
        console.print(f"│  [bold {SAKURA_PINK}]{name:15}[/bold {SAKURA_PINK}] {description}")


def print_footer():
    """Print footer line."""
    console.print("│")
    console.print(f"└─ {'─' * 50}")


def print_main_menu():
    """Print the main menu when clawlet is invoked without args."""
    print_sakura_banner()
    
    print_section("Commands", "What would you like to do?")
    
    print_command("onboard", "Interactive setup wizard (recommended)", "clawlet onboard")
    print_command("init", "Quick workspace initialization", "clawlet init")
    print_command("agent", "Start your AI agent", "clawlet agent")
    print_command("dashboard", "Launch web dashboard", "clawlet dashboard")
    print_command("status", "Check workspace status", "clawlet status")
    print_command("health", "Run health checks", "clawlet health")
    print_command("validate", "Validate configuration", "clawlet validate")
    print_command("config", "View/edit configuration", "clawlet config")
    
    print_footer()
    
    console.print()
    console.print(f"[dim]🌸 Run 'clawlet <command> --help' for more info[/dim]")
    console.print(f"[dim]🌸 Version: {__version__} | https://github.com/Kxrbx/Clawlet[/dim]")
    console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
):
    """🌸 Clawlet - A lightweight AI agent framework with identity awareness."""
    if version:
        console.print(f"[magenta]🌸 clawlet version {__version__}[/magenta]")
        raise typer.Exit()
    
    # If no command provided, show custom menu
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
    """🌸 Quick workspace initialization.
    
    For guided setup, use 'clawlet onboard' instead.
    """
    workspace_path = workspace or get_workspace_path()
    
    # If workspace doesn't exist, suggest onboard
    if not workspace_path.exists():
        print_section("Quick Setup", "Creating workspace with defaults")
        console.print("│  [dim]💡 For guided setup, use: clawlet onboard[/dim]")
    else:
        print_section("Quick Setup", f"Updating {workspace_path}")
    
    console.print("│")
    
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
            console.print(f"│  [yellow]→[/yellow] {filename} [dim](exists, skipped)[/dim]")
        else:
            file_path.write_text(content)
            console.print(f"│  [green]✓[/green] {filename}")
    
    # Create config file
    config_path = workspace_path / "config.yaml"
    if not config_path.exists() or force:
        config_path.write_text(get_config_template())
        console.print(f"│  [green]✓[/green] config.yaml")
    
    print_footer()
    
    console.print()
    console.print(f"[bold green]✓ Workspace ready![/bold green]")
    console.print(f"  Location: [{SAKURA_PINK}]{workspace_path}[/{SAKURA_PINK}]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Edit [{SAKURA_PINK}]config.yaml[/{SAKURA_PINK}] to add API keys")
    console.print(f"  2. Run [{SAKURA_PINK}]clawlet agent[/{SAKURA_PINK}] to start")
    console.print()


@app.command()
def onboard():
    """🌸 Interactive onboarding with guided setup (recommended for first-time users)."""
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
    """🌸 Start the Clawlet agent."""
    workspace_path = workspace or get_workspace_path()
    
    if not workspace_path.exists():
        console.print("[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]")
        raise typer.Exit(1)
    
    print_sakura_banner()
    console.print(f"\n[{SAKURA_LIGHT}]Starting agent with {channel} channel...[/{SAKURA_LIGHT}]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    
    try:
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
    frontend_port: int = typer.Option(5173, "--frontend-port", "-f", help="Frontend dev server port"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser automatically"),
):
    """Start the Clawlet dashboard.
    
    Starts both the API server and shows the dashboard URL.
    The React frontend needs to be started separately with: cd dashboard && npm run dev
    """
    workspace_path = workspace or get_workspace_path()
    
    api_url = f"http://localhost:{port}"
    frontend_url = f"http://localhost:{frontend_port}"
    
    print_section("Clawlet Dashboard", "Web UI for your AI agent")
    console.print("│")
    console.print(f"│  [bold]URLs:[/bold]")
    console.print(f"│    API:      [cyan][link={api_url}]{api_url}[/link][/cyan]")
    console.print(f"│    Frontend: [cyan][link={frontend_url}]{frontend_url}[/link][/cyan]")
    console.print(f"│    Docs:     [cyan][link={api_url}/docs]{api_url}/docs[/link][/cyan]")
    
    # Check if frontend is built
    dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"
    if dashboard_dir.exists():
        console.print("│")
        console.print(f"│  [dim]Dashboard directory: {dashboard_dir}[/dim]")
        
        # Check for node_modules
        if not (dashboard_dir / "node_modules").exists():
            console.print("│")
            console.print("│  [yellow]! Frontend not installed[/yellow]")
            console.print(f"│    Run: [{SAKURA_PINK}]cd {dashboard_dir} && npm install[/{SAKURA_PINK}]")
    else:
        console.print("│")
        console.print("│  [yellow]! Dashboard directory not found[/yellow]")
    
    console.print("│")
    console.print("│  [bold]To start the frontend (new terminal):[/bold]")
    console.print(f"│    [{SAKURA_PINK}]cd dashboard && npm run dev[/{SAKURA_PINK}]")
    
    print_footer()
    
    # Open browser if requested
    if open_browser:
        import webbrowser
        console.print("[dim]Opening browser...[/dim]")
        webbrowser.open(frontend_url)
    
    # Start the API server
    console.print()
    console.print(f"[bold green]🌸 Starting API server on port {port}...[/bold green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()
    
    try:
        import uvicorn
        from clawlet.dashboard.api import app
        
        uvicorn.run(app, host="0.0.0.0", port=port)
    except ImportError:
        console.print("[red]Error: Dashboard dependencies not installed.[/red]")
        console.print()
        console.print("Install with:")
        console.print(f"  [{SAKURA_PINK}]pip install -e '.[dashboard]'[/{SAKURA_PINK}]")
        console.print()
        console.print("Or:")
        console.print(f"  [{SAKURA_PINK}]pip install fastapi uvicorn[/{SAKURA_PINK}]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")


@app.command()
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


@app.command()
def health():
    """🌸 Run health checks on all components."""
    print_section("Health Checks", "Checking system components")
    
    import asyncio
    from clawlet.health import quick_health_check
    
    async def run_checks():
        result = await quick_health_check()
        return result
    
    result = asyncio.run(run_checks())
    
    # Display results
    for check in result.get("checks", []):
        status = check["status"]
        if status == "healthy":
            console.print(f"│  [green]✓[/green] {check['name']}: {check['message']}")
        elif status == "degraded":
            console.print(f"│  [yellow]![/yellow] {check['name']}: {check['message']}")
        else:
            console.print(f"│  [red]✗[/red] {check['name']}: {check['message']}")
    
    print_footer()
    
    # Overall status
    overall = result.get("status", "unknown")
    console.print()
    if overall == "healthy":
        console.print("[green]✓ All systems operational[/green]")
    elif overall == "degraded":
        console.print("[yellow]! Some systems degraded[/yellow]")
    else:
        console.print("[red]✗ Some systems unhealthy[/red]")
    console.print()


@app.command()
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
        from clawlet.config import Config
        
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
        f"🌸 [bold {SAKURA_PINK}]Clawlet Health Check[/bold {SAKURA_PINK}]"
    ))
    
    import asyncio
    from clawlet.health import quick_health_check
    
    async def run_checks():
        result = await quick_health_check()
        return result
    
    result = asyncio.run(run_checks())
    
    # Display results
    table = Table(title="Health Check Results")
    table.add_column("Check", style=f"{SAKURA_PINK}")
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
    """🌸 Validate configuration file."""
    workspace_path = workspace or get_workspace_path()
    config_path = workspace_path / "config.yaml"
    
    console.print(Panel.fit(
        f"🌸 [bold {SAKURA_PINK}]Validating Configuration[/bold {SAKURA_PINK}]"
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
        table = Table(title=f"🌸 Configuration Summary")
        table.add_column("Setting", style=f"{SAKURA_PINK}")
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
    """🌸 Show or manage configuration."""
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
            console.print(f"[{SAKURA_PINK}]{key}[/{SAKURA_PINK}]: {value}")
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
