"""Model-management UI helpers for the CLI."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

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

    current_model = None
    api_key = None
    if config.provider.openrouter:
        current_model = config.provider.openrouter.model
        api_key = config.provider.openrouter.api_key
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")

    if current:
        print_section("Current Model", "Active model configuration")
        console.print("|")
        if current_model:
            console.print(f"|  [bold]Model:[/bold] [{SAKURA_PINK}]{current_model}[/{SAKURA_PINK}]")
        else:
            console.print("|  [yellow]No model configured[/yellow]")
        print_footer()
        return

    if list_models:
        asyncio.run(_list_models(api_key))
        return

    try:
        new_model = asyncio.run(_select_model_interactive(api_key, current_model))
        if new_model and new_model != current_model:
            if config.provider.openrouter:
                config.provider.openrouter.model = new_model
            else:
                from clawlet.config import OpenRouterConfig, ProviderConfig

                config.provider = ProviderConfig(
                    primary="openrouter",
                    openrouter=OpenRouterConfig(api_key=api_key or "", model=new_model),
                )
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


async def _list_models(api_key: str = None):
    """List all available models from OpenRouter."""
    print_section("Available Models", "Fetching models from OpenRouter...")
    console.print("|")

    try:
        from clawlet.providers.openrouter import OpenRouterProvider

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
                console.print("|  [yellow]! No API key configured, using cached/default models[/yellow]")
                from clawlet.cli.onboard import DEFAULT_OPENROUTER_MODELS

                models = [{"id": m, "name": m} for m in DEFAULT_OPENROUTER_MODELS]

            progress.update(task, completed=100, description="Done!")

        if not models:
            console.print("|  [red]x No models found[/red]")
            print_footer()
            return

        table = Table(show_header=True, header_style=f"bold {SAKURA_PINK}", box=None)
        table.add_column("Model ID", style=SAKURA_LIGHT)
        table.add_column("Name", style="dim")

        for model in models[:20]:
            model_id = model.get("id", "Unknown")
            model_name = model.get("name", model.get("id", "").split("/")[-1])
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


async def _select_model_interactive(api_key: str = None, current_model: str = None) -> str:
    """Interactive model selection with search and browse."""
    from clawlet.cli.onboard import (
        CUSTOM_STYLE,
        DEFAULT_OPENROUTER_MODELS,
        _search_models,
        _show_all_models,
        _use_default_models,
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
            console.print(f"|  [green]OK[/green] Found {len(models)} models")
    except Exception as e:
        logger.debug(f"Could not fetch models: {e}")
        console.print("|  [yellow]! Could not fetch models from API[/yellow]")

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
        choices = ["Search models...", "Use default models"]
        choices.extend(DEFAULT_OPENROUTER_MODELS[:5])

    choice = await questionary.select(
        "  Select a model:",
        choices=choices,
        style=CUSTOM_STYLE,
    ).ask_async()

    if choice is None:
        return None

    if choice.startswith("Search models..."):
        return await _search_models(
            models if models else [{"id": m} for m in DEFAULT_OPENROUTER_MODELS],
            model_ids if model_ids else DEFAULT_OPENROUTER_MODELS,
        )
    if choice.startswith("Show all ("):
        if model_ids:
            return await _show_all_models(models, model_ids)
        return await _use_default_models()
    if choice.startswith("Use default models"):
        return await _use_default_models()
    if choice in (model_ids if model_ids else DEFAULT_OPENROUTER_MODELS):
        return choice
    return model_ids[0] if model_ids else DEFAULT_OPENROUTER_MODELS[0]
