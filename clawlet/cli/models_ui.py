"""Model-management UI helpers for the CLI."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from clawlet.cli.common_ui import print_footer, print_section

SAKURA_PINK = "#FF69B4"
SAKURA_LIGHT = "#FFB7C5"
console = Console()


def run_models_command(workspace_path: Path, config_path: Path, current: bool, list_models: bool) -> None:
    """Run models command orchestration."""
    if not config_path.exists():
        console.print("[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]")
        raise typer.Exit(1)

    try:
        from clawlet.config import Config

        config = Config.from_yaml(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1)

    provider_name = str(getattr(config.provider, "primary", "openrouter") or "openrouter").lower()
    current_model = _get_config_model(config, provider_name)

    if current:
        print_section("Current Model", "Active model configuration")
        console.print("|")
        console.print(f"|  [bold]Provider:[/bold] [{SAKURA_PINK}]{provider_name}[/{SAKURA_PINK}]")
        if current_model:
            console.print(f"|  [bold]Model:[/bold] [{SAKURA_PINK}]{current_model}[/{SAKURA_PINK}]")
        else:
            console.print("|  [yellow]No model configured[/yellow]")
        print_footer()
        return

    if list_models:
        asyncio.run(_list_models(config, provider_name))
        return

    try:
        new_model = asyncio.run(_select_model_interactive(config, provider_name, current_model))
        if new_model and new_model != current_model:
            _set_config_model(config, provider_name, new_model)
            config.to_yaml(config_path)
            console.print()
            console.print(f"[green]OK Model updated to:[/green] [{SAKURA_PINK}]{new_model}[/{SAKURA_PINK}]")
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
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


async def _list_models(config: Any, provider_name: str):
    """List all available models from the configured provider."""
    print_section("Available Models", f"Fetching models from {provider_name}...")
    console.print("|")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Fetching models...", total=100)
            models = await _fetch_provider_models(config, provider_name)

            progress.update(task, completed=100, description="Done!")

        if not models:
            console.print("|  [red]x No models found[/red]")
            print_footer()
            return

        table = Table(show_header=True, header_style=f"bold {SAKURA_PINK}", box=None)
        table.add_column("Model ID", style=SAKURA_LIGHT)
        table.add_column("Name", style="dim")

        for model in models[:20]:
            model_id = _model_identifier(model)
            model_name = _model_display_name(model)
            if len(model_name) > 40:
                model_name = model_name[:37] + "..."
            table.add_row(model_id, model_name)

        console.print("|")
        console.print(f"|  [green]OK[/green] Found {len(models)} models (showing top 20)")
        console.print("|")
        for line in str(table).split("\n"):
            console.print(f"|  {line}")

        if len(models) > 20:
            console.print("|")
            console.print(f"|  [dim]... and {len(models) - 20} more models[/dim]")
            console.print("|")
            console.print("|  [dim]Use 'clawlet models' to search and select interactively[/dim]")

        print_footer()

    except Exception as e:
        console.print(f"|  [red]x Error fetching models: {e}[/red]")
        print_footer()


async def _select_model_interactive(config: Any, provider_name: str, current_model: str = None) -> str:
    """Interactive model selection with search and browse."""
    from clawlet.cli.onboard import (
        CUSTOM_STYLE,
        DEFAULT_OPENROUTER_MODELS,
        _search_models,
        _show_all_models,
    )
    import questionary

    print_section("Model Selection", "Choose your AI model")
    console.print("|")

    if current_model:
        console.print(f"|  [bold]Current model:[/bold] [{SAKURA_PINK}]{current_model}[/{SAKURA_PINK}]")
        console.print("|")

    models = []
    model_ids = []

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(f"Fetching models from {provider_name}...", total=100)
            models = await _fetch_provider_models(config, provider_name)
            model_ids = [_model_identifier(m) for m in models if _model_identifier(m)]

            progress.update(task, completed=100, description="Done!")

        if models:
            console.print(f"|  [green]OK[/green] Found {len(models)} models")
    except Exception as e:
        logger.debug(f"Could not fetch models: {e}")
        console.print("|  [yellow]! Could not fetch models from API[/yellow]")

    fallback_ids = _fallback_model_ids(config, provider_name, current_model)

    console.print("|")
    if model_ids:
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

        choices = ["Search models...", f"Show all ({len(models)} models)"]
        if popular:
            choices.extend(popular)
    else:
        choices = ["Search models..."]
        choices.extend(fallback_ids[:5] if fallback_ids else DEFAULT_OPENROUTER_MODELS[:5])

    choice = await questionary.select(
        "  Select a model:",
        choices=choices,
        style=CUSTOM_STYLE,
    ).ask_async()

    if choice is None:
        return None

    if choice.startswith("Search models..."):
        return await _search_models(
            models if models else [{"id": m} for m in (fallback_ids or DEFAULT_OPENROUTER_MODELS)],
            model_ids if model_ids else (fallback_ids or DEFAULT_OPENROUTER_MODELS),
        )
    if choice.startswith("Show all ("):
        if model_ids:
            return await _show_all_models(models, model_ids)
        return None
    if choice in (model_ids if model_ids else (fallback_ids or DEFAULT_OPENROUTER_MODELS)):
        return choice
    return model_ids[0] if model_ids else (fallback_ids or DEFAULT_OPENROUTER_MODELS)[0]


def _get_config_model(config: Any, provider_name: str) -> str | None:
    provider_config = getattr(config.provider, provider_name, None)
    return getattr(provider_config, "model", None)


def _set_config_model(config: Any, provider_name: str, model: str) -> None:
    provider_config = getattr(config.provider, provider_name, None)
    if provider_config is None:
        raise RuntimeError(f"Provider '{provider_name}' is not configured in config.yaml")
    provider_config.model = model


def _resolve_provider_credentials(config: Any, provider_name: str) -> dict[str, str]:
    provider_config = getattr(config.provider, provider_name, None)
    env_by_provider = {
        "openrouter": ("OPENROUTER_API_KEY", "api_key"),
        "openai": ("OPENAI_API_KEY", "api_key"),
        "anthropic": ("ANTHROPIC_API_KEY", "api_key"),
        "minimax": ("MINIMAX_API_KEY", "api_key"),
        "moonshot": ("MOONSHOT_API_KEY", "api_key"),
        "google": ("GOOGLE_API_KEY", "api_key"),
        "qwen": ("QWEN_API_KEY", "api_key"),
        "zai": ("ZAI_API_KEY", "api_key"),
        "copilot": ("GITHUB_TOKEN", "access_token"),
        "vercel": ("VERCEL_API_KEY", "api_key"),
        "opencode_zen": ("OPENCODE_ZEN_API_KEY", "api_key"),
        "xiaomi": ("XIAOMI_API_KEY", "api_key"),
        "synthetic": ("SYNTHETIC_API_KEY", "api_key"),
        "venice": ("VENICE_API_KEY", "api_key"),
    }
    if provider_name not in env_by_provider:
        return {}

    env_var, field_name = env_by_provider[provider_name]
    env_value = os.environ.get(env_var, "")
    config_value = getattr(provider_config, field_name, "") if provider_config else ""
    return {field_name: env_value or config_value}


def _create_models_provider(config: Any, provider_name: str) -> Any:
    provider_config = getattr(config.provider, provider_name, None)
    default_model = getattr(provider_config, "model", None) or _get_config_model(config, provider_name)
    credentials = _resolve_provider_credentials(config, provider_name)

    if provider_name == "openrouter":
        from clawlet.providers.openrouter import OpenRouterProvider

        return OpenRouterProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "openai":
        from clawlet.providers.openai import OpenAIProvider

        organization = getattr(provider_config, "organization", None) if provider_config else None
        return OpenAIProvider(
            api_key=credentials.get("api_key", ""),
            default_model=default_model,
            organization=organization,
        )
    if provider_name == "anthropic":
        from clawlet.providers.anthropic import AnthropicProvider

        return AnthropicProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "minimax":
        from clawlet.providers.minimax import MiniMaxProvider

        return MiniMaxProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "moonshot":
        from clawlet.providers.moonshot import MoonshotProvider

        return MoonshotProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "google":
        from clawlet.providers.google import GoogleProvider

        return GoogleProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "qwen":
        from clawlet.providers.qwen import QwenProvider

        return QwenProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "zai":
        from clawlet.providers.zai import ZAIProvider

        return ZAIProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "copilot":
        from clawlet.providers.copilot import CopilotProvider

        return CopilotProvider(access_token=credentials.get("access_token", ""), default_model=default_model)
    if provider_name == "vercel":
        from clawlet.providers.vercel import VercelProvider

        return VercelProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "opencode_zen":
        from clawlet.providers.opencode_zen import OpenCodeZenProvider

        return OpenCodeZenProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "xiaomi":
        from clawlet.providers.xiaomi import XiaomiProvider

        return XiaomiProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "synthetic":
        from clawlet.providers.synthetic import SyntheticProvider

        return SyntheticProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "venice":
        from clawlet.providers.venice import VeniceProvider

        return VeniceProvider(api_key=credentials.get("api_key", ""), default_model=default_model)
    if provider_name == "ollama":
        from clawlet.providers.ollama import OllamaProvider

        base_url = getattr(provider_config, "base_url", "http://localhost:11434") if provider_config else "http://localhost:11434"
        return OllamaProvider(base_url=base_url, default_model=default_model)
    if provider_name == "lmstudio":
        from clawlet.providers.lmstudio import LMStudioProvider

        base_url = getattr(provider_config, "base_url", "http://localhost:1234") if provider_config else "http://localhost:1234"
        return LMStudioProvider(base_url=base_url, default_model=default_model)

    raise RuntimeError(f"Provider '{provider_name}' is not supported by 'clawlet models'")


async def _fetch_provider_models(config: Any, provider_name: str) -> list[dict]:
    provider = _create_models_provider(config, provider_name)
    try:
        list_models = getattr(provider, "list_models", None)
        if list_models is None:
            raise RuntimeError(f"Provider '{provider_name}' does not expose model discovery")

        try:
            raw_models = await list_models(force_refresh=True)
        except TypeError:
            raw_models = await list_models()

        models = [_normalize_model_entry(model) for model in raw_models]
        models = [model for model in models if model.get("id")]
        models.sort(key=lambda item: item.get("id", ""))
        return models
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()


def _normalize_model_entry(model: Any) -> dict[str, str]:
    if isinstance(model, dict):
        normalized = dict(model)
        if not normalized.get("id"):
            normalized["id"] = normalized.get("name") or normalized.get("displayName") or normalized.get("model") or ""
        return normalized
    if isinstance(model, str):
        return {"id": model, "name": model}
    return {"id": str(model), "name": str(model)}


def _model_identifier(model: dict[str, Any]) -> str:
    return str(model.get("id") or model.get("name") or model.get("displayName") or "Unknown")


def _model_display_name(model: dict[str, Any]) -> str:
    return str(model.get("name") or model.get("displayName") or model.get("id") or "Unknown")


def _fallback_model_ids(config: Any, provider_name: str, current_model: str | None) -> list[str]:
    fallback_ids: list[str] = []
    if current_model:
        fallback_ids.append(current_model)

    configured_model = _get_config_model(config, provider_name)
    if configured_model and configured_model not in fallback_ids:
        fallback_ids.append(configured_model)

    return fallback_ids
