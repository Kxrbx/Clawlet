"""
Models command module.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from clawlet.cli import SAKURA_LIGHT, SAKURA_PINK, app, console, get_workspace_path, print_section, print_footer


@app.command(name="models")
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
    from loguru import logger
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
