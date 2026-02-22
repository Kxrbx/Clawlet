"""
Agent command module.
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer

from clawlet.cli import app, console, get_workspace_path, print_sakura_banner

SAKURA_LIGHT = "#FFB7C5"


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
    
    # Get Telegram configuration from the correct field
    # ClawletConfig stores channels as individual fields (telegram, discord, etc.)
    telegram_cfg = config.telegram
    
    # Handle both raw dict and Pydantic model formats
    if isinstance(telegram_cfg, dict):
        telegram_enabled = telegram_cfg.get("enabled", False)
        telegram_token = telegram_cfg.get("token", "")
    else:
        # Pydantic model
        telegram_enabled = getattr(telegram_cfg, 'enabled', False)
        telegram_token = getattr(telegram_cfg, 'token', '')
    
    from loguru import logger
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
