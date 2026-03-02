"""
Clawlet CLI commands.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional
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

if TYPE_CHECKING:
    from clawlet.agent.loop import AgentLoop

app = typer.Typer(
    name="clawlet",
    help="🌸 Clawlet - A lightweight AI agent framework",
    no_args_is_help=False,
)
benchmark_app = typer.Typer(help="Performance and regression benchmark commands")
plugin_app = typer.Typer(help="Plugin SDK v2 commands")
recovery_app = typer.Typer(help="Interrupted-run recovery commands")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(plugin_app, name="plugin")
app.add_typer(recovery_app, name="recovery")

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


def _filter_breach_lines(
    breach_lines: list[str],
    breach_category: Optional[str],
) -> tuple[list[str], Optional[str]]:
    category = (breach_category or "").strip().lower()
    if not category:
        return breach_lines, None
    valid_categories = {"local", "corpus", "lane", "context", "coding", "comparison", "other"}
    if category not in valid_categories:
        return breach_lines, (
            "Invalid --breach-category. Use one of: "
            "local, corpus, lane, context, coding, comparison, other"
        )
    filtered = [item for item in breach_lines if item.lower().startswith(f"{category}:")]
    return filtered, None


def print_main_menu():
    """Print the main menu when clawlet is invoked without args."""
    print_sakura_banner()
    
    print_section("Commands", "What would you like to do?")
    
    print_command("onboard", "Interactive setup wizard (recommended)", "clawlet onboard")
    print_command("init", "Quick workspace initialization", "clawlet init")
    print_command("agent", "Start your AI agent", "clawlet agent")
    print_command("models", "Manage AI models", "clawlet models")
    print_command("dashboard", "Launch web dashboard", "clawlet dashboard")
    print_command("benchmark", "Run performance regression suite", "clawlet benchmark run")
    print_command("replay", "Inspect deterministic run events", "clawlet replay <run_id>")
    print_command("plugin", "Manage plugin SDK extensions", "clawlet plugin init")
    print_command("recovery", "Inspect and recover interrupted runs", "clawlet recovery list")
    print_command("status", "Check workspace status", "clawlet status")
    print_command("health", "Run health checks", "clawlet health")
    print_command("validate", "Validate configuration", "clawlet validate")
    print_command("config", "View/edit configuration", "clawlet config")
    print_command("migrate-config", "Analyze/autofix legacy config keys", "clawlet migrate-config")
    print_command("migration-matrix", "Scan migration readiness across workspaces", "clawlet migration-matrix")
    print_command("release-readiness", "Run consolidated release readiness checks", "clawlet release-readiness")
    
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
    log_file: Optional[Path] = typer.Option(None, "--log-file", help="File to write logs to"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"),
):
    """🌸 Start the Clawlet agent."""
    workspace_path = workspace or get_workspace_path()
    
    if not workspace_path.exists():
        console.print("[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]")
        raise typer.Exit(1)
    
    # Configure logging to file if requested
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_file),
            rotation="10 MB",
            retention="7 days",
            level=log_level.upper(),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        )
        logger.info(f"Logging to file: {log_file}")
    
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


@app.command()
def chat(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
):
    """🌸 Start a local interactive chat session in the terminal."""
    workspace_path = workspace or get_workspace_path()
    if not workspace_path.exists():
        console.print("[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]")
        raise typer.Exit(1)
    try:
        asyncio.run(run_chat(workspace_path, model))
    except KeyboardInterrupt:
        console.print("\n[yellow]Chat stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def logs(
    log_file: Path = typer.Option(Path.home() / ".clawlet" / "clawlet.log", "--log-file", "-f", help="Log file to read"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to display"),
    follow: bool = typer.Option(False, "--follow", help="Follow log output (tail -f)"),
):
    """🌸 Tail the Clawlet agent logs."""
    if not log_file.exists():
        console.print(f"[yellow]Log file not found: {log_file}[/yellow]")
        console.print("Start the agent with --log-file to enable file logging.")
        raise typer.Exit(1)
    
    try:
        if follow:
            import subprocess
            console.print(f"[dim]Following {log_file} (Ctrl+C to stop)...[/dim]")
            subprocess.run(["tail", "-f", str(log_file)])
        else:
            with open(log_file) as f:
                all_lines = f.readlines()
                start = max(0, len(all_lines) - lines)
                for line in all_lines[start:]:
                    console.print(line.rstrip())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped following logs.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error reading log file: {e}[/red]")
        raise typer.Exit(1)


def _create_provider(config, model: Optional[str]):
    """Create provider from config primary setting."""
    import os
    primary = config.provider.primary
    effective_model = model
    api_key = ""

    if primary == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            api_key = config.provider.openrouter.api_key if config.provider.openrouter else ""
        effective_model = model or (config.provider.openrouter.model if config.provider.openrouter else None)
        from clawlet.providers.openrouter import OpenRouterProvider
        return OpenRouterProvider(api_key=api_key, default_model=effective_model), effective_model
    if primary == "ollama":
        effective_model = model or (config.provider.ollama.model if config.provider.ollama else None)
        from clawlet.providers.ollama import OllamaProvider
        return OllamaProvider(base_url=config.provider.ollama.base_url, default_model=effective_model), effective_model
    if primary == "lmstudio":
        effective_model = model or (config.provider.lmstudio.model if config.provider.lmstudio else None)
        from clawlet.providers.lmstudio import LMStudioProvider
        return LMStudioProvider(base_url=config.provider.lmstudio.base_url, default_model=effective_model), effective_model
    if primary == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "") or (config.provider.openai.api_key if config.provider.openai else "")
        effective_model = model or (config.provider.openai.model if config.provider.openai else None)
        from clawlet.providers.openai import OpenAIProvider
        return OpenAIProvider(api_key=api_key, default_model=effective_model), effective_model
    if primary == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or (config.provider.anthropic.api_key if config.provider.anthropic else "")
        effective_model = model or (config.provider.anthropic.model if config.provider.anthropic else None)
        from clawlet.providers.anthropic import AnthropicProvider
        return AnthropicProvider(api_key=api_key, default_model=effective_model), effective_model

    # Fallback provider
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key and config.provider.openrouter:
        api_key = config.provider.openrouter.api_key
    effective_model = model or (config.provider.openrouter.model if config.provider.openrouter else None)
    from clawlet.providers.openrouter import OpenRouterProvider
    return OpenRouterProvider(api_key=api_key, default_model=effective_model), effective_model


async def run_agent(workspace: Path, model: Optional[str], channel: str):
    """Run the agent loop with explicit channel routing."""
    from clawlet.agent.loop import AgentLoop
    from clawlet.agent.identity import IdentityLoader
    from clawlet.bus.queue import MessageBus
    from clawlet.config import load_config
    from loguru import logger
    
    # Load identity
    identity_loader = IdentityLoader(workspace)
    identity = identity_loader.load_all()
    
    # Create message bus
    bus = MessageBus()
    
    # Load configuration first (needed for both provider and channels)
    config = load_config(workspace)
    
    provider, effective_model = _create_provider(config, model)
    
    # Create tool registry first (needed for agent)
    from clawlet.tools import create_default_tool_registry
    tools = create_default_tool_registry(allowed_dir=str(workspace), config=config)
    logger.info(f"Created tool registry with {len(tools.all_tools())} tools")
    
    # Create agent loop first (needed for channel initialization)
    agent = AgentLoop(
        bus=bus,
        workspace=workspace,
        identity=identity,
        provider=provider,
        model=effective_model,
        tools=tools,
        max_iterations=config.agent.max_iterations,
        max_tool_calls_per_message=config.agent.max_tool_calls_per_message,
        storage_config=config.storage,
        runtime_config=config.runtime,
    )
    
    runtime_channel = None
    if channel == "telegram":
        telegram_cfg = config.channels.get("telegram")
        token = telegram_cfg.get("token", "") if isinstance(telegram_cfg, dict) else getattr(telegram_cfg, "token", "")
        enabled = telegram_cfg.get("enabled", False) if isinstance(telegram_cfg, dict) else getattr(telegram_cfg, "enabled", False)
        if not enabled:
            raise ValueError("Telegram channel is disabled in config")
        if not token:
            raise ValueError("Telegram token is missing in config")
        from clawlet.channels.telegram import TelegramChannel
        runtime_channel = TelegramChannel(bus, {"token": token}, agent)
        await runtime_channel.start()
    elif channel == "discord":
        discord_cfg = config.channels.get("discord")
        token = discord_cfg.get("token", "") if isinstance(discord_cfg, dict) else getattr(discord_cfg, "token", "")
        enabled = discord_cfg.get("enabled", False) if isinstance(discord_cfg, dict) else getattr(discord_cfg, "enabled", False)
        if not enabled:
            raise ValueError("Discord channel is disabled in config")
        if not token:
            raise ValueError("Discord token is missing in config")
        from clawlet.channels.discord import DiscordChannel
        runtime_channel = DiscordChannel(bus, {"token": token}, agent)
        await runtime_channel.start()
    else:
        raise ValueError(f"Unsupported channel '{channel}'. Supported: telegram, discord")
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown_agent(agent, runtime_channel, s)))
    
    # Run the agent
    await agent.run()


async def shutdown_agent(agent: AgentLoop, telegram_channel, signum):
    """Shutdown agent gracefully on signal."""
    logger.info(f"Received signal {signum}, shutting down...")
    
    # Stop Telegram channel first to prevent background tasks from hanging
    if telegram_channel is not None:
        try:
            logger.info("Stopping Telegram channel...")
            await telegram_channel.stop()
            logger.info("Telegram channel stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram channel: {e}")
    
    agent.stop()
    await agent.close()
    logger.info("Agent shutdown complete")


async def run_chat(workspace: Path, model: Optional[str]) -> None:
    """Run a local terminal chat loop using the same agent core."""
    from clawlet.agent.loop import AgentLoop
    from clawlet.agent.identity import IdentityLoader
    from clawlet.bus.queue import MessageBus, InboundMessage
    from clawlet.config import load_config
    from clawlet.tools import create_default_tool_registry

    identity = IdentityLoader(workspace).load_all()
    bus = MessageBus()
    config = load_config(workspace)
    provider, effective_model = _create_provider(config, model)
    tools = create_default_tool_registry(allowed_dir=str(workspace), config=config)

    agent = AgentLoop(
        bus=bus,
        workspace=workspace,
        identity=identity,
        provider=provider,
        model=effective_model,
        tools=tools,
        max_iterations=config.agent.max_iterations,
        max_tool_calls_per_message=config.agent.max_tool_calls_per_message,
        storage_config=config.storage,
        runtime_config=config.runtime,
    )

    agent_task = asyncio.create_task(agent.run())
    console.print("[dim]Local chat mode. Type 'exit' to quit.[/dim]")
    try:
        while True:
            user_text = await asyncio.to_thread(input, "\nYou> ")
            if user_text.strip().lower() in {"exit", "quit"}:
                break
            await bus.publish_inbound(InboundMessage(channel="cli", chat_id="local", content=user_text))
            while True:
                out = await bus.consume_outbound()
                if out.channel == "cli" and out.chat_id == "local":
                    console.print(f"Clawlet> {out.content}")
                    break
    finally:
        agent.stop()
        await agent.close()
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


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
        
        if npx_path:
            # Use npx to run the dev server (it will find npm internally)
            npm_cmd = [npx_path, "npm", "run", "dev", "--", "--port", str(frontend_port)]
        elif npm_path:
            npm_cmd = [npm_path, "run", "dev", "--", "--port", str(frontend_port)]
        else:
            # Check common paths
            for path in npm_paths:
                if os.path.exists(path):
                    npm_cmd = [path, "run", "dev", "--", "--port", str(frontend_port)]
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
                    bufsize=1
                )
                
                # Give it time to start
                time.sleep(3)
                
                if frontend_process.poll() is not None:
                    # Process already exited - check for errors
                    output = frontend_process.stdout.read() if frontend_process.stdout else ""
                    console.print(f"│  [red]! Frontend failed to start[/red]")
                    if output:
                        console.print(f"│  [dim]Output: {output[:200]}[/dim]")
                    no_frontend = True
                else:
                    console.print(f"│  [green]✓ Frontend dev server started (PID: {frontend_process.pid})[/green]")
                    
            except FileNotFoundError:
                console.print("│  [yellow]! npm not found, skipping frontend[/yellow]")
                console.print("│    Make sure Node.js is installed")
                no_frontend = True
            except Exception as e:
                console.print(f"│  [yellow]! Frontend start error: {e}[/yellow]")
                no_frontend = True
    
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
    migration: bool = typer.Option(False, "--migration", help="Run legacy migration compatibility analysis"),
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

        if migration:
            from clawlet.config_migration import analyze_config_migration

            report = analyze_config_migration(config_path)
            console.print("│")
            console.print(f"│  [bold]Migration Analysis:[/bold] {len(report.issues)} issue(s)")
            for issue in report.issues:
                marker = "•"
                if issue.severity == "error":
                    marker = "[red]✗[/red]"
                elif issue.severity == "warning":
                    marker = "[yellow]![/yellow]"
                else:
                    marker = "[cyan]i[/cyan]"
                auto = " [dim](autofixable)[/dim]" if issue.can_autofix else ""
                console.print(
                    f"│    {marker} {issue.severity.upper()} {issue.path}: {issue.message}{auto}"
                )
                console.print(f"│      hint: {issue.hint}")
            if report.has_blockers:
                print_footer()
                raise typer.Exit(2)
        
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


@app.command("migrate-config")
def migrate_config(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    write: bool = typer.Option(False, "--write", help="Apply autofix changes to config.yaml"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create .bak backup when writing"),
):
    """Analyze and optionally autofix legacy config keys."""
    from clawlet.config_migration import analyze_config_migration, apply_config_migration_autofix

    workspace_path = workspace or get_workspace_path()
    config_path = workspace_path / "config.yaml"

    print_section("Config Migration", str(config_path))
    analysis = analyze_config_migration(config_path)
    if analysis.issues:
        console.print(f"│  Detected {len(analysis.issues)} issue(s):")
        for issue in analysis.issues:
            mark = "✗" if issue.severity == "error" else ("!" if issue.severity == "warning" else "i")
            auto = " (autofixable)" if issue.can_autofix else ""
            console.print(f"│   {mark} {issue.severity.upper()} {issue.path}: {issue.message}{auto}")
            console.print(f"│      hint: {issue.hint}")
    else:
        console.print("│  No migration issues detected")

    result = apply_config_migration_autofix(config_path, write=write, create_backup=backup)
    console.print("│")
    mode = "write" if write else "dry-run"
    console.print(f"│  Autofix mode: {mode}")
    console.print(f"│  Changes available: {'yes' if result.changed else 'no'}")
    if result.actions:
        for action in result.actions:
            console.print(f"│   - {action}")
    if write and result.changed and result.backup_path:
        console.print(f"│  Backup: {result.backup_path}")

    print_footer()

    if analysis.has_blockers:
        raise typer.Exit(2)


@app.command("migration-matrix")
def migration_matrix(
    root: Path = typer.Option(Path("."), "--root", help="Root directory containing workspaces"),
    pattern: str = typer.Option("config.yaml", "--pattern", help="Config filename/pattern to scan"),
    max_workspaces: int = typer.Option(200, "--max-workspaces", min=1, max=5000, help="Maximum configs to scan"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON output report path"),
    fail_on_errors: bool = typer.Option(
        False,
        "--fail-on-errors",
        help="Exit non-zero if any scanned workspace has migration blocking errors",
    ),
):
    """Scan many workspaces and report migration compatibility readiness."""
    from clawlet.config_migration_matrix import run_migration_matrix, write_migration_matrix_report

    report = run_migration_matrix(root=root, pattern=pattern, max_workspaces=max_workspaces)
    print_section("Migration Matrix", f"root={root.resolve()}")
    console.print(
        "│  "
        f"scanned={report.scanned} with_issues={report.with_issues} with_errors={report.with_errors}"
    )
    console.print(
        "│  "
        f"issues={report.total_issues} errors={report.total_errors} "
        f"warnings={report.total_warnings} infos={report.total_infos} "
        f"autofixable={report.total_autofixable}"
    )
    if report.results:
        console.print("│")
        top = sorted(report.results, key=lambda r: (r.errors, r.issues), reverse=True)[:20]
        for item in top:
            console.print(
                "│  "
                f"{item.workspace}: issues={item.issues} errors={item.errors} "
                f"warnings={item.warnings} autofixable={item.autofixable}"
            )

    output = report_path or (Path(root).resolve() / "migration-matrix-report.json")
    write_migration_matrix_report(output, report)
    console.print(f"│  Report: {output}")
    print_footer()

    if fail_on_errors and report.with_errors > 0:
        raise typer.Exit(2)


@app.command("release-readiness")
def release_readiness(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Primary workspace directory"),
    local_iterations: int = typer.Option(25, "--local-iterations", min=1, max=500),
    corpus_iterations: int = typer.Option(10, "--corpus-iterations", min=1, max=200),
    baseline_report: Optional[Path] = typer.Option(None, "--baseline-report"),
    target_improvement_pct: float = typer.Option(35.0, "--target-improvement-pct", min=0.0, max=100.0),
    require_comparison: bool = typer.Option(False, "--require-comparison"),
    migration_root: Optional[Path] = typer.Option(None, "--migration-root", help="Root path for migration matrix scan"),
    migration_pattern: str = typer.Option("config.yaml", "--migration-pattern"),
    migration_max_workspaces: int = typer.Option(200, "--migration-max-workspaces", min=1, max=5000),
    check_remote_health: bool = typer.Option(False, "--check-remote-health"),
    breach_category: Optional[str] = typer.Option(
        None,
        "--breach-category",
        help="Filter displayed gate breaches by category: local|corpus|lane|context|coding|comparison|other",
    ),
    max_breaches: int = typer.Option(
        8,
        "--max-breaches",
        min=1,
        max=100,
        help="Maximum number of breach lines to display",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    fail_on_not_ready: bool = typer.Option(True, "--fail-on-not-ready/--no-fail-on-not-ready"),
):
    """Run consolidated release readiness checks across benchmarks/migration/plugins."""
    from clawlet.config import BenchmarksSettings, load_config
    from clawlet.release_readiness import (
        run_release_readiness,
        summarize_gate_breaches,
        write_release_readiness_report,
    )

    workspace_path = workspace or get_workspace_path()
    gates_cfg = BenchmarksSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            gates_cfg = BenchmarksSettings(**(raw.get("benchmarks") or {}))
        except Exception:
            pass

    plugin_dirs = [workspace_path / "plugins"]
    remote_endpoint = ""
    remote_api_key = ""
    remote_timeout_seconds = 60.0
    try:
        import os

        cfg = load_config(workspace_path)
        plugin_dirs = []
        for raw_dir in cfg.plugins.directories:
            p = Path(raw_dir).expanduser()
            if not p.is_absolute():
                p = workspace_path / p
            plugin_dirs.append(p)
        remote_endpoint = str(getattr(cfg.runtime.remote, "endpoint", "") or "")
        remote_timeout_seconds = float(getattr(cfg.runtime.remote, "timeout_seconds", 60.0) or 60.0)
        api_env = str(getattr(cfg.runtime.remote, "api_key_env", "CLAWLET_REMOTE_API_KEY") or "CLAWLET_REMOTE_API_KEY")
        remote_api_key = os.environ.get(api_env, "")
    except Exception:
        pass

    report = run_release_readiness(
        workspace=workspace_path,
        benchmark_gates=gates_cfg.gates,
        local_iterations=local_iterations,
        corpus_iterations=corpus_iterations,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        require_comparison=require_comparison,
        migration_root=migration_root,
        migration_pattern=migration_pattern,
        migration_max_workspaces=migration_max_workspaces,
        plugin_dirs=plugin_dirs,
        check_remote_health=check_remote_health,
        remote_endpoint=remote_endpoint,
        remote_api_key=remote_api_key,
        remote_timeout_seconds=remote_timeout_seconds,
    )

    rg = report.release_gate or {}
    local = rg.get("local_summary") or {}
    lane = report.lane_scheduling or {}
    context = report.context_cache or {}
    coding = report.coding_loop or {}
    gate_breaches = list(report.gate_breaches or [])[:max_breaches]
    if not gate_breaches:
        gate_breaches = summarize_gate_breaches(report, max_items=max_breaches)
    gate_breaches, category_error = _filter_breach_lines(gate_breaches, breach_category)
    if category_error:
        console.print(f"[red]{category_error}[/red]")
        raise typer.Exit(2)
    breach_counts = dict(report.breach_counts or {})

    output = report_path or (workspace_path / "release-readiness-report.json")
    write_release_readiness_report(output, report)

    if json_output:
        payload = report.to_dict()
        payload["display_gate_breaches"] = gate_breaches
        payload["display_max_breaches"] = max_breaches
        payload["display_breach_category"] = (breach_category or "").strip().lower()
        payload["report_path"] = str(output)
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        if fail_on_not_ready and not report.passed:
            raise typer.Exit(2)
        return

    print_section("Release Readiness", str(workspace_path))
    console.print(f"│  passed={'yes' if report.passed else 'no'}")
    console.print(f"│  release_gate={'yes' if report.release_gate_passed else 'no'}")
    console.print(f"│  migration_matrix={'yes' if report.migration_matrix_passed else 'no'}")
    console.print(f"│  plugin_matrix={'yes' if report.plugin_matrix_passed else 'no'}")
    console.print(f"│  lane_scheduling={'yes' if report.lane_scheduling_passed else 'no'}")
    console.print(f"│  context_cache={'yes' if report.context_cache_passed else 'no'}")
    console.print(f"│  coding_loop={'yes' if report.coding_loop_passed else 'no'}")
    console.print(f"│  remote_health={'yes' if report.remote_health_passed else 'no'}")
    if local or lane or context or coding:
        console.print("│  Metrics:")
        if local:
            console.print(
                "│    "
                f"local_p95_ms={float(local.get('p95_ms', 0.0)):.2f} "
                f"local_success={float(local.get('success_rate', 0.0)):.2f}% "
                f"local_determinism={float(local.get('deterministic_replay_pass_rate_pct', 0.0)):.2f}%"
            )
        if lane:
            console.print(
                "│    "
                f"lane_parallel_ms={float(lane.get('parallel_elapsed_ms', 0.0)):.2f} "
                f"lane_speedup={float(lane.get('speedup_ratio', 0.0)):.2f}x"
            )
        if context:
            console.print(
                "│    "
                f"context_warm_ms={float(context.get('warm_ms', 0.0)):.2f} "
                f"context_speedup={float(context.get('speedup_ratio', 0.0)):.2f}x"
            )
        if coding:
            console.print(
                "│    "
                f"coding_success={float(coding.get('success_rate', 0.0)):.2f}% "
                f"coding_p95_total_ms={float(coding.get('p95_total_ms', 0.0)):.2f}"
            )
    if breach_counts:
        compact = ", ".join(f"{k}={v}" for k, v in sorted(breach_counts.items()))
        console.print(f"│  [red]Breach counts:[/red] {compact}")
    if gate_breaches:
        console.print("│  [red]Gate Breaches:[/red]")
        for item in gate_breaches:
            console.print(f"│    - {item}")
    if report.reasons:
        console.print("│  [red]Reasons:[/red]")
        for reason in report.reasons:
            console.print(f"│    - {reason}")

    console.print(f"│  Report: {output}")
    print_footer()

    if fail_on_not_ready and not report.passed:
        raise typer.Exit(2)


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
  max_tool_calls_per_message: 6
  context_window: 20
  temperature: 0.7
  mode: safe
  shell_allow_dangerous: false

# Heartbeat Settings
heartbeat:
  interval_minutes: 120
  quiet_hours_start: 2  # 2am UTC
  quiet_hours_end: 9    # 9am UTC

# Runtime v2 Settings
runtime:
  engine: hybrid_rust
  enable_idempotency_cache: true
  enable_parallel_read_batches: true
  max_parallel_read_tools: 4
  default_tool_timeout_seconds: 30
  default_tool_retries: 1
  outbound_publish_retries: 2
  outbound_publish_backoff_seconds: 0.5
  policy:
    allowed_modes: [read_only, workspace_write]
    require_approval_for: [elevated]
    lanes:
      read_only: "parallel:read_only"
      workspace_write: "serial:workspace_write"
      elevated: "serial:elevated"
  replay:
    enabled: true
    directory: ".runtime"
    retention_days: 30
    redact_tool_outputs: false
    validate_events: true
    validation_mode: "warn"
  remote:
    enabled: false
    endpoint: ""
    timeout_seconds: 60
    api_key_env: "CLAWLET_REMOTE_API_KEY"

# Benchmarks + hard quality gates
benchmarks:
  enabled: true
  gates:
    max_p95_latency_ms: 3000
    min_tool_success_rate_pct: 99.0
    min_deterministic_replay_pass_rate_pct: 98.0
    min_lane_speedup_ratio: 1.20
    max_lane_parallel_elapsed_ms: 1000
    min_context_cache_speedup_ratio: 1.05
    max_context_cache_warm_ms: 1200
    min_coding_loop_success_rate_pct: 99.0
    max_coding_loop_p95_total_ms: 2500

# Plugin SDK v2
plugins:
  auto_load: true
  directories:
    - "~/.clawlet/plugins"
  sdk_version: "2.0.0"
"""


# ── Benchmark and replay commands ─────────────────────────────────────────────

@benchmark_app.command("run")
def benchmark_run(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    iterations: int = typer.Option(25, "--iterations", min=5, max=500, help="Benchmark iterations"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    fail_on_gate: bool = typer.Option(False, "--fail-on-gate", help="Exit non-zero when quality gates fail"),
):
    """Run local performance benchmark and evaluate quality gates."""
    from clawlet.benchmarks import check_gates, run_local_runtime_benchmark, write_report
    from clawlet.config import BenchmarksSettings

    workspace_path = workspace or get_workspace_path()
    gates_cfg = BenchmarksSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            gates_cfg = BenchmarksSettings(**(raw.get("benchmarks") or {}))
        except Exception:
            pass

    print_section("Benchmark", f"Running {iterations} iterations")
    summary = run_local_runtime_benchmark(workspace=workspace_path, iterations=iterations)
    failures = check_gates(summary, gates_cfg.gates)

    console.print(f"│  Samples: {summary.samples}")
    console.print(f"│  p50: {summary.p50_ms:.2f} ms")
    console.print(f"│  p95: {summary.p95_ms:.2f} ms")
    console.print(f"│  p99: {summary.p99_ms:.2f} ms")
    console.print(f"│  Success: {summary.success_rate:.2f}%")
    console.print(
        "│  Determinism: "
        f"{summary.deterministic_replay_pass_rate_pct:.2f}% "
        "(replay signature stability)"
    )

    if failures:
        console.print("│")
        console.print("│  [red]Gate failures:[/red]")
        for failure in failures:
            console.print(f"│    - {failure}")
    else:
        console.print("│  [green]All quality gates passed[/green]")

    output = report_path or (workspace_path / "benchmark-report.json")
    write_report(output, summary, failures)
    console.print(f"│  Report: {output}")
    print_footer()

    if fail_on_gate and failures:
        raise typer.Exit(2)


@benchmark_app.command("equivalence")
def benchmark_equivalence(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    strict_rust: bool = typer.Option(
        False,
        "--strict-rust",
        help="Fail if Rust extension is unavailable",
    ),
):
    """Run Python vs Rust execution equivalence checks."""
    from clawlet.benchmarks import run_engine_equivalence_smokecheck

    workspace_path = workspace or get_workspace_path()
    result = run_engine_equivalence_smokecheck(workspace_path)

    print_section("Benchmark Equivalence", "Python vs Rust execution paths")
    console.print(f"│  Rust available: {'yes' if result.rust_available else 'no'}")
    console.print(f"│  Shell equivalent: {'yes' if result.shell_equivalent else 'no'}")
    console.print(f"│  File equivalent: {'yes' if result.file_equivalent else 'no'}")
    console.print(f"│  Patch equivalent: {'yes' if result.patch_equivalent else 'no'}")
    if result.details:
        console.print("│")
        for detail in result.details:
            console.print(f"│  - {detail}")
    print_footer()

    if strict_rust and not result.rust_available:
        raise typer.Exit(2)
    if not result.passed:
        raise typer.Exit(2)


@benchmark_app.command("remote-health")
def benchmark_remote_health(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Check configured remote worker health endpoint."""
    from clawlet.config import RuntimeSettings
    from clawlet.runtime.remote import RemoteToolExecutor

    workspace_path = workspace or get_workspace_path()
    runtime_cfg = RuntimeSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            runtime_cfg = RuntimeSettings(**(raw.get("runtime") or {}))
        except Exception:
            pass

    remote_cfg = runtime_cfg.remote
    if not remote_cfg.enabled:
        console.print("[yellow]Remote execution is disabled (runtime.remote.enabled=false)[/yellow]")
        raise typer.Exit(1)
    if not remote_cfg.endpoint:
        console.print("[red]Remote execution enabled but endpoint is empty[/red]")
        raise typer.Exit(1)

    import os

    api_key = os.environ.get(remote_cfg.api_key_env, "")
    client = RemoteToolExecutor(
        endpoint=remote_cfg.endpoint,
        api_key=api_key,
        timeout_seconds=remote_cfg.timeout_seconds,
    )
    ok, detail = asyncio.run(client.health())

    print_section("Remote Health", remote_cfg.endpoint)
    console.print(f"│  enabled={str(remote_cfg.enabled).lower()}")
    console.print(f"│  api_key_env={remote_cfg.api_key_env}")
    console.print(f"│  status={'ok' if ok else 'failed'}")
    console.print(f"│  detail={detail}")
    print_footer()

    if not ok:
        raise typer.Exit(2)


@benchmark_app.command("remote-parity")
def benchmark_remote_parity(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Run remote/local execution parity smokecheck."""
    from clawlet.benchmarks import run_remote_parity_smokecheck

    workspace_path = workspace or get_workspace_path()
    ok, errors = run_remote_parity_smokecheck(workspace_path)
    print_section("Remote Parity", str(workspace_path))
    console.print(f"│  passed={'yes' if ok else 'no'}")
    if errors:
        for item in errors:
            console.print(f"│  - {item}")
    print_footer()
    if not ok:
        raise typer.Exit(2)


@benchmark_app.command("lanes")
def benchmark_lanes(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
):
    """Run lane scheduling benchmark (serial vs parallel)."""
    from clawlet.benchmarks import (
        run_lane_contention_benchmark,
        write_lane_contention_report,
    )

    workspace_path = workspace or get_workspace_path()
    report = run_lane_contention_benchmark(workspace_path)

    print_section("Lane Scheduling", str(workspace_path))
    console.print(f"│  passed={'yes' if report.passed else 'no'}")
    console.print(f"│  serial_elapsed_ms={report.serial_elapsed_ms:.1f}")
    console.print(f"│  parallel_elapsed_ms={report.parallel_elapsed_ms:.1f}")
    console.print(f"│  speedup_ratio={report.speedup_ratio:.2f}x")
    if report.details:
        for item in report.details:
            console.print(f"│  - {item}")
    output = report_path or (workspace_path / "benchmark-lanes-report.json")
    write_lane_contention_report(output, report)
    console.print(f"│  report={output}")
    print_footer()

    if not report.passed:
        raise typer.Exit(2)


@benchmark_app.command("context-cache")
def benchmark_context_cache(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
):
    """Run context-engine warm-cache vs cold-cache benchmark."""
    from clawlet.benchmarks import (
        run_context_cache_benchmark,
        write_context_cache_report,
    )

    workspace_path = workspace or get_workspace_path()
    report = run_context_cache_benchmark(workspace_path)

    print_section("Context Cache", str(workspace_path))
    console.print(f"│  passed={'yes' if report.passed else 'no'}")
    console.print(f"│  cold_ms={report.cold_ms:.1f}")
    console.print(f"│  warm_ms={report.warm_ms:.1f}")
    console.print(f"│  speedup_ratio={report.speedup_ratio:.2f}x")
    if report.details:
        for item in report.details:
            console.print(f"│  - {item}")
    output = report_path or (workspace_path / "benchmark-context-cache-report.json")
    write_context_cache_report(output, report)
    console.print(f"│  report={output}")
    print_footer()

    if not report.passed:
        raise typer.Exit(2)


@benchmark_app.command("coding-loop")
def benchmark_coding_loop(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    iterations: int = typer.Option(10, "--iterations", min=1, max=200, help="Benchmark iterations"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
):
    """Run coding-loop benchmark (inspect -> patch -> verify -> summarize)."""
    from clawlet.benchmarks import (
        run_coding_loop_benchmark,
        write_coding_loop_report,
    )

    workspace_path = workspace or get_workspace_path()
    report = run_coding_loop_benchmark(workspace_path, iterations=iterations)

    print_section("Coding Loop", str(workspace_path))
    console.print(f"│  passed={'yes' if report.passed else 'no'}")
    console.print(f"│  iterations={report.iterations}")
    console.print(f"│  success_rate={report.success_rate:.2f}%")
    console.print(f"│  p95_total_ms={report.p95_total_ms:.2f}")
    console.print(
        "│  "
        f"avg_inspect_ms={report.avg_inspect_ms:.2f} "
        f"avg_patch_ms={report.avg_patch_ms:.2f} "
        f"avg_verify_ms={report.avg_verify_ms:.2f} "
        f"avg_summarize_ms={report.avg_summarize_ms:.2f}"
    )
    if report.details:
        for item in report.details:
            console.print(f"│  - {item}")
    output = report_path or (workspace_path / "benchmark-coding-loop-report.json")
    write_coding_loop_report(output, report)
    console.print(f"│  report={output}")
    print_footer()

    if not report.passed:
        raise typer.Exit(2)


@benchmark_app.command("corpus")
def benchmark_corpus(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    iterations: int = typer.Option(10, "--iterations", min=1, max=200, help="Iterations per scenario"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    baseline_report: Optional[Path] = typer.Option(
        None,
        "--baseline-report",
        help="Optional baseline report JSON (OpenClaw or previous Clawlet run)",
    ),
    target_improvement_pct: float = typer.Option(
        35.0,
        "--target-improvement-pct",
        min=0.0,
        max=100.0,
        help="Required p95 improvement percent vs baseline",
    ),
    fail_on_gate: bool = typer.Option(False, "--fail-on-gate", help="Exit non-zero when quality gates fail"),
    fail_on_regression: bool = typer.Option(
        False,
        "--fail-on-regression",
        help="Exit non-zero on baseline regressions or target miss",
    ),
):
    """Run OpenClaw-matched corpus and optional baseline comparison."""
    from clawlet.benchmarks import (
        check_corpus_gates,
        compare_corpus_to_baseline,
        run_openclaw_matched_corpus,
        write_corpus_report,
    )
    from clawlet.config import BenchmarksSettings

    workspace_path = workspace or get_workspace_path()
    gates_cfg = BenchmarksSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            gates_cfg = BenchmarksSettings(**(raw.get("benchmarks") or {}))
        except Exception:
            pass

    print_section("Benchmark Corpus", f"OpenClaw-matched scenarios x {iterations} iteration(s)")
    report = run_openclaw_matched_corpus(workspace=workspace_path, iterations=iterations)
    gate_failures = check_corpus_gates(report, gates_cfg.gates)

    summary = report.summary
    console.print(f"│  Corpus: {report.corpus_id}")
    console.print(f"│  Samples: {int(summary.get('samples', 0))}")
    console.print(f"│  p50: {float(summary.get('p50_ms', 0.0)):.2f} ms")
    console.print(f"│  p95: {float(summary.get('p95_ms', 0.0)):.2f} ms")
    console.print(f"│  p99: {float(summary.get('p99_ms', 0.0)):.2f} ms")
    console.print(f"│  Success: {float(summary.get('success_rate', 0.0)):.2f}%")
    console.print("│")
    for scenario in report.scenarios:
        console.print(
            "│  "
            f"{scenario.scenario_id}: p95={scenario.p95_ms:.2f}ms "
            f"success={scenario.success_rate:.2f}%"
        )

    comparison = None
    if baseline_report is not None:
        comparison = compare_corpus_to_baseline(
            report=report,
            baseline_path=baseline_report,
            target_improvement_pct=target_improvement_pct,
        )
        console.print("│")
        console.print(f"│  Baseline: {comparison.baseline_source}")
        console.print(
            "│  Improvement: "
            f"{comparison.improvement_pct:.2f}% "
            f"(target {comparison.target_improvement_pct:.2f}%)"
        )
        console.print(f"│  Meets target: {'yes' if comparison.meets_target else 'no'}")
        for row in comparison.scenario_comparisons:
            console.print(
                "│    "
                f"{row.scenario_id}: baseline_p95={row.baseline_p95_ms:.2f}ms "
                f"current_p95={row.current_p95_ms:.2f}ms "
                f"delta={row.improvement_pct:.2f}%"
            )
        if comparison.regressions:
            console.print("│  [red]Regressions:[/red]")
            for item in comparison.regressions:
                console.print(f"│    - {item}")

    if gate_failures:
        console.print("│")
        console.print("│  [red]Gate failures:[/red]")
        for failure in gate_failures:
            console.print(f"│    - {failure}")
    else:
        console.print("│")
        console.print("│  [green]All corpus gates passed[/green]")

    output = report_path or (workspace_path / "benchmark-corpus-report.json")
    write_corpus_report(output, report, gate_failures, comparison=comparison)
    console.print(f"│  Report: {output}")
    print_footer()

    if fail_on_gate and gate_failures:
        raise typer.Exit(2)
    if fail_on_regression and comparison is not None and not comparison.meets_target:
        raise typer.Exit(2)


@benchmark_app.command("compare")
def benchmark_compare(
    current_report: Path = typer.Option(..., "--current-report", help="Current corpus report JSON"),
    baseline_report: Path = typer.Option(..., "--baseline-report", help="Baseline corpus report JSON"),
    target_improvement_pct: float = typer.Option(
        35.0,
        "--target-improvement-pct",
        min=0.0,
        max=100.0,
        help="Required p95 improvement percent vs baseline",
    ),
    fail_on_regression: bool = typer.Option(
        True,
        "--fail-on-regression/--no-fail-on-regression",
        help="Exit non-zero on regressions or target miss",
    ),
):
    """Compare two saved OpenClaw-matched corpus reports."""
    from clawlet.benchmarks import compare_corpus_reports

    comparison = compare_corpus_reports(
        current_path=current_report,
        baseline_path=baseline_report,
        target_improvement_pct=target_improvement_pct,
    )

    print_section("Benchmark Compare", "Current vs baseline corpus reports")
    console.print(f"│  Baseline: {comparison.baseline_source}")
    console.print(f"│  Baseline p95: {comparison.baseline_p95_ms:.2f} ms")
    console.print(f"│  Current p95: {comparison.current_p95_ms:.2f} ms")
    console.print(
        "│  Improvement: "
        f"{comparison.improvement_pct:.2f}% "
        f"(target {comparison.target_improvement_pct:.2f}%)"
    )
    console.print(f"│  Meets target: {'yes' if comparison.meets_target else 'no'}")
    for row in comparison.scenario_comparisons:
        console.print(
            "│  "
            f"{row.scenario_id}: baseline_p95={row.baseline_p95_ms:.2f}ms "
            f"current_p95={row.current_p95_ms:.2f}ms "
            f"delta={row.improvement_pct:.2f}%"
        )
    if comparison.regressions:
        console.print("│  [red]Regressions:[/red]")
        for item in comparison.regressions:
            console.print(f"│    - {item}")
    print_footer()

    if fail_on_regression and not comparison.meets_target:
        raise typer.Exit(2)


@benchmark_app.command("release-gate")
def benchmark_release_gate(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    local_iterations: int = typer.Option(
        25,
        "--local-iterations",
        min=1,
        max=500,
        help="Iterations for local runtime benchmark",
    ),
    corpus_iterations: int = typer.Option(
        10,
        "--corpus-iterations",
        min=1,
        max=200,
        help="Iterations per corpus scenario",
    ),
    baseline_report: Optional[Path] = typer.Option(
        None,
        "--baseline-report",
        help="Optional baseline corpus report for superiority comparison",
    ),
    target_improvement_pct: float = typer.Option(
        35.0,
        "--target-improvement-pct",
        min=0.0,
        max=100.0,
        help="Required p95 improvement vs baseline",
    ),
    require_comparison: bool = typer.Option(
        False,
        "--require-comparison",
        help="Fail gate when --baseline-report is not provided",
    ),
    report_path: Optional[Path] = typer.Option(
        None,
        "--report",
        help="Optional JSON report output path",
    ),
    breach_category: Optional[str] = typer.Option(
        None,
        "--breach-category",
        help="Filter displayed gate breaches by category: local|corpus|lane|context|coding|comparison|other",
    ),
    max_breaches: int = typer.Option(
        8,
        "--max-breaches",
        min=1,
        max=100,
        help="Maximum number of breach lines to display",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
    fail_on_gate: bool = typer.Option(
        True,
        "--fail-on-gate/--no-fail-on-gate",
        help="Exit non-zero when any release gate fails",
    ),
):
    """Run consolidated benchmark release gates in one command."""
    from clawlet.benchmarks import run_release_gate, write_release_gate_report
    from clawlet.config import BenchmarksSettings

    workspace_path = workspace or get_workspace_path()
    gates_cfg = BenchmarksSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            gates_cfg = BenchmarksSettings(**(raw.get("benchmarks") or {}))
        except Exception:
            pass

    report = run_release_gate(
        workspace=workspace_path,
        gates=gates_cfg.gates,
        local_iterations=local_iterations,
        corpus_iterations=corpus_iterations,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        require_comparison=require_comparison,
    )

    output = report_path or (workspace_path / "benchmark-release-gate-report.json")
    write_release_gate_report(output, report)

    breach_lines = list(report.gate_breaches or report.reasons)
    breach_lines, category_error = _filter_breach_lines(breach_lines, breach_category)
    if category_error:
        console.print(f"[red]{category_error}[/red]")
        raise typer.Exit(2)

    if json_output:
        payload = report.to_dict()
        payload["display_gate_breaches"] = breach_lines[:max_breaches]
        payload["display_max_breaches"] = max_breaches
        payload["display_breach_category"] = (breach_category or "").strip().lower()
        payload["report_path"] = str(output)
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        if fail_on_gate and not report.passed:
            raise typer.Exit(2)
        return

    print_section("Benchmark Release Gate", f"workspace={workspace_path}")
    console.print("│  Local benchmark:")
    console.print(
        "│    "
        f"p95={report.local_summary.p95_ms:.2f}ms "
        f"success={report.local_summary.success_rate:.2f}% "
        f"determinism={report.local_summary.deterministic_replay_pass_rate_pct:.2f}%"
    )
    console.print("│  Corpus benchmark:")
    console.print(
        "│    "
        f"p95={float(report.corpus_report.summary.get('p95_ms', 0.0)):.2f}ms "
        f"success={float(report.corpus_report.summary.get('success_rate', 0.0)):.2f}%"
    )
    console.print("│  Lane scheduling:")
    console.print(
        "│    "
        f"passed={'yes' if report.lane_scheduling.get('passed') else 'no'} "
        f"serial_ms={float(report.lane_scheduling.get('serial_elapsed_ms', 0.0)):.2f} "
        f"parallel_ms={float(report.lane_scheduling.get('parallel_elapsed_ms', 0.0)):.2f} "
        f"speedup={float(report.lane_scheduling.get('speedup_ratio', 0.0)):.2f}x"
    )
    console.print("│  Context cache:")
    console.print(
        "│    "
        f"passed={'yes' if report.context_cache.get('passed') else 'no'} "
        f"cold_ms={float(report.context_cache.get('cold_ms', 0.0)):.2f} "
        f"warm_ms={float(report.context_cache.get('warm_ms', 0.0)):.2f} "
        f"speedup={float(report.context_cache.get('speedup_ratio', 0.0)):.2f}x"
    )
    console.print("│  Coding loop:")
    console.print(
        "│    "
        f"passed={'yes' if report.coding_loop.get('passed') else 'no'} "
        f"success={float(report.coding_loop.get('success_rate', 0.0)):.2f}% "
        f"p95_total_ms={float(report.coding_loop.get('p95_total_ms', 0.0)):.2f}"
    )
    if report.comparison is not None:
        console.print("│  Baseline comparison:")
        console.print(
            "│    "
            f"improvement={report.comparison.improvement_pct:.2f}% "
            f"target={report.comparison.target_improvement_pct:.2f}% "
            f"meets_target={'yes' if report.comparison.meets_target else 'no'}"
        )
    if report.reasons:
        counts = report.breach_counts or {}
        if counts:
            compact = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            console.print(f"│  [red]Breach counts:[/red] {compact}")
        console.print("│  [red]Gate failures:[/red]")
        for reason in breach_lines[:max_breaches]:
            console.print(f"│    - {reason}")
    else:
        console.print("│  [green]All release gates passed[/green]")
    console.print(f"│  Report: {output}")
    print_footer()

    if fail_on_gate and not report.passed:
        raise typer.Exit(2)


@app.command("replay")
def replay(
    run_id: str = typer.Argument(..., help="Run ID to inspect"),
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    limit: int = typer.Option(500, "--limit", min=1, max=5000, help="Max events to display"),
    show_signature: bool = typer.Option(False, "--signature", help="Show deterministic replay signature"),
    verify: bool = typer.Option(False, "--verify", help="Verify deterministic signature stability and event flow"),
    verify_resume: bool = typer.Option(
        False,
        "--verify-resume",
        help="Verify recovery resume-chain equivalence assertions for this run",
    ),
    reliability: bool = typer.Option(
        False,
        "--reliability",
        help="Print run-level reliability report from runtime events",
    ),
    reexecute: bool = typer.Option(
        False,
        "--reexecute",
        help="Re-execute recorded tool requests and compare deterministic outcomes",
    ),
    allow_write_reexecute: bool = typer.Option(
        False,
        "--allow-write-reexecute",
        help="Allow workspace-write tool reexecution (still blocks elevated actions)",
    ),
    fail_on_mismatch: bool = typer.Option(
        True,
        "--fail-on-mismatch/--no-fail-on-mismatch",
        help="Exit non-zero when replay reexecution detects mismatches",
    ),
):
    """Inspect structured runtime events for a run."""
    from clawlet.config import RuntimeSettings
    from clawlet.config import load_config as load_runtime_config
    from clawlet.tools import create_default_tool_registry
    from clawlet.runtime import (
        RecoveryManager,
        RuntimeEventStore,
        build_reliability_report,
        reexecute_run,
        replay_run,
        verify_resume_equivalence,
    )

    workspace_path = workspace or get_workspace_path()
    runtime_cfg = RuntimeSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            runtime_cfg = RuntimeSettings(**(raw.get("runtime") or {}))
        except Exception:
            pass
    replay_dir = Path(runtime_cfg.replay.directory).expanduser()
    if not replay_dir.is_absolute():
        replay_dir = workspace_path / replay_dir
    store = RuntimeEventStore(replay_dir / "events.jsonl")

    events = store.iter_events(run_id=run_id, limit=limit)
    print_section("Replay", f"Run {run_id}")
    if not events:
        console.print("│  [yellow]No events found for this run id[/yellow]")
        print_footer()
        raise typer.Exit(1)

    for ev in events:
        payload = ev.payload or {}
        preview = str(payload)[:120].replace("\\n", " ")
        console.print(f"│  {ev.timestamp}  [{ev.event_type}] {preview}")

    if show_signature:
        signature = store.get_run_signature(run_id)
        console.print("│")
        console.print(f"│  Signature: [bold]{signature}[/bold]")

    if verify:
        report = replay_run(store, run_id)
        console.print("│")
        console.print(f"│  Verify signature: {'yes' if bool(report.signature) else 'no'}")
        console.print(f"│  Verify event-flow: {'yes' if report.has_start and report.has_end else 'no'}")
        console.print(
            "│  Verify tool-chain: "
            f"requested={report.tool_requested} started={report.tool_started} finished={report.tool_finished}"
        )
        for warning in report.warnings:
            console.print(f"│  warning: {warning}")
        for error in report.errors:
            console.print(f"│  error: {error}")
        if not report.passed:
            print_footer()
            raise typer.Exit(2)

    if verify_resume:
        manager = RecoveryManager(replay_dir / "checkpoints")
        resume_report = verify_resume_equivalence(store, manager, run_id)
        console.print("│")
        console.print(
            f"│  Verify resume-equivalence: {'yes' if resume_report.equivalent else 'no'}"
        )
        console.print(
            f"│  Resume successors: {len(resume_report.successors)} "
            f"({', '.join(resume_report.successors) if resume_report.successors else 'none'})"
        )
        for detail in resume_report.details:
            console.print(f"│  detail: {detail}")
        if not resume_report.equivalent:
            print_footer()
            raise typer.Exit(2)

    if reliability or verify:
        rr = build_reliability_report(store, run_id)
        console.print("│")
        console.print(
            "│  Reliability: "
            f"tool_success_rate={rr.tool_success_rate * 100:.1f}% "
            f"tool_failed={rr.tool_failed} provider_failed={rr.provider_failed} "
            f"storage_failed={rr.storage_failed} channel_failed={rr.channel_failed}"
        )
        console.print(
            f"│  Reliability crash-like: {'yes' if rr.crash_like else 'no'} "
            f"(run_completed_error={'yes' if rr.run_completed_error else 'no'})"
        )

    if reexecute:
        try:
            cfg = load_runtime_config(workspace_path)
        except Exception:
            cfg = None
        registry = create_default_tool_registry(allowed_dir=str(workspace_path), config=cfg)
        rex = reexecute_run(
            store=store,
            run_id=run_id,
            registry=registry,
            allow_write=allow_write_reexecute,
        )
        console.print("│")
        console.print(
            "│  Reexecute: "
            f"requested={rex.requested} executed={rex.executed} matched={rex.matched} "
            f"mismatched={rex.mismatched} skipped={rex.skipped}"
        )
        for detail in rex.details:
            if detail.status == "matched":
                continue
            console.print(
                f"│  {detail.status}: tcid={detail.tool_call_id} tool={detail.tool_name} reason={detail.reason}"
            )
        if rex.mismatched > 0 and fail_on_mismatch:
            print_footer()
            raise typer.Exit(2)

    print_footer()


# ── Recovery commands ─────────────────────────────────────────────────────────

@recovery_app.command("list")
def recovery_list(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    limit: int = typer.Option(20, "--limit", min=1, max=500, help="Maximum checkpoints"),
):
    """List interrupted runs with available checkpoints."""
    from clawlet.config import RuntimeSettings
    from clawlet.runtime import RecoveryManager

    workspace_path = workspace or get_workspace_path()
    runtime_cfg = RuntimeSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            runtime_cfg = RuntimeSettings(**(raw.get("runtime") or {}))
        except Exception:
            pass
    replay_dir = Path(runtime_cfg.replay.directory).expanduser()
    if not replay_dir.is_absolute():
        replay_dir = workspace_path / replay_dir

    manager = RecoveryManager(replay_dir / "checkpoints")
    checkpoints = manager.list_active(limit=limit)

    print_section("Recovery", f"{len(checkpoints)} checkpoint(s)")
    if not checkpoints:
        console.print("│  [dim]No interrupted runs found[/dim]")
        print_footer()
        return

    for cp in checkpoints:
        console.print(
            f"│  run={cp.run_id} stage={cp.stage} iter={cp.iteration} "
            f"chat={cp.channel}/{cp.chat_id}"
        )
    print_footer()


@recovery_app.command("show")
def recovery_show(
    run_id: str = typer.Argument(..., help="Run ID"),
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Show checkpoint details for one run id."""
    from clawlet.config import RuntimeSettings
    from clawlet.runtime import RecoveryManager

    workspace_path = workspace or get_workspace_path()
    runtime_cfg = RuntimeSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            runtime_cfg = RuntimeSettings(**(raw.get("runtime") or {}))
        except Exception:
            pass
    replay_dir = Path(runtime_cfg.replay.directory).expanduser()
    if not replay_dir.is_absolute():
        replay_dir = workspace_path / replay_dir

    manager = RecoveryManager(replay_dir / "checkpoints")
    cp = manager.load(run_id)
    print_section("Recovery", f"run={run_id}")
    if cp is None:
        console.print("│  [red]Checkpoint not found[/red]")
        print_footer()
        raise typer.Exit(1)

    console.print(f"│  session={cp.session_id}")
    console.print(f"│  stage={cp.stage}")
    console.print(f"│  iteration={cp.iteration}")
    console.print(f"│  channel={cp.channel}")
    console.print(f"│  chat_id={cp.chat_id}")
    console.print(f"│  notes={cp.notes}")
    if cp.pending_confirmation:
        console.print(f"│  pending_confirmation={cp.pending_confirmation}")
    print_footer()


@recovery_app.command("resume-payload")
def recovery_resume_payload(
    run_id: str = typer.Argument(..., help="Run ID"),
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Render recovery inbound payload for manual resume orchestration."""
    import json
    from clawlet.config import RuntimeSettings
    from clawlet.runtime import RecoveryManager

    workspace_path = workspace or get_workspace_path()
    runtime_cfg = RuntimeSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            runtime_cfg = RuntimeSettings(**(raw.get("runtime") or {}))
        except Exception:
            pass
    replay_dir = Path(runtime_cfg.replay.directory).expanduser()
    if not replay_dir.is_absolute():
        replay_dir = workspace_path / replay_dir

    manager = RecoveryManager(replay_dir / "checkpoints")
    payload = manager.build_resume_message(run_id)
    if payload is None:
        console.print("[red]Checkpoint not found[/red]")
        raise typer.Exit(1)
    console.print(json.dumps(payload, indent=2))


@recovery_app.command("cleanup")
def recovery_cleanup(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    retention_days: int = typer.Option(
        0,
        "--retention-days",
        min=0,
        help="Override runtime.replay.retention_days (0 uses config value)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview cleanup without modifying files",
    ),
):
    """Prune replay events/checkpoints older than retention policy."""
    from clawlet.config import RuntimeSettings
    from clawlet.runtime import cleanup_replay_artifacts

    workspace_path = workspace or get_workspace_path()
    runtime_cfg = RuntimeSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            runtime_cfg = RuntimeSettings(**(raw.get("runtime") or {}))
        except Exception:
            pass
    replay_dir = Path(runtime_cfg.replay.directory).expanduser()
    if not replay_dir.is_absolute():
        replay_dir = workspace_path / replay_dir

    effective_retention_days = int(retention_days or runtime_cfg.replay.retention_days)
    report = cleanup_replay_artifacts(
        replay_dir=replay_dir,
        retention_days=effective_retention_days,
        dry_run=dry_run,
    )

    print_section("Recovery Cleanup", f"retention_days={effective_retention_days} dry_run={str(dry_run).lower()}")
    console.print(f"│  replay_dir={report.replay_dir}")
    console.print(
        "│  events: "
        f"total={report.event_lines_total} kept={report.event_lines_kept} "
        f"removed={report.event_lines_removed} malformed={report.event_lines_malformed}"
    )
    console.print(
        "│  checkpoints: "
        f"total={report.checkpoints_total} kept={report.checkpoints_kept} "
        f"removed={report.checkpoints_removed}"
    )
    print_footer()


# ── Plugin SDK commands ───────────────────────────────────────────────────────

@plugin_app.command("init")
def plugin_init(
    name: str = typer.Argument(..., help="Plugin name"),
    directory: Path = typer.Option(Path("."), "--dir", help="Base directory for plugin"),
):
    """Initialize a plugin SDK v2 skeleton."""
    class_name = name.title().replace("-", "").replace("_", "") + "Tool"
    plugin_dir = (directory / name).resolve()
    plugin_dir.mkdir(parents=True, exist_ok=True)

    plugin_file = plugin_dir / "plugin.py"
    readme_file = plugin_dir / "README.md"

    if not plugin_file.exists():
        plugin_template = f"""\"\"\"Example Clawlet plugin: {name}.\"\"\"\n\nfrom clawlet.plugins import PluginTool, ToolInput, ToolOutput, ToolSpec\n\n\nclass {class_name}(PluginTool):\n    def __init__(self):\n        super().__init__(ToolSpec(name=\"{name}\", description=\"Example plugin tool\"))\n\n    async def execute_with_context(self, tool_input: ToolInput, context) -> ToolOutput:\n        return ToolOutput(output=\"Plugin executed\", data={{\"arguments\": tool_input.arguments}})\n\n\nTOOLS = [{class_name}()]\n"""
        plugin_file.write_text(plugin_template, encoding="utf-8")

    if not readme_file.exists():
        readme_file.write_text(
            f"# {name}\\n\\n"
            "This plugin follows Clawlet Plugin SDK v2.\\n\\n"
            "Commands:\\n"
            f"- `clawlet plugin test --path {plugin_dir}`\\n"
            f"- `clawlet plugin publish --path {plugin_dir}`\\n",
            encoding="utf-8",
        )

    console.print(f"[green]✓ Plugin initialized at {plugin_dir}[/green]")


@plugin_app.command("test")
def plugin_test(
    path: Path = typer.Option(..., "--path", help="Plugin directory containing plugin.py"),
    strict: bool = typer.Option(
        True,
        "--strict/--no-strict",
        help="Fail on conformance errors",
    ),
):
    """Load and validate a plugin package."""
    from clawlet.plugins.loader import PluginLoader
    from clawlet.plugins.conformance import check_plugin_conformance

    loader = PluginLoader([path])
    tools = loader.load_tools()

    if not tools:
        console.print("[red]No valid plugin tools discovered[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓ Loaded {len(tools)} plugin tool(s)[/green]")
    for tool in tools:
        console.print(f"  - {tool.name}: {tool.description}")

    report = check_plugin_conformance(tools)
    if report.issues:
        console.print()
        console.print(f"[bold]Conformance:[/bold] {len(report.issues)} issue(s)")
        for issue in report.issues:
            color = "red" if issue.severity == "error" else ("yellow" if issue.severity == "warning" else "cyan")
            console.print(
                f"[{color}]• {issue.severity.upper()}[/{color}] "
                f"{issue.plugin_name} [{issue.code}] {issue.message}"
            )
            console.print(f"  hint: {issue.hint}")

    if strict and not report.passed:
        raise typer.Exit(2)


@plugin_app.command("conformance")
def plugin_conformance(
    path: Path = typer.Option(..., "--path", help="Plugin directory containing plugin.py"),
):
    """Run Plugin SDK v2 conformance checks."""
    from clawlet.plugins.loader import PluginLoader
    from clawlet.plugins.conformance import check_plugin_conformance

    loader = PluginLoader([path])
    tools = loader.load_tools()
    report = check_plugin_conformance(tools)

    print_section("Plugin Conformance", f"path={path}")
    console.print(
        "│  "
        f"checked={report.checked} errors={len(report.errors)} "
        f"warnings={len(report.warnings)} infos={len(report.infos)}"
    )
    if report.issues:
        console.print("│")
        for issue in report.issues:
            console.print(
                "│  "
                f"{issue.severity.upper()} {issue.plugin_name} [{issue.code}] {issue.message}"
            )
            console.print(f"│    hint: {issue.hint}")
    print_footer()

    if not report.passed:
        raise typer.Exit(2)


@plugin_app.command("matrix")
def plugin_matrix(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    fail_on_errors: bool = typer.Option(
        False,
        "--fail-on-errors",
        help="Exit non-zero when plugin conformance errors are detected",
    ),
):
    """Scan plugin directories and summarize conformance compatibility."""
    from clawlet.config import load_config
    from clawlet.plugins.matrix import run_plugin_conformance_matrix, write_plugin_matrix_report

    workspace_path = workspace or get_workspace_path()
    try:
        config = load_config(workspace_path)
        plugin_dirs = []
        for raw_dir in config.plugins.directories:
            p = Path(raw_dir).expanduser()
            if not p.is_absolute():
                p = workspace_path / p
            plugin_dirs.append(p)
    except Exception:
        plugin_dirs = [workspace_path / "plugins"]

    report = run_plugin_conformance_matrix(plugin_dirs)
    print_section("Plugin Matrix", f"workspace={workspace_path}")
    console.print(
        "│  "
        f"directories={report.scanned_directories} tools={report.scanned_tools} "
        f"errors={report.total_errors} warnings={report.total_warnings} infos={report.total_infos}"
    )
    if report.results:
        console.print("│")
        for item in report.results:
            console.print(
                "│  "
                f"{item.directory}: tools={item.loaded_tools} "
                f"errors={item.errors} warnings={item.warnings} "
                f"passed={'yes' if item.passed else 'no'}"
            )
    output = report_path or (workspace_path / "plugin-matrix-report.json")
    write_plugin_matrix_report(output, report)
    console.print(f"│  Report: {output}")
    print_footer()

    if fail_on_errors and not report.passed:
        raise typer.Exit(2)


@plugin_app.command("publish")
def plugin_publish(
    path: Path = typer.Option(..., "--path", help="Plugin directory to package"),
    out_dir: Path = typer.Option(Path("dist"), "--out-dir", help="Output directory"),
):
    """Package a plugin directory as a distributable tarball."""
    import tarfile
    import time as _time

    if not path.exists() or not path.is_dir():
        console.print("[red]Invalid plugin path[/red]")
        raise typer.Exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{path.name}-{int(_time.time())}.tar.gz"

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(path, arcname=path.name)

    console.print(f"[green]✓ Packaged plugin archive: {archive}[/green]")


# ── Sessions management ───────────────────────────────────────────────────────

@app.command()
def sessions(
    workspace: Optional[Path] = typer.Option(None, "--workspace", help="Workspace directory"),
    export: Optional[Path] = typer.Option(None, "--export", help="Export sessions to JSON file"),
    limit: int = typer.Option(10, "--limit", help="Number of recent sessions to list"),
):
    """🌸 List and export conversation sessions from storage."""
    workspace_path = workspace or get_workspace_path()
    
    # Determine DB path from config
    config_path = workspace_path / "config.yaml"
    if not config_path.exists():
        console.print("[red]Config file not found[/red]")
        raise typer.Exit(1)
    
    try:
        import yaml
        from clawlet.config import Config
        from clawlet.storage.sqlite import SQLiteStorage
        from clawlet.storage.postgres import PostgresStorage
        from pathlib import Path
        
        config = Config.from_yaml(config_path)
        
        # Select storage backend
        if config.storage.backend == "sqlite":
            db_path = Path(config.storage.sqlite.path).expanduser()
            storage = SQLiteStorage(db_path)
        elif config.storage.backend == "postgres":
            pg = config.storage.postgres
            storage = PostgresStorage(
                host=pg.host,
                port=pg.port,
                database=pg.database,
                user=pg.user,
                password=pg.password,
            )
        else:
            console.print(f"[red]Unsupported storage backend: {config.storage.backend}[/red]")
            raise typer.Exit(1)
        
        # Note: Need to run async init; we'll do it synchronously for CLI
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(storage.initialize())
        
        # For SQLite, we can query distinct session_ids directly
        if config.storage.backend == "sqlite":
            import aiosqlite
            async def get_recent_sessions():
                async with aiosqlite.connect(db_path) as db:
                    # Get distinct session_ids ordered by latest activity
                    cursor = await db.execute("""
                        SELECT session_id, COUNT(*) as msg_count, MAX(created_at) as last_seen
                        FROM messages
                        GROUP BY session_id
                        ORDER BY last_seen DESC
                        LIMIT ?
                    """, (limit,))
                    rows = await cursor.fetchall()
                    return rows
            rows = loop.run_until_complete(get_recent_sessions())
        else:
            console.print("[yellow]Postgres sessions listing not implemented yet[/yellow]")
            rows = []
        
        if not rows:
            console.print("[dim]No sessions found[/dim]")
        else:
            print_section("Recent Sessions", f"Showing up to {limit} sessions")
            for session_id, count, last_seen in rows:
                console.print(f"│  {session_id[:12]}...  [{count} messages]  last: {last_seen}")
            print_footer()
        
        # Export if requested
        if export:
            import json
            # Export all messages for all sessions (or limit?)
            export_data = []
            if config.storage.backend == "sqlite":
                async def export_all():
                    async with aiosqlite.connect(db_path) as db:
                        cursor = await db.execute("SELECT * FROM messages ORDER BY created_at DESC")
                        rows = await cursor.fetchall()
                        # Convert to dict
                        cols = [desc[0] for desc in cursor.description]
                        return [dict(zip(cols, row)) for row in rows]
                all_msgs = loop.run_until_complete(export_all())
                export.write_text(json.dumps(all_msgs, indent=2))
                console.print(f"[green]✓ Exported {len(all_msgs)} messages to {export}[/green]")
        
        loop.run_until_complete(storage.close())
        loop.close()
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
