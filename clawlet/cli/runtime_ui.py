"""Runtime command helpers for the CLI."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console

console = Console()


def run_agent_command(
    workspace: Optional[Path],
    model: Optional[str],
    channel: str,
    log_file: Optional[Path],
    log_level: str,
    get_workspace_path_fn,
    print_sakura_banner_fn,
    sakura_light: str,
) -> None:
    """Run agent command orchestration."""
    workspace_path = workspace or get_workspace_path_fn()

    if not workspace_path.exists():
        console.print("[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]")
        raise typer.Exit(1)

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

    print_sakura_banner_fn()
    console.print(f"\n[{sakura_light}]Starting agent with {channel} channel...[/{sakura_light}]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    try:
        asyncio.run(run_agent(workspace_path, model, channel))
    except KeyboardInterrupt:
        console.print("\n[yellow]Agent stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def run_chat_command(workspace: Optional[Path], model: Optional[str], get_workspace_path_fn) -> None:
    """Run local chat command orchestration."""
    workspace_path = workspace or get_workspace_path_fn()
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


def run_logs_command(log_file: Path, lines: int, follow: bool) -> None:
    """Tail or print agent logs."""
    if not log_file.exists():
        console.print(f"[yellow]Log file not found: {log_file}[/yellow]")
        console.print("Start the agent with --log-file to enable file logging.")
        raise typer.Exit(1)

    try:
        if follow:
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
        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or (
            config.provider.anthropic.api_key if config.provider.anthropic else ""
        )
        effective_model = model or (config.provider.anthropic.model if config.provider.anthropic else None)
        from clawlet.providers.anthropic import AnthropicProvider

        return AnthropicProvider(api_key=api_key, default_model=effective_model), effective_model

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key and config.provider.openrouter:
        api_key = config.provider.openrouter.api_key
    effective_model = model or (config.provider.openrouter.model if config.provider.openrouter else None)
    from clawlet.providers.openrouter import OpenRouterProvider

    return OpenRouterProvider(api_key=api_key, default_model=effective_model), effective_model


async def run_agent(workspace: Path, model: Optional[str], channel: str):
    """Run the agent loop with explicit channel routing."""
    from clawlet.agent.identity import IdentityLoader
    from clawlet.agent.loop import AgentLoop
    from clawlet.bus.queue import MessageBus
    from clawlet.config import load_config

    identity_loader = IdentityLoader(workspace)
    identity = identity_loader.load_all()
    bus = MessageBus()
    config = load_config(workspace)

    provider, effective_model = _create_provider(config, model)

    from clawlet.tools import create_default_tool_registry

    tools = create_default_tool_registry(allowed_dir=str(workspace), config=config)
    logger.info(f"Created tool registry with {len(tools.all_tools())} tools")

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

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown_agent(agent, runtime_channel, s)))

    await agent.run()


async def shutdown_agent(agent, runtime_channel, signum):
    """Shutdown agent gracefully on signal."""
    logger.info(f"Received signal {signum}, shutting down...")

    if runtime_channel is not None:
        try:
            logger.info("Stopping Telegram channel...")
            await runtime_channel.stop()
            logger.info("Telegram channel stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram channel: {e}")

    agent.stop()
    await agent.close()
    logger.info("Agent shutdown complete")


async def run_chat(workspace: Path, model: Optional[str]) -> None:
    """Run a local terminal chat loop using the same agent core."""
    from clawlet.agent.identity import IdentityLoader
    from clawlet.agent.loop import AgentLoop
    from clawlet.bus.queue import InboundMessage, MessageBus
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
