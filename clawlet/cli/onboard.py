"""
Interactive onboarding experience for Clawlet - Unique UI.
"""

import asyncio
from pathlib import Path
from typing import Optional
import os

from rich.console import Console
from rich.text import Text
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.layout import Layout
from rich.panel import Panel
from rich import box

import questionary
from questionary import Style

from loguru import logger

from clawlet.cli.runtime_paths import get_default_workspace_path
from clawlet.agent.task_profiles import TASK_KINDS, TaskProfile
from clawlet.config import (
    Config,
    ProviderConfig,
    OpenRouterConfig,
    OllamaConfig,
    LMStudioConfig,
    OpenAIConfig,
    AnthropicConfig,
    MiniMaxConfig,
    MoonshotConfig,
    GoogleConfig,
    QwenConfig,
    ZAIConfig,
    CopilotConfig,
    VercelConfig,
    OpenCodeZenConfig,
    XiaomiConfig,
    SyntheticConfig,
    VeniceAIConfig,
    BraveSearchConfig,
    AgentSettings,
)


# Sakura pink color scheme
SAKURA_PINK = "#FF69B4"
SAKURA_LIGHT = "#FFB7C5"
SAKURA_DARK = "#DB7093"

# Custom style for questionary - sakura theme
CUSTOM_STYLE = Style(
    [
        ("qmark", f"fg:{SAKURA_PINK} bold"),
        ("question", "bold"),
        ("answer", f"fg:{SAKURA_DARK} bold"),
        ("pointer", f"fg:{SAKURA_PINK} bold"),
        ("highlighted", f"fg:{SAKURA_PINK} bold"),
        ("selected", f"fg:{SAKURA_LIGHT}"),
        ("separator", f"fg:{SAKURA_DARK}"),
        ("instruction", "fg:#8d8d8d"),
        ("text", ""),
    ]
)


console = Console()


def print_sakura_header():
    """Print ASCII art header with sakura petals."""
    console.clear()
    console.print("""
[bold magenta]     *  . 　　 　　　✦ 　　 　 ‍ ‍ ‍ ‍ 　. 　　　　 　　　
　　˚  . 　　　　　　　　　　　　　. 　　　✦ 　　　　　　　　　　　
[bold magenta]　✦ 　　　　 　　　　　　　　　　　　　　　. 　　　　　　　　.
 　　　　　　　　　　　. 　　　　　　　　　　　　　　　. 　　　　　　✦[/bold magenta]

[bold cyan]
  _____ _          __          ___      ______ _______ 
 / ____| |        /\\ \\        / / |    |  ____|__   __|
| |    | |       /  \\ \\  /\\  / /| |    | |__     | |   
| |    | |      / /\\ \\ \\/  \\/ / | |    |  __|    | |   
| |____| |____ / ____ \\  /\\  /  | |____| |____   | |   
 \\_____|______/_/    \\_\\/  \\/   |______|______|  |_|   
[/bold cyan]

[bold magenta]　✦ 　　　　 　　　　　　　　　　　　　　　. 　　　　　　　　.
 　　　　　　　　　　　. 　　　🌸 A lightweight AI agent framework 🌸　　　　　　✦
　　˚  . 　　　　　　　　　　　　　. 　　　✦ 　　　　　　　　　　　
[bold magenta]　✦ 　　　　 　　　　　　　　　　　　　　　. 　　　　　　　　.
     *  . 　　 　　　✦ 　　 　 ‍ ‍ ‍ ‍ 　. 　　　　 　　　[/bold magenta]
""")


def print_step_indicator(current: int, total: int, steps: list[str]):
    """Print a horizontal step indicator showing all steps."""
    console.print()

    # Build step string
    parts = []
    for i, step in enumerate(steps, 1):
        if i < current:
            # Completed
            parts.append(f"[green]✓[/green] [dim]{step}[/dim]")
        elif i == current:
            # Current
            parts.append(f"[bold {SAKURA_PINK}]● {step}[/bold {SAKURA_PINK}]")
        else:
            # Pending
            parts.append(f"[dim]○ {step}[/dim]")

    console.print("  " + "  →  ".join(parts))
    console.print()


def print_section(title: str, subtitle: str = None):
    """Print a section header with sakura styling."""
    console.print()
    text = Text()
    text.append("┌─ ", style=f"bold {SAKURA_PINK}")
    text.append(title, style=f"bold {SAKURA_LIGHT}")
    console.print(text)

    if subtitle:
        console.print(f"│  [dim]{subtitle}[/dim]")
    console.print("│")


def print_option(key: str, label: str, description: str = None):
    """Print a menu option."""
    console.print(f"│")
    console.print(f"│  [bold {SAKURA_PINK}]{key}[/bold {SAKURA_PINK}]  {label}")
    if description:
        console.print(f"│      [dim]{description}[/dim]")


def print_footer():
    """Print footer line."""
    console.print("│")
    console.print(f"└─ {'─' * 50}")


# Default models for fallback
DEFAULT_OPENROUTER_MODELS = [
    "anthropic/claude-sonnet-4",
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4-turbo",
    "meta-llama/llama-3.3-70b-instruct",
]


async def _select_from_model_ids(
    model_ids: list[str],
    *,
    fallback: str,
    popular_patterns: tuple[str, ...] = (),
    max_popular: int = 5,
) -> str:
    """Arrow-key model picker over a known id list (OpenRouter-style UX).

    Small lists go straight to selection; long ones get popular shortcuts
    plus search/show-all. Never returns empty: falls back to `fallback`.
    """
    ids = list(dict.fromkeys(m for m in model_ids if m))
    if not ids:
        return fallback
    if not popular_patterns or len(ids) <= 12:
        selected = await questionary.select(
            "  Select a model:",
            choices=ids,
            style=CUSTOM_STYLE,
        ).ask_async()
        return selected or fallback

    popular = [
        m for m in ids if any(p in m.lower() for p in popular_patterns)
    ][:max_popular]

    choices = [f"🔍 Search models...", f"📋 Show all ({len(ids)} models)"]
    choices.extend(popular)

    choice = await questionary.select(
        "  Select a model:",
        choices=choices,
        style=CUSTOM_STYLE,
    ).ask_async()

    if choice is None:
        return popular[0] if popular else ids[0]
    if choice.startswith("🔍"):
        return await _search_models(ids, fallback)
    if choice.startswith("📋"):
        return await _show_all_models(ids, fallback)
    return choice


async def _select_live_model(
    label: str,
    provider_cls,
    auth: dict,
    *,
    static_ids: tuple[str, ...] | list[str] = (),
    popular_patterns: tuple[str, ...] = (),
    fallback: str,
) -> str:
    """Fetch a provider's model list (live or static fallback) then pick.

    The provider is built lazily: a missing key (allowed by onboarding)
    skips the live call and offers the known static list instead.
    """
    print_section("Choose Model", f"Fetching available {label} models...")

    ids: list[str] = []
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(f"Connecting to {label}...", total=100)
            models = await provider_cls(**auth).list_models()
            progress.update(task, completed=100, description="Done!")

        raw = [
            (m if isinstance(m, str) else (m.get("id") or m.get("name", "")))
            for m in (models or [])
        ]
        ids = [m.removeprefix("models/") for m in raw if m]
        ids = list(dict.fromkeys(ids))
    except Exception as e:
        logger.error(f"Failed to fetch {label} models: {e}")
        ids = list(static_ids)

    if not ids:
        console.print("  [yellow]! No models found, using default[/yellow]")
        return fallback

    console.print(f"\n  [green]✓[/green] Found {len(ids)} models")
    return await _select_from_model_ids(
        ids, fallback=fallback, popular_patterns=popular_patterns
    )


async def _select_openrouter_model(api_key: str = None) -> str:
    """Select OpenRouter model with arrow key navigation and search."""
    print_section("Choose Model", "Fetching available models...")

    try:
        from clawlet.providers.openrouter import OpenRouterProvider

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Connecting to OpenRouter...", total=100)

            # Use provided API key or try env var
            key = api_key or os.environ.get("OPENROUTER_API_KEY", "")

            if not key:
                console.print(
                    "  [yellow]! No API key provided, using default models[/yellow]"
                )
                return await _use_default_models()

            provider = OpenRouterProvider(api_key=key)
            models = await provider.list_models()
            progress.update(task, completed=100, description="Done!")

        if not models:
            console.print("  [yellow]! Failed to fetch models, using defaults[/yellow]")
            return await _use_default_models()

        console.print(f"\n  [green]✓[/green] Found {len(models)} models")

        # Extract model IDs
        model_ids = [m.get("id", "Unknown") for m in models if m.get("id")]

        return await _select_from_model_ids(
            model_ids,
            fallback=DEFAULT_OPENROUTER_MODELS[0],
            popular_patterns=(
                "anthropic/claude",
                "openai/gpt-4",
                "openai/gpt-4o",
                "meta-llama/llama",
                "google/gemini",
                "mistral/mistral",
            ),
        )

    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
        console.print(f"  [yellow]! Using default models list[/yellow]")
        return await _use_default_models()


async def _search_models(model_ids: list[str], fallback: str) -> str:
    """Search and select from available models with arrow key navigation."""
    console.print()
    search_term = await questionary.text(
        "  🔍 Search models (leave empty to browse all):",
        style=CUSTOM_STYLE,
    ).ask_async()

    if search_term:
        # Filter models by search term (case-insensitive, partial match)
        filtered = [m for m in model_ids if search_term.lower() in m.lower()]

        if not filtered:
            console.print(
                f"  [yellow]! No models found matching '{search_term}'[/yellow]"
            )

            # Offer to show all models instead
            retry = await questionary.confirm(
                "  Show all available models instead?",
                default=True,
                style=CUSTOM_STYLE,
            ).ask_async()

            if retry:
                return await _show_all_models(model_ids, fallback)
            else:
                return fallback

        console.print(f"\n  [green]✓[/green] [{len(filtered)} models found]")

        # Use select with arrow key navigation
        selected = await questionary.select(
            "  Select a model:",
            choices=filtered,
            style=CUSTOM_STYLE,
        ).ask_async()

        return selected if selected else fallback

    # If no search term, show all models
    return await _show_all_models(model_ids, fallback)


async def _show_all_models(model_ids: list[str], fallback: str) -> str:
    """Show all available models with arrow key navigation."""
    console.print(f"\n  [[{len(model_ids)} models available]]")

    # Use select with arrow key navigation for all models
    selected = await questionary.select(
        "  Select a model:",
        choices=model_ids,
        style=CUSTOM_STYLE,
    ).ask_async()

    return selected if selected else fallback


async def _use_default_models() -> str:
    """Use default model selection with arrow key navigation."""
    print_section("Choose Model", "Using default models (API unavailable)")

    # Use select with arrow key navigation
    selected = await questionary.select(
        "  Select a model:",
        choices=DEFAULT_OPENROUTER_MODELS,
        style=CUSTOM_STYLE,
    ).ask_async()

    return selected if selected else DEFAULT_OPENROUTER_MODELS[0]


async def _select_lmstudio_model(base_url: str = "http://localhost:1234") -> str:
    """
    Select LM Studio model with interactive selection UI.

    Connects to LM Studio and fetches available models, allowing
    the user to select from downloaded models.

    Args:
        base_url: LM Studio server URL

    Returns:
        Selected model name or default
    """
    print_section("Choose Model", "Fetching available models...")

    try:
        from clawlet.providers.lmstudio import LMStudioProvider

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Connecting to LM Studio...", total=100)

            provider = LMStudioProvider(base_url=base_url)
            models = await provider.list_models_detailed()
            await provider.close()
            progress.update(task, completed=100, description="Done!")

        if not models:
            console.print(
                "  [yellow]! No models found. Make sure you have downloaded models in LM Studio.[/yellow]"
            )
            return await _use_default_lmstudio_model()

        console.print(f"\n  [green]✓[/green] Found {len(models)} models")

        # Format model choices with useful info
        choices = []
        for model in models:
            model_id = model.get("id", "Unknown")
            model_type = model.get("type", "?")
            quantization = model.get("quantization", "?")
            max_ctx = model.get("max_context_length", 0)

            # Format display string
            if max_ctx:
                ctx_str = f"{max_ctx // 1024}K"
            else:
                ctx_str = "?"

            display = f"{model_id} [{model_type} | {quantization} | {ctx_str}]"
            choices.append(display)

        # Allow user to select
        selected = await questionary.select(
            "  Select a model:",
            choices=choices,
            style=CUSTOM_STYLE,
        ).ask_async()

        if selected:
            # Extract just the model ID from the display string
            model_id = selected.split(" [")[0]
            return model_id

        return "local-model"

    except Exception as e:
        logger.error(f"Failed to fetch LM Studio models: {e}")
        console.print(f"  [yellow]! Error connecting to LM Studio: {e}[/yellow]")
        return await _use_default_lmstudio_model()


async def _use_default_lmstudio_model() -> str:
    """Use default model selection for LM Studio."""
    print_section("Choose Model", "Using default model name")

    # Use select with common model names as suggestions
    common_models = [
        "local-model",
        "llama3.2",
        "mistral",
        "phi3",
        "qwen2",
    ]

    selected = await questionary.select(
        "  Select a model:",
        choices=common_models,
        style=CUSTOM_STYLE,
    ).ask_async()

    return selected if selected else "local-model"


_PROVIDER_IDS = (
    "openrouter",
    "openai",
    "anthropic",
    "minimax",
    "moonshot",
    "google",
    "qwen",
    "zai",
    "copilot",
    "vercel",
    "opencode_zen",
    "xiaomi",
    "synthetic",
    "venice",
    "ollama",
    "lmstudio",
)

_PROVIDER_CHOICES = {str(i + 1): pid for i, pid in enumerate(_PROVIDER_IDS)}


async def run_onboarding(workspace: Optional[Path] = None) -> Config:
    """
    Run interactive onboarding flow with unique UI.
    """
    workspace = workspace or get_default_workspace_path()

    steps = [
        "Provider",
        "API Key",
        "Web Search",
        "Identity",
        "Execution Mode",
        "Task Models",
        "Create",
    ]

    # Welcome screen
    print_sakura_header()
    console.print()
    console.print(f"[bold]Welcome to Clawlet![/bold] Let's set up your AI agent.")
    console.print(
        "[dim]This takes about 2 minutes. Press Ctrl+C to cancel anytime.[/dim]"
    )

    await asyncio.sleep(0.5)

    # Check existing workspace
    existing = workspace.exists()
    if existing:
        console.print()
        console.print(f"[yellow]! Workspace already exists at {workspace}[/yellow]")
        overwrite = await questionary.confirm(
            "Overwrite existing configuration?",
            default=False,
            style=CUSTOM_STYLE,
        ).ask_async()
        if not overwrite:
            console.print("[dim]Keeping existing configuration.[/dim]")
            return Config.from_yaml(workspace / "config.yaml")

    # ============================================
    # Step 1: Choose Provider
    # ============================================
    print_step_indicator(1, 7, steps)
    print_section(
        "Choose Your AI Provider", "Where should your agent get its intelligence?"
    )

    print_option("1", "OpenRouter", "Cloud API - Best models")
    print_option("2", "OpenAI", "Direct GPT-5 access")
    print_option("3", "Anthropic", "Direct Claude access")
    print_option("4", "MiniMax", "Chinese - abab7")
    print_option("5", "Moonshot AI", "Kimi K2.5")
    print_option("6", "Google", "Gemini 4 Pro")
    print_option("7", "Qwen", "Alibaba - Qwen4")
    print_option("8", "Z.AI", "GLM-5")
    print_option("9", "Copilot", "GitHub OAuth")
    print_option("10", "Vercel", "AI Gateway")
    print_option("11", "OpenCode Zen", "Zen 3.0")
    print_option("12", "Xiaomi", "Mi Agent 2")
    print_option("13", "Synthetic", "Privacy-focused")
    print_option("14", "Venice AI", "Uncensored")
    print_option("15", "Ollama", "Local - Free")
    print_option("16", "LM Studio", "Local - Free")
    print_footer()

    choice = Prompt.ask(
        "\n  Select",
        choices=[
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
        ],
        default="1",
    )

    provider_choice = _PROVIDER_CHOICES[choice]
    console.print(f"  [green]✓[/green] Selected: [bold]{provider_choice}[/bold]")

    provider_config = None

    # ============================================
    # Step 2: Configure Provider
    # ============================================
    print_step_indicator(2, 7, steps)

    if provider_choice == "openrouter":
        print_section("OpenRouter API Key", "Get your key at openrouter.ai/keys")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        model = await _select_openrouter_model(api_key=api_key)

        provider_config = ProviderConfig(
            primary="openrouter",
            openrouter=OpenRouterConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "ollama":
        print_section("Ollama Setup", "Local AI running on your machine")
        console.print("│")
        console.print("│  [dim]Make sure Ollama is running: ollama serve[/dim]")
        console.print("│  [dim]Install from: ollama.ai[/dim]")
        console.print("│")

        from clawlet.providers.ollama import OllamaProvider

        ollama_models = await OllamaProvider().list_models()
        if ollama_models:
            console.print("│  [green]✓ Ollama is running[/green]")
            print_footer()
            model = await _select_from_model_ids(
                ollama_models, fallback="llama3.2"
            )
        else:
            console.print("│  [yellow]! Could not connect to Ollama[/yellow]")
            print_footer()
            model = Prompt.ask("\n  Model name", default="llama3.2")
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="ollama",
            ollama=OllamaConfig(model=model),
        )

    elif provider_choice == "lmstudio":
        print_section("LM Studio Setup", "Local AI with GUI")
        console.print("│")
        console.print("│  [dim]Make sure LM Studio server is running (port 1234)[/dim]")
        console.print("│  [dim]Download models from the LM Studio app first[/dim]")
        console.print("│")

        # Check if LM Studio is running and fetch models
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await asyncio.wait_for(
                    client.get("http://localhost:1234/api/v1/models"), timeout=2.0
                )
                response.raise_for_status()
                console.print("│  [green]✓ LM Studio is running[/green]")

                # Fetch available models
                model = await _select_lmstudio_model()
                console.print(f"│  [green]✓[/green] Model: [bold]{model}[/bold]")

        except:
            console.print("│  [yellow]! Could not connect to LM Studio[/yellow]")
            console.print(
                "│  [dim]Using default model name (will auto-detect when connected)[/dim]"
            )
            model = "local-model"

        provider_config = ProviderConfig(
            primary="lmstudio",
            lmstudio=LMStudioConfig(model=model),
        )
        console.print("│  [green]✓ LM Studio configured[/green]")
        print_footer()

    elif provider_choice == "openai":
        print_section("OpenAI API Key", "Get your key at platform.openai.com/api-keys")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.openai import OPENAI_MODELS, OpenAIProvider

        model = await _select_live_model(
            "OpenAI",
            OpenAIProvider,
            {"api_key": api_key},
            static_ids=OPENAI_MODELS,
            popular_patterns=("gpt-4o", "gpt-5", "o3", "o4"),
            fallback="gpt-5",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="openai",
            openai=OpenAIConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "anthropic":
        print_section("Anthropic API Key", "Get your key at console.anthropic.com")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.anthropic import ANTHROPIC_MODELS, AnthropicProvider

        model = await _select_live_model(
            "Anthropic",
            AnthropicProvider,
            {"api_key": api_key},
            static_ids=ANTHROPIC_MODELS,
            fallback="claude-sonnet-5-20260203",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="anthropic",
            anthropic=AnthropicConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "minimax":
        print_section("MiniMax API Key", "Get your key at minimax.chat")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.minimax import MiniMaxProvider

        model = await _select_live_model(
            "MiniMax",
            MiniMaxProvider,
            {"api_key": api_key},
            static_ids=MiniMaxProvider.DEFAULT_MODELS,
            fallback="abab7-preview",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="minimax",
            minimax=MiniMaxConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "moonshot":
        print_section("Moonshot AI API Key", "Get your key at moonshot.ai")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.moonshot import MoonshotProvider

        model = await _select_live_model(
            "Moonshot AI",
            MoonshotProvider,
            {"api_key": api_key},
            static_ids=MoonshotProvider.DEFAULT_MODELS,
            fallback="kimi-k2.5",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="moonshot",
            moonshot=MoonshotConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "google":
        print_section("Google API Key", "Get your key at aistudio.google.com")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.google import GOOGLE_MODELS, GoogleProvider

        model = await _select_live_model(
            "Google",
            GoogleProvider,
            {"api_key": api_key},
            static_ids=GOOGLE_MODELS,
            popular_patterns=("gemini-4", "gemini-3"),
            fallback="gemini-4-pro",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="google",
            google=GoogleConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "qwen":
        print_section("Qwen API Key", "Get your key from Alibaba Cloud")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.qwen import QwenProvider

        model = await _select_live_model(
            "Qwen",
            QwenProvider,
            {"api_key": api_key},
            static_ids=QwenProvider.DEFAULT_MODELS,
            fallback="qwen4",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="qwen",
            qwen=QwenConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "zai":
        print_section("Z.AI API Key", "Get your key at z.ai")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.zai import ZAIProvider

        model = await _select_live_model(
            "Z.AI",
            ZAIProvider,
            {"api_key": api_key},
            static_ids=ZAIProvider.DEFAULT_MODELS,
            fallback="glm-5",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="zai",
            zai=ZAIConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "copilot":
        print_section(
            "GitHub Copilot Token", "Get your token at github.com/settings/tokens"
        )
        console.print("│")
        console.print("│  [dim]Required scopes: repo, read:user[/dim]")
        console.print("│")

        access_token = await questionary.password(
            "  Enter your GitHub access token:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not access_token:
            console.print(
                "  [yellow]! No token provided, you'll need to add it later[/yellow]"
            )
            access_token = ""
        else:
            console.print("  [green]✓[/green] Token saved")

        console.print()
        from clawlet.providers.copilot import CopilotProvider

        model = await _select_live_model(
            "GitHub Copilot",
            CopilotProvider,
            {"access_token": access_token},
            static_ids=CopilotProvider.DEFAULT_MODELS,
            fallback="gpt-4.2",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="copilot",
            copilot=CopilotConfig(access_token=access_token, model=model),
        )

    elif provider_choice == "vercel":
        print_section("Vercel API Key", "Get your key at vercel.com/settings/tokens")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.vercel import VercelProvider

        model = await _select_live_model(
            "Vercel",
            VercelProvider,
            {"api_key": api_key},
            static_ids=VercelProvider.DEFAULT_MODELS,
            fallback="openai/gpt-5",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="vercel",
            vercel=VercelConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "opencode_zen":
        print_section("OpenCode Zen API Key", "Get your key at opencode.ai")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.opencode_zen import OpenCodeZenProvider

        model = await _select_live_model(
            "OpenCode Zen",
            OpenCodeZenProvider,
            {"api_key": api_key},
            static_ids=OpenCodeZenProvider.DEFAULT_MODELS,
            fallback="zen-3.0",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="opencode_zen",
            opencode_zen=OpenCodeZenConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "xiaomi":
        print_section("Xiaomi API Key", "Get your key at mi.com")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.xiaomi import XiaomiProvider

        model = await _select_live_model(
            "Xiaomi",
            XiaomiProvider,
            {"api_key": api_key},
            static_ids=XiaomiProvider.DEFAULT_MODELS,
            fallback="mi-agent-2",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="xiaomi",
            xiaomi=XiaomiConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "synthetic":
        print_section("Synthetic API Key", "Get your key at synthetic.ai")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.synthetic import SyntheticProvider

        model = await _select_live_model(
            "Synthetic",
            SyntheticProvider,
            {"api_key": api_key},
            static_ids=SyntheticProvider.DEFAULT_MODELS,
            fallback="synthetic-llm-2",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="synthetic",
            synthetic=SyntheticConfig(api_key=api_key, model=model),
        )

    elif provider_choice == "venice":
        print_section("Venice AI API Key", "Get your key at venice.ai")
        console.print("│")

        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()

        if not api_key:
            console.print(
                "  [yellow]! No key provided, you'll need to add it later[/yellow]"
            )
            api_key = ""
        else:
            console.print("  [green]✓[/green] Key saved")

        console.print()
        from clawlet.providers.venice import VeniceProvider

        model = await _select_live_model(
            "Venice AI",
            VeniceProvider,
            {"api_key": api_key},
            static_ids=VeniceProvider.DEFAULT_MODELS,
            fallback="venice-llama-4",
        )
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")

        provider_config = ProviderConfig(
            primary="venice",
            venice=VeniceAIConfig(api_key=api_key, model=model),
        )

    # ============================================
    # Step 3: Brave Search API (Optional)
    # ============================================
    print_step_indicator(3, 7, steps)
    print_section("Web Search", "Enable web search for your agent?")

    brave_use = await questionary.confirm(
        "  Use Brave Search API for web searches?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask_async()

    brave_api_key = None
    if brave_use:
        console.print("│  [dim]Get your free key at brave.com/search/api[/dim]")
        brave_api_key = await questionary.password(
            "  Enter your Brave Search API key:",
            style=CUSTOM_STYLE,
        ).ask_async()
        if brave_api_key:
            console.print("  [green]✓[/green] Brave Search configured")

    # ============================================
    # Step 4: Agent Identity
    # ============================================
    print_step_indicator(4, 7, steps)
    print_section("Agent Identity", "Give your agent a personality")
    console.print("│")

    agent_name = Prompt.ask("  │  Name your agent", default="Clawlet")
    console.print(f"  │  [green]✓[/green] Name: [bold]{agent_name}[/bold]")

    console.print("│")
    console.print("│  [dim]Describe your agent in a few words (optional)[/dim]")
    console.print("│  [dim]e.g., 'friendly helper with a dry sense of humor'[/dim]")
    console.print("│")

    personality = await questionary.text(
        "  Personality:",
        style=CUSTOM_STYLE,
    ).ask_async()

    if personality:
        console.print(f"  [green]✓[/green] Custom personality set")

    print_footer()

    # ============================================
    # Step 5: Execution Mode
    # ============================================
    print_step_indicator(5, 7, steps)
    print_section("Execution Mode", "Choose capability level for your agent")
    console.print("│")
    print_option("s", "safe", "Workspace-restricted tools (recommended)")
    print_option("f", "full_exec", "Machine-wide tool access (advanced)")
    print_footer()

    mode_choice = Prompt.ask("\n  Select", choices=["s", "f"], default="s")
    agent_mode = "full_exec" if mode_choice == "f" else "safe"
    shell_allow_dangerous = True if mode_choice == "f" else False

    if agent_mode == "full_exec":
        console.print(
            "\n  [yellow]! full_exec grants broad machine capabilities[/yellow]"
        )
        shell_allow_dangerous = await questionary.confirm(
            "  Also allow dangerous shell patterns?",
            default=False,
            style=CUSTOM_STYLE,
        ).ask_async()
        console.print(
            f"  [green]✓[/green] Mode: [bold]{agent_mode}[/bold], "
            f"dangerous shell patterns: {'enabled' if shell_allow_dangerous else 'disabled'}"
        )

    # ============================================
    # Step 7: Per-Task Models
    # ============================================
    print_step_indicator(6, 7, steps)
    print_section(
        "Models Per Task", "Optionally give each task type its own provider and model"
    )
    console.print("│")
    console.print("  [dim]Blank = inherit the primary provider everywhere.[/dim]")
    print_footer()

    task_profiles = {}
    customize = await questionary.confirm(
        "  Customize models per task type?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask_async()
    if customize:
        kinds = (
            await questionary.checkbox(
                "  Which task types?",
                choices=list(TASK_KINDS),
                style=CUSTOM_STYLE,
            ).ask_async()
            or []
        )
        for kind in kinds:
            provider = await questionary.select(
                f"  [{kind}] provider (same = primary [{provider_choice}])",
                choices=["same"] + list(_PROVIDER_IDS),
                default="same",
                style=CUSTOM_STYLE,
            ).ask_async()
            model = await questionary.text(
                f"  [{kind}] model (blank = provider default):",
                style=CUSTOM_STYLE,
            ).ask_async()
            task_profiles[kind] = TaskProfile(
                provider="" if provider in (None, "same") else str(provider),
                model=(model or "").strip(),
            )
            console.print(
                f"  [green]✓[/green] {kind}: {provider} / {model or 'default'}"
            )

    # ============================================
    # Step 8: Create Workspace
    # ============================================
    print_step_indicator(7, 7, steps)
    print_section("Creating Workspace", "Setting up your files...")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(
            bar_width=40, complete_style=f"{SAKURA_PINK}", finished_style="green"
        ),
        transient=True,
    ) as progress:
        task = progress.add_task("Creating directories...", total=5)

        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "memory").mkdir(exist_ok=True)
        progress.update(task, advance=1, description="Writing config...")

        config = Config(
            provider=provider_config,
            agent=AgentSettings(
                mode=agent_mode, shell_allow_dangerous=shell_allow_dangerous
            ),
            task_profiles=task_profiles,
            web_search=BraveSearchConfig(
                api_key=brave_api_key if brave_api_key else "",
                enabled=bool(brave_api_key),
            )
            if brave_use
            else BraveSearchConfig(),
        )
        config.save(workspace / "config.yaml")
        progress.update(task, advance=1, description="Creating identity files...")

        create_identity_files(
            workspace,
            agent_name=agent_name,
            personality=personality,
        )
        progress.update(task, advance=1, description="Finalizing...")
        await asyncio.sleep(0.3)
        progress.update(task, advance=2, description="Done!")

    # ============================================
    # Done!
    # ============================================
    print_sakura_header()

    console.print()
    console.print(f"[bold green]✓ Setup Complete![/bold green]")
    console.print()
    console.print(f"  Workspace: [{SAKURA_PINK}]{workspace}[/{SAKURA_PINK}]")
    console.print()

    console.print("[bold]Quick Start:[/bold]")
    console.print(f"  1. Review [{SAKURA_PINK}]{workspace}/config.yaml[/{SAKURA_PINK}]")
    console.print(
        f"  2. Run [{SAKURA_PINK}]clawlet validate[/{SAKURA_PINK}] to verify the setup"
    )
    console.print(
        f"  3. Run [{SAKURA_PINK}]clawlet agent[/{SAKURA_PINK}] to start your agent"
    )
    console.print()

    console.print("[bold]Commands:[/bold]")
    console.print(
        f"  [{SAKURA_PINK}]clawlet --help[/{SAKURA_PINK}]     Show all commands"
    )
    console.print(
        f"  [{SAKURA_PINK}]clawlet health[/{SAKURA_PINK}]    Check your setup"
    )
    console.print(
        f"  [{SAKURA_PINK}]clawlet validate[/{SAKURA_PINK}]  Validate configuration"
    )
    console.print()
    console.print(f"[dim]🌸 Docs: https://github.com/Kxrbx/Clawlet[/dim]")
    console.print()

    return config


def create_identity_files(
    workspace: Path,
    agent_name: str = "Clawlet",
    personality: str = None,
):
    """Create identity files in workspace."""

    # SOUL.md
    soul_content = f"""# SOUL.md - Who You Are

## Name
{agent_name}

## Personality
{personality or "I am a helpful, friendly AI assistant. I communicate clearly and warmly, and I'm eager to help with any task."}

## Values
1. **Helpfulness**: I strive to provide genuinely useful assistance
2. **Honesty**: I'm truthful about my capabilities and limitations  
3. **Privacy**: I respect your data and never share it inappropriately
4. **Growth**: I learn from our interactions to become better

## Communication Style
- Be warm and supportive
- Be direct when needed, gentle when appropriate
- Ask clarifying questions when uncertain
- Celebrate wins together

---
🌸 _This file is yours to customize. Make your agent unique!_
"""
    (workspace / "SOUL.md").write_text(soul_content, encoding="utf-8")

    # USER.md
    (workspace / "USER.md").write_text(
        "# USER.md - About Your Human\n\n## Name\n[Your name]\n\n## What to call you\n[Preferred name/nickname]\n\n## Timezone\n[Your timezone, e.g., UTC, America/New_York]\n\n## Notes\n- What do you care about?\n- What projects are you working on?\n- What makes you laugh?\n\n---\n🌸 _The more your agent knows, the better it can help!_\n",
        encoding="utf-8",
    )

    # MEMORY.md
    (workspace / "MEMORY.md").write_text(
        "# MEMORY.md - Long-Term Memory\n\n## Key Information\n- Add important facts here\n- Decisions made\n- Lessons learned\n\n## Recent Updates\n- [Date] Initial setup\n\n---\n🌸 _Memories persist across sessions._\n",
        encoding="utf-8",
    )

    # HEARTBEAT.md
    (workspace / "HEARTBEAT.md").write_text(
        "# HEARTBEAT.md\n\n# Keep this file empty (or with only comments) to skip heartbeat API calls.\n\n# Add tasks below when you want the agent to check something periodically.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(run_onboarding())
