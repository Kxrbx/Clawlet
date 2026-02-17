"""
Clawlet CLI commands.
"""

import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import Optional
import getpass

import typer
from rich.console import Console
from rich.text import Text
from rich.table import Table
from loguru import logger

from clawlet import __version__

# Sakura color scheme
SAKURA_PINK = "#FF69B4"
SAKURA_LIGHT = "#FFB7C5"

app = typer.Typer(
    name="clawlet",
    help="🌸 Clawlet - A lightweight AI agent framework",
    no_args_is_help=False,
)

console = Console()


from clawlet.config import get_default_config_path


def get_workspace_path() -> Path:
    """Get the default workspace path."""
    return Path.home() / ".clawlet"


def print_sakura_banner():
    """Print ASCII art banner."""
    console.print("""
[bold magenta]     *  . 　　 　　　✦ 　　 　 ‍ ‍ ‍ ‍ 　. 　　　　 　　　[/bold magenta]
[bold cyan]
  _____ _          __          ___      ______ _______ 
 / ____| |        /\\ \\        / / |    |  ____|__   __|
| |    | |       /  \\ \\  /\\  / /| |    | |__     | |   
| |    | |      / /\\ \\ \\/  \\/ / | |    |  __|    | |   
| |____| |____ / ____ \\  /\\  /  | |____| |____   | |   
 \\_____|______/_/    \\_\\/  \\/   |______|______|  |_|   
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
    print_command("models", "Manage AI models", "clawlet models")
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
    from clawlet.providers.openrouter import OpenRouterProvider
    from clawlet.config import load_config
    import os
    
    # Load identity
    identity_loader = IdentityLoader(workspace)
    identity = identity_loader.load_all()
    
    # Create message bus
    bus = MessageBus()
    
    # Load configuration first (needed for both provider and channels)
    config = load_config(workspace)
    
    # Get API key from config or environment variable
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    config_model = None
    if config.provider.openrouter:
        if not api_key:
            api_key = config.provider.openrouter.api_key
        config_model = config.provider.openrouter.model
    
    # Use model from CLI arg, then config, then provider default
    effective_model = model or config_model
    
    # Create provider with the configured model
    provider = OpenRouterProvider(api_key=api_key, default_model=effective_model)
    
    # DEBUG: Check Telegram configuration
    telegram_cfg = config.channels.get("telegram")
    
    # Handle both raw dict and Pydantic model formats
    if isinstance(telegram_cfg, dict):
        telegram_enabled = telegram_cfg.get("enabled", False)
        telegram_token = telegram_cfg.get("token", "")
    else:
        # Pydantic model
        telegram_enabled = getattr(telegram_cfg, 'enabled', False)
        telegram_token = getattr(telegram_cfg, 'token', '')
    
    logger.debug(f"Telegram config: enabled={telegram_enabled}")
    
    # Initialize and start Telegram channel if enabled
    if telegram_enabled and telegram_token:
        from clawlet.channels.telegram import TelegramChannel
        logger.info("Initializing Telegram channel...")
        telegram_channel = TelegramChannel(bus, {"token": telegram_token})
        await telegram_channel.start()
        logger.info("Telegram channel started")
    elif telegram_enabled and not telegram_token:
        logger.warning("Telegram enabled but token not configured")
    else:
        logger.warning("Telegram channel not enabled in config - messages will not be received!")
    
    # Create agent loop with the configured model
    agent = AgentLoop(
        bus=bus,
        workspace=workspace,
        identity=identity,
        provider=provider,
        model=effective_model,
    )
    
    # Run the agent
    await agent.run()


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
    import signal
    import sys
    import threading
    
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
    frontend_process = None
    
    if dashboard_dir.exists():
        console.print("│")
        console.print(f"│  [dim]Dashboard directory: {dashboard_dir}[/dim]")
        
        # Check for node_modules
        if not (dashboard_dir / "node_modules").exists():
            console.print("│")
            console.print("│  [yellow]! Frontend dependencies not installed[/yellow]")
            console.print(f"│    Run: [{SAKURA_PINK}]cd {dashboard_dir} && npm install[/{SAKURA_PINK}]")
            console.print("│    Starting API server only...")
            no_frontend = True
    else:
        console.print("│")
        console.print("│  [yellow]! Dashboard directory not found[/yellow]")
        no_frontend = True
    
    def cleanup_processes():
        """Clean up subprocesses on exit."""
        if frontend_process and frontend_process.poll() is None:
            console.print("\n[dim]Stopping frontend dev server...[/dim]")
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()
    
    # Start frontend dev server
    if not no_frontend and dashboard_dir.exists():
        console.print("│")
        console.print(f"│  [bold]Starting frontend dev server on port {frontend_port}...[/bold]")
        
        # Try to find npm or npx
        npm_cmd = None
        npx_cmd = None
        
        # Check common Windows npm locations
        username = getpass.getuser()
        npm_paths = [
            "C:\\Program Files\\nodejs\\npm.cmd",
            "C:\\Program Files\\nodejs\\npx.cmd",
            "C:\\Program Files\\nodejs\\npm.exe",
            "C:\\Program Files\\nodejs\\npx.exe",
            f"C:\\Users\\{username}\\AppData\\Roaming\\npm\\npm.cmd",
            f"C:\\Users\\{username}\\AppData\\Roaming\\npm\\npx.cmd",
        ]
        
        # Try using shutil.which first (respects PATH)
        import shutil
        npm_path = shutil.which("npm")
        npx_path = shutil.which("npx")
        
        console.print(f"[dim]npm path: {npm_path}[/dim]")
        console.print(f"[dim]npx path: {npx_path}[/dim]")
        
        if npx_path:
            # Use npx to run the dev server (it will find npm internally)
            npm_cmd = [npx_path, "npm", "run", "dev", "--", "--port", str(frontend_port)]
            console.print(f"[dim]Using npx: {npm_cmd}[/dim]")
        elif npm_path:
            npm_cmd = [npm_path, "run", "dev", "--", "--port", str(frontend_port)]
            console.print(f"[dim]Using npm: {npm_cmd}[/dim]")
        else:
            # Check common paths
            npm_cmd = None
            for path in npm_paths:
                console.print(f"[dim]Checking: {path}[/dim]")
                if os.path.exists(path):
                    npm_cmd = [path, "run", "dev", "--", "--port", str(frontend_port)]
                    console.print(f"[dim]Found at: {path}[/dim]")
                    break
        
        if npm_cmd is None:
            console.print("│  [yellow]! npm/npx not found, skipping frontend[/yellow]")
            console.print("│    Make sure Node.js is installed and in your PATH")
            console.print("│    Download from: https://nodejs.org")
            no_frontend = True
        else:
            try:
                # Start npm/npx dev server
                frontend_process = subprocess.Popen(
                    npm_cmd,
                    cwd=dashboard_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=0  # Unbuffered
                )
                
                # Wait for frontend to be ready (poll for a few seconds)
                console.print("[dim]Waiting for frontend to start...[/dim]")
                max_wait = 15
                started = False
                for i in range(max_wait):
                    time.sleep(1)
                    
                    # Check if process exited
                    if frontend_process.poll() is not None:
                        # Process exited - check for errors
                        output = frontend_process.stdout.read() if frontend_process.stdout else ""
                        console.print(f"│  [red]! Frontend failed to start[/red]")
                        if output:
                            lines = output.strip().split('\n')[-15:]
                            for line in lines:
                                if line.strip():
                                    console.print(f"│  [dim]  {line}[/dim]")
                        no_frontend = True
                        break
                    
                    # Read any available output
                    if frontend_process.stdout:
                        try:
                            output = frontend_process.stdout.readline()
                            if output:
                                console.print(f"│  [dim]npm: {output.strip()}[/dim]")
                                # Check for Local: URL (might have ANSI codes)
                                if "http://localhost:" in output:
                                    started = True
                                    break
                        except:
                            pass
                
                if not started and frontend_process.poll() is None:
                    console.print(f"│  [green]✓ Frontend dev server started (PID: {frontend_process.pid})[/green]")
                    
            except FileNotFoundError:
                console.print("│  [yellow]! npm not found, skipping frontend[/yellow]")
                console.print("│    Make sure Node.js is installed")
                no_frontend = True
            except Exception as e:
                console.print(f"│  [yellow]! Frontend start error: {e}[/yellow]")
                no_frontend = True
    
    print_footer()
    
    # Open browser if requested and frontend is running
    if open_browser and frontend_process and no_frontend == False:
        import webbrowser
        console.print(f"[dim]Opening browser to {frontend_url}...[/dim]")
        # Give frontend a moment to be fully ready
        time.sleep(2)
        webbrowser.open(frontend_url)
        console.print(f"[dim]Browser should be open at {frontend_url}[/dim]")
    elif open_browser:
        console.print("[dim]Frontend not running, skipping browser open[/dim]")
    
    # Start the API server
    console.print()
    console.print(f"[bold green]🌸 Starting API server on port {port}...[/bold green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()
    
    # Diagnostic info
    import sys
    console.print(f"[dim]Python: {sys.executable}[/dim]")
    console.print(f"[dim]Python version: {sys.version.split()[0]}[/dim]")
    
    # Get pip location
    try:
        pip_path = subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                                   capture_output=True, text=True, timeout=10)
        console.print(f"[dim]pip: {pip_path.stdout.strip()}[/dim]")
    except Exception as e:
        console.print(f"[dim]pip check failed: {e}[/dim]")
    
    def signal_handler(sig, frame):
        """Handle Ctrl+C gracefully."""
        cleanup_processes()
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Check which import fails
        try:
            import uvicorn
            console.print("[dim]uvicorn: found[/dim]")
        except ImportError as e:
            console.print(f"[red]uvicorn: NOT FOUND - {e}[/red]")
        
        try:
            import fastapi
            console.print("[dim]fastapi: found[/dim]")
        except ImportError as e:
            console.print(f"[red]fastapi: NOT FOUND - {e}[/red]")
        
        from clawlet.dashboard.api import app
        
        uvicorn.run(app, host="0.0.0.0", port=port)
    except ImportError as e:
        cleanup_processes()
        console.print()
        console.print(f"[red]Error: Dashboard dependencies not installed.[/red]")
        console.print(f"[red]Import error: {e}[/red]")
        console.print()
        console.print("Install with:")
        console.print(f"  [{SAKURA_PINK}]pip install -e '.[dashboard]'[/{SAKURA_PINK}]")
        console.print()
        console.print("Or:")
        console.print(f"  [{SAKURA_PINK}]pip install fastapi uvicorn[/{SAKURA_PINK}]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        cleanup_processes()
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


@app.command()
def models(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    list_models: bool = typer.Option(False, "--list", "-l", help="List all available models"),
    current: bool = typer.Option(False, "--current", "-c", help="Show current model"),
):
    """🌸 Manage AI models for OpenRouter.
    
    Interactive model selection with search and browse capabilities.
    
    Examples:
        clawlet models              # Interactive model selection
        clawlet models --list       # List all available models
        clawlet models --current    # Show current model
    """
    workspace_path = workspace or get_workspace_path()
    config_path = workspace_path / "config.yaml"
    
    # Check if config exists
    if not config_path.exists():
        console.print("[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]")
        raise typer.Exit(1)
    
    # Load config
    try:
        from clawlet.config import Config
        config = Config.from_yaml(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1)
    
    # Get current model
    current_model = None
    api_key = None
    if config.provider.openrouter:
        current_model = config.provider.openrouter.model
        api_key = config.provider.openrouter.api_key
    
    # Also check environment variable for API key
    import os
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    
    # Handle --current flag
    if current:
        print_section("Current Model", "Active model configuration")
        console.print("│")
        if current_model:
            console.print(f"│  [bold]Model:[/bold] [{SAKURA_PINK}]{current_model}[/{SAKURA_PINK}]")
        else:
            console.print("│  [yellow]No model configured[/yellow]")
        print_footer()
        return
    
    # Handle --list flag
    if list_models:
        asyncio.run(_list_models(api_key))
        return
    
    # Interactive model selection
    try:
        new_model = asyncio.run(_select_model_interactive(api_key, current_model))
        
        if new_model and new_model != current_model:
            # Update config
            if config.provider.openrouter:
                config.provider.openrouter.model = new_model
            else:
                from clawlet.config import OpenRouterConfig, ProviderConfig
                config.provider = ProviderConfig(
                    primary="openrouter",
                    openrouter=OpenRouterConfig(api_key=api_key or "YOUR_OPENROUTER_API_KEY", model=new_model)
                )
            
            # Save config
            config.to_yaml(config_path)
            
            console.print()
            console.print(f"[green]✓ Model updated to:[/green] [{SAKURA_PINK}]{new_model}[/{SAKURA_PINK}]")
            console.print(f"[dim]Config saved to: {config_path}[/dim]")
        elif new_model == current_model:
            console.print()
            console.print("[dim]Model unchanged.[/dim]")
        else:
            console.print()
            console.print("[yellow]Model selection cancelled.[/yellow]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
    except ImportError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Try running 'pip install questionary' first.[/yellow]")
        raise typer.Exit(1)


async def _list_models(api_key: str = None):
    """List all available models from OpenRouter."""
    print_section("Available Models", "Fetching models from OpenRouter...")
    console.print("│")
    
    try:
        from clawlet.providers.openrouter import OpenRouterProvider
        from rich.progress import Progress, SpinnerColumn, TextColumn
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Fetching models...", total=100)
            
            if api_key:
                provider = OpenRouterProvider(api_key=api_key)
                models = await provider.list_models()
            else:
                # Try without API key (may fail)
                console.print("│  [yellow]! No API key configured, using cached/default models[/yellow]")
                from clawlet.cli.onboard import DEFAULT_OPENROUTER_MODELS
                models = [{"id": m, "name": m} for m in DEFAULT_OPENROUTER_MODELS]
            
            progress.update(task, completed=100, description="Done!")
        
        if not models:
            console.print("│  [red]✗ No models found[/red]")
            print_footer()
            return
        
        # Create table for models
        table = Table(show_header=True, header_style=f"bold {SAKURA_PINK}", box=None)
        table.add_column("Model ID", style=SAKURA_LIGHT)
        table.add_column("Name", style="dim")
        
        # Show top 20 models
        for model in models[:20]:
            model_id = model.get("id", "Unknown")
            model_name = model.get("name", model.get("id", "").split("/")[-1])
            # Truncate long names
            if len(model_name) > 40:
                model_name = model_name[:37] + "..."
            table.add_row(model_id, model_name)
        
        console.print("│")
        console.print(f"│  [green]✓[/green] Found {len(models)} models (showing top 20)")
        console.print("│")
        
        # Print table inside the box
        for line in table.to_string().split("\n"):
            console.print(f"│  {line}")
        
        if len(models) > 20:
            console.print("│")
            console.print(f"│  [dim]... and {len(models) - 20} more models[/dim]")
            console.print("│")
            console.print(f"│  [dim]Use 'clawlet models' to search and select interactively[/dim]")
        
        print_footer()
        
    except Exception as e:
        console.print(f"│  [red]✗ Error fetching models: {e}[/red]")
        print_footer()


async def _select_model_interactive(api_key: str = None, current_model: str = None) -> str:
    """Interactive model selection with search and browse."""
    from clawlet.cli.onboard import (
        _select_openrouter_model,
        _search_models,
        _show_all_models,
        _use_default_models,
        DEFAULT_OPENROUTER_MODELS,
        CUSTOM_STYLE,
    )
    from rich.progress import Progress, SpinnerColumn, TextColumn
    import questionary
    
    print_section("Model Selection", "Choose your AI model")
    console.print("│")
    
    # Show current model
    if current_model:
        console.print(f"│  [bold]Current model:[/bold] [{SAKURA_PINK}]{current_model}[/{SAKURA_PINK}]")
        console.print("│")
    
    # Try to fetch models
    models = []
    model_ids = []
    
    try:
        from clawlet.providers.openrouter import OpenRouterProvider
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Fetching models from OpenRouter...", total=100)
            
            if api_key:
                provider = OpenRouterProvider(api_key=api_key)
                models = await provider.list_models()
                model_ids = [m.get("id", "Unknown") for m in models if m.get("id")]
            
            progress.update(task, completed=100, description="Done!")
        
        if models:
            console.print(f"│  [green]✓[/green] Found {len(models)} models")
    except Exception as e:
        logger.debug(f"Could not fetch models: {e}")
        console.print("│  [yellow]! Could not fetch models from API[/yellow]")
    
    console.print("│")
    
    # Build choices
    if model_ids:
        # Show popular models
        popular_patterns = [
            "anthropic/claude",
            "openai/gpt-4",
            "openai/gpt-4o",
            "meta-llama/llama",
            "google/gemini",
            "mistral/mistral",
        ]
        
        popular = []
        for model_id in model_ids:
            if any(pattern in model_id.lower() for pattern in popular_patterns):
                popular.append(model_id)
            if len(popular) >= 5:
                break
        
        choices = ["🔍 Search models...", f"📋 Show all ({len(models)} models)"]
        if popular:
            choices.extend(popular)
    else:
        # Use defaults
        choices = ["🔍 Search models...", "📋 Use default models"]
        choices.extend(DEFAULT_OPENROUTER_MODELS[:5])
    
    choice = await questionary.select(
        "  Select a model:",
        choices=choices,
        style=CUSTOM_STYLE,
    ).ask_async()
    
    if choice is None:
        return None  # Cancelled
    
    if choice.startswith("🔍"):
        return await _search_models(models if models else [{"id": m} for m in DEFAULT_OPENROUTER_MODELS], 
                                     model_ids if model_ids else DEFAULT_OPENROUTER_MODELS)
    elif choice.startswith("📋"):
        if model_ids:
            return await _show_all_models(models, model_ids)
        else:
            return await _use_default_models()
    elif choice in (model_ids if model_ids else DEFAULT_OPENROUTER_MODELS):
        return choice
    else:
        # Default to first available
        return (model_ids[0] if model_ids else DEFAULT_OPENROUTER_MODELS[0])


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
  context_window: 20
  temperature: 0.7

# Heartbeat Settings
heartbeat:
  interval_minutes: 120
  quiet_hours_start: 2  # 2am UTC
  quiet_hours_end: 9    # 9am UTC

# Multi-Agent Routing (optional)
routing:
  enabled: false
  default_agent: "default"
  routes: []
"""


# ============================================================================
# Workspace Management Commands
# ============================================================================

workspace_app = typer.Typer(
    name="workspace",
    help="Manage multiple agent workspaces",
)

app.add_typer(workspace_app, name="workspace")


@workspace_app.command("list")
def workspace_list():
    """List all workspaces."""
    from clawlet.agent.workspace import WorkspaceManager
    
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
            config_icon = "[green]â\u201c\u201d[/green]" if ws.has_config else "[red]â\u201c\u0153[/red]"
            identity_icon = "[green]â\u201c\u201d[/green]" if ws.has_identity else "[red]â\u201c\u0153[/red]"
            
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
            console.print(f"[green]â\u201c\u201d Multi-agent routing enabled[/green]")
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
    from clawlet.agent.workspace import WorkspaceManager
    
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
        
        console.print(f"¦  [green]â\u201c\u201d[/green] Created workspace at [{SAKURA_PINK}]{workspace.path}[/{SAKURA_PINK}]")
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
        console.print(f"¦  [red]â\u201c\u0153 Error creating workspace: {e}[/red]")
        print_footer()
        raise typer.Exit(1)


@workspace_app.command("delete")
def workspace_delete(
    name: str = typer.Argument(..., help="Workspace name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a workspace."""
    from clawlet.agent.workspace import WorkspaceManager
    
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
        console.print(f"¦  [green]â\u201c\u201d[/green] Workspace '{name}' deleted")
        print_footer()
    else:
        console.print(f"¦  [red]â\u201c\u0153 Failed to delete workspace[/red]")
        print_footer()
        raise typer.Exit(1)


@workspace_app.command("show")
def workspace_show(
    name: str = typer.Argument(..., help="Workspace name"),
):
    """Show workspace details."""
    from clawlet.agent.workspace import WorkspaceManager
    
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
            console.print(f"  [green]â\u201c\u201d[/green] {filename} [dim]({size} bytes)[/dim]")
        else:
            console.print(f"  [red]â\u201c\u0153[/red] {filename} [dim](missing)[/dim]")


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


# ============================================================================
# Routing Commands
# ============================================================================

@app.command("routing")
def routing_cmd(
    list_routes: bool = typer.Option(False, "--list", "-l", help="List routing rules"),
    enable: bool = typer.Option(False, "--enable", help="Enable routing"),
    disable: bool = typer.Option(False, "--disable", help="Disable routing"),
    add_route: bool = typer.Option(False, "--add", help="Add a route interactively"),
):
    """Manage multi-agent routing configuration."""
    from clawlet.config import load_config
    
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
        console.print("[green]â\u201c\u201d Multi-agent routing enabled[/green]")
        return
    
    if disable:
        config.routing.enabled = False
        config.to_yaml(config_path)
        console.print("[green]â\u201c\u201d Multi-agent routing disabled[/green]")
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


if __name__ == "__main__":
    app()
