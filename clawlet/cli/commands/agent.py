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
    from clawlet.agent.memory import MemoryManager
    from clawlet.bus.queue import MessageBus
    from clawlet.config import load_config
    from loguru import logger
    import os
    
    # Load identity
    identity_loader = IdentityLoader(workspace)
    identity = identity_loader.load_all()
    
    # Create message bus
    bus = MessageBus()
    
    # Load configuration first (needed for both provider and channels)
    config = load_config(workspace)
    
    # DEBUG: Log the primary provider to confirm the issue
    primary_provider = config.provider.primary
    logger.debug(f"DEBUG: Primary provider from config: {primary_provider}")
    
    # Get API key and model based on the configured primary provider
    api_key = ""
    config_model = None
    
    if primary_provider == "openrouter":
        logger.debug("DEBUG: Selected provider is OpenRouter - checking for OPENROUTER_API_KEY")
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            api_key = config.provider.openrouter.api_key if config.provider.openrouter else ""
        config_model = config.provider.openrouter.model if config.provider.openrouter else None
    elif primary_provider == "ollama":
        logger.debug("DEBUG: Selected provider is Ollama - no API key required")
        config_model = config.provider.ollama.model if config.provider.ollama else None
    elif primary_provider == "lmstudio":
        logger.debug("DEBUG: Selected provider is LMStudio - no API key required")
        config_model = config.provider.lmstudio.model if config.provider.lmstudio else None
    elif primary_provider == "openai":
        logger.debug("DEBUG: Selected provider is OpenAI - checking for OPENAI_API_KEY")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            api_key = config.provider.openai.api_key if config.provider.openai else ""
        config_model = config.provider.openai.model if config.provider.openai else None
    elif primary_provider == "anthropic":
        logger.debug("DEBUG: Selected provider is Anthropic - checking for ANTHROPIC_API_KEY")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            api_key = config.provider.anthropic.api_key if config.provider.anthropic else ""
        config_model = config.provider.anthropic.model if config.provider.anthropic else None
    else:
        logger.warning(f"DEBUG: Unknown provider '{primary_provider}', defaulting behavior")
        # Fallback: try openrouter config
        if config.provider.openrouter:
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            if not api_key:
                api_key = config.provider.openrouter.api_key
            config_model = config.provider.openrouter.model
    
    # Use model from CLI arg, then config, then provider default
    effective_model = model or config_model
    
    logger.debug(f"DEBUG: Creating provider for '{primary_provider}' with model: {effective_model}")
    
    # Create provider based on the primary provider setting
    if primary_provider == "openrouter":
        from clawlet.providers.openrouter import OpenRouterProvider
        provider = OpenRouterProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "ollama":
        from clawlet.providers.ollama import OllamaProvider
        provider = OllamaProvider(base_url=config.provider.ollama.base_url, default_model=effective_model)
    elif primary_provider == "lmstudio":
        from clawlet.providers.lmstudio import LMStudioProvider
        provider = LMStudioProvider(base_url=config.provider.lmstudio.base_url, default_model=effective_model)
    elif primary_provider == "openai":
        from clawlet.providers.openai import OpenAIProvider
        provider = OpenAIProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "anthropic":
        from clawlet.providers.anthropic import AnthropicProvider
        provider = AnthropicProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "minimax":
        from clawlet.providers.minimax import MiniMaxProvider
        api_key = api_key or (config.provider.minimax.api_key if config.provider.minimax else "")
        provider = MiniMaxProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "moonshot":
        from clawlet.providers.moonshot import MoonshotProvider
        api_key = api_key or (config.provider.moonshot.api_key if config.provider.moonshot else "")
        provider = MoonshotProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "google":
        from clawlet.providers.google import GoogleProvider
        api_key = api_key or (config.provider.google.api_key if config.provider.google else "")
        provider = GoogleProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "qwen":
        from clawlet.providers.qwen import QwenProvider
        api_key = api_key or (config.provider.qwen.api_key if config.provider.qwen else "")
        provider = QwenProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "zai":
        from clawlet.providers.zai import ZAIProvider
        api_key = api_key or (config.provider.zai.api_key if config.provider.zai else "")
        provider = ZAIProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "copilot":
        from clawlet.providers.copilot import CopilotProvider
        access_token = os.environ.get("GITHUB_TOKEN", config.provider.copilot.access_token if config.provider.copilot else "")
        provider = CopilotProvider(access_token=access_token, default_model=effective_model)
    elif primary_provider == "vercel":
        from clawlet.providers.vercel import VercelProvider
        api_key = api_key or (config.provider.vercel.api_key if config.provider.vercel else "")
        provider = VercelProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "opencode_zen":
        from clawlet.providers.opencode_zen import OpenCodeZenProvider
        api_key = api_key or (config.provider.opencode_zen.api_key if config.provider.opencode_zen else "")
        provider = OpenCodeZenProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "xiaomi":
        from clawlet.providers.xiaomi import XiaomiProvider
        api_key = api_key or (config.provider.xiaomi.api_key if config.provider.xiaomi else "")
        provider = XiaomiProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "synthetic":
        from clawlet.providers.synthetic import SyntheticProvider
        api_key = api_key or (config.provider.synthetic.api_key if config.provider.synthetic else "")
        provider = SyntheticProvider(api_key=api_key, default_model=effective_model)
    elif primary_provider == "venice_ai":
        from clawlet.providers.venice import VeniceProvider
        api_key = api_key or (config.provider.venice_ai.api_key if config.provider.venice_ai else "")
        provider = VeniceProvider(api_key=api_key, default_model=effective_model)
    else:
        # Default fallback to openrouter
        from clawlet.providers.openrouter import OpenRouterProvider
        logger.warning(f"Unknown provider '{primary_provider}', falling back to OpenRouter")
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
    
    telegram_channel = None
    try:
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
        memory = MemoryManager(workspace)
        
        # Create tool registry with all tools (including web search)
        from clawlet.tools import create_default_tool_registry
        allowed_dir = str(workspace)
        tools = create_default_tool_registry(allowed_dir=allowed_dir, config=config)
        
        agent = AgentLoop(
            bus=bus,
            workspace=workspace,
            identity=identity,
            provider=provider,
            model=effective_model,
            memory=memory,
            tools=tools,
        )
        
        # Run the agent
        await agent.run()
    finally:
        if telegram_channel is not None:
            try:
                logger.info("Stopping Telegram channel...")
                await telegram_channel.stop()
            except Exception as e:
                logger.error(f"Error stopping Telegram channel: {e}")
