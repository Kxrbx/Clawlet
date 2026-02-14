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

from clawlet.config import Config, ProviderConfig, OpenRouterConfig, OllamaConfig, LMStudioConfig, OpenAIConfig, AnthropicConfig, MiniMaxConfig, MoonshotConfig, GoogleConfig, QwenConfig, ZAIConfig, CopilotConfig, VercelConfig, OpenCodeZenConfig, XiaomiConfig, SyntheticConfig, VeniceAIConfig, BraveSearchConfig


# Sakura pink color scheme
SAKURA_PINK = "#FF69B4"
SAKURA_LIGHT = "#FFB7C5"
SAKURA_DARK = "#DB7093"

# Custom style for questionary - sakura theme
CUSTOM_STYLE = Style([
    ('qmark', f'fg:{SAKURA_PINK} bold'),
    ('question', 'bold'),
    ('answer', f'fg:{SAKURA_DARK} bold'),
    ('pointer', f'fg:{SAKURA_PINK} bold'),
    ('highlighted', f'fg:{SAKURA_PINK} bold'),
    ('selected', f'fg:{SAKURA_LIGHT}'),
    ('separator', f'fg:{SAKURA_DARK}'),
    ('instruction', 'fg:#8d8d8d'),
    ('text', ''),
])


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
                console.print("  [yellow]! No API key provided, using default models[/yellow]")
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
        
        # Show top 10 popular models
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
            if len(popular) >= 10:
                break
        
        # Create choices with search option
        choices = ["🔍 Search models...", f"📋 Show all ({len(models)} models)"]
        if popular:
            choices.extend(popular[:5])
        
        choice = await questionary.select(
            "  Select a model:",
            choices=choices,
            style=CUSTOM_STYLE,
        ).ask_async()
        
        if choice.startswith("🔍"):
            return await _search_models(models, model_ids)
        elif choice.startswith("📋"):
            return await _show_all_models(models, model_ids)
        elif choice in popular[:5]:
            return choice
        else:
            # Default to first popular model
            return popular[0] if popular else model_ids[0] if model_ids else DEFAULT_OPENROUTER_MODELS[0]
            
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
        console.print(f"  [yellow]! Using default models list[/yellow]")
        return await _use_default_models()


async def _search_models(models: list, model_ids: list = None) -> str:
    """Search and select from available models with arrow key navigation."""
    if model_ids is None:
        model_ids = [m.get("id", "Unknown") for m in models if m.get("id")]
    
    console.print()
    search_term = await questionary.text(
        "  🔍 Search models (leave empty to browse all):",
        style=CUSTOM_STYLE,
    ).ask_async()
    
    if search_term:
        # Filter models by search term (case-insensitive, partial match)
        filtered = [m for m in model_ids if search_term.lower() in m.lower()]
        
        if not filtered:
            console.print(f"  [yellow]! No models found matching '{search_term}'[/yellow]")
            
            # Offer to show all models instead
            retry = await questionary.confirm(
                "  Show all available models instead?",
                default=True,
                style=CUSTOM_STYLE,
            ).ask_async()
            
            if retry:
                return await _show_all_models(models, model_ids)
            else:
                return DEFAULT_OPENROUTER_MODELS[0]
        
        console.print(f"\n  [green]✓[/green] [{len(filtered)} models found]")
        
        # Use select with arrow key navigation
        selected = await questionary.select(
            "  Select a model:",
            choices=filtered,
            style=CUSTOM_STYLE,
        ).ask_async()
        
        return selected if selected else DEFAULT_OPENROUTER_MODELS[0]
    
    # If no search term, show all models
    return await _show_all_models(models, model_ids)


async def _show_all_models(models: list, model_ids: list = None) -> str:
    """Show all available models with arrow key navigation."""
    if model_ids is None:
        model_ids = [m.get("id", "Unknown") for m in models if m.get("id")]
    
    console.print(f"\n  [[{len(model_ids)} models available]]")
    
    # Use select with arrow key navigation for all models
    selected = await questionary.select(
        "  Select a model:",
        choices=model_ids,
        style=CUSTOM_STYLE,
    ).ask_async()
    
    return selected if selected else DEFAULT_OPENROUTER_MODELS[0]


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


async def run_onboarding(workspace: Optional[Path] = None) -> Config:
    """
    Run interactive onboarding flow with unique UI.
    """
    workspace = workspace or Path.home() / ".clawlet"
    
    steps = [
        "Provider",
        "API Key",
        "Web Search",
        "Channel",
        "Identity",
        "Create",
    ]
    
    # Welcome screen
    print_sakura_header()
    console.print()
    console.print(f"[bold]Welcome to Clawlet![/bold] Let's set up your AI agent.")
    console.print("[dim]This takes about 2 minutes. Press Ctrl+C to cancel anytime.[/dim]")
    
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
    print_step_indicator(1, 5, steps)
    print_section("Choose Your AI Provider", "Where should your agent get its intelligence?")
    
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
        choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16"],
        default="1",
    )
    
    provider_choice = {
        "1": "openrouter",
        "2": "openai",
        "3": "anthropic",
        "4": "minimax",
        "5": "moonshot",
        "6": "google",
        "7": "qwen",
        "8": "zai",
        "9": "copilot",
        "10": "vercel",
        "11": "opencode_zen",
        "12": "xiaomi",
        "13": "synthetic",
        "14": "venice",
        "15": "ollama",
        "16": "lmstudio",
    }[choice]
    console.print(f"  [green]✓[/green] Selected: [bold]{provider_choice}[/bold]")
    
    provider_config = None
    
    # ============================================
    # Step 2: Configure Provider
    # ============================================
    print_step_indicator(2, 5, steps)
    
    if provider_choice == "openrouter":
        print_section("OpenRouter API Key", "Get your key at openrouter.ai/keys")
        console.print("│")
        
        api_key = await questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask_async()
        
        if not api_key:
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_OPENROUTER_API_KEY"
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
        
        # Check if running
        print("│  [dim]Checking connection...[/dim]")
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await asyncio.wait_for(
                    client.get("http://localhost:11434/api/tags"),
                    timeout=2.0
                )
                response.raise_for_status()
                console.print("│  [green]✓ Ollama is running[/green]")
        except:
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
        console.print("│")
        
        provider_config = ProviderConfig(
            primary="lmstudio",
            lmstudio=LMStudioConfig(),
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_OPENAI_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="gpt-5")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_ANTHROPIC_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="claude-sonnet-5-20260203")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_MINIMAX_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="abab7-preview")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_MOONSHOT_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="kimi-k2.5")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_GOOGLE_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="gemini-4-pro")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_QWEN_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="qwen4")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_ZAI_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="glm-5")
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")
        
        provider_config = ProviderConfig(
            primary="zai",
            zai=ZAIConfig(api_key=api_key, model=model),
        )
        
    elif provider_choice == "copilot":
        print_section("GitHub Copilot Token", "Get your token at github.com/settings/tokens")
        console.print("│")
        console.print("│  [dim]Required scopes: repo, read:user[/dim]")
        console.print("│")
        
        access_token = await questionary.password(
            "  Enter your GitHub access token:",
            style=CUSTOM_STYLE,
        ).ask_async()
        
        if not access_token:
            console.print("  [yellow]! No token provided, you'll need to add it later[/yellow]")
            access_token = "YOUR_GITHUB_ACCESS_TOKEN"
        else:
            console.print("  [green]✓[/green] Token saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="gpt-4.2")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_VERCEL_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="openai/gpt-5")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_OPENCODE_ZEN_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="zen-3.0")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_XIAOMI_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="mi-agent-2")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_SYNTHETIC_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="synthetic-llm-2")
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
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_VENICE_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        model = Prompt.ask("  Model name", default="venice-llama-4")
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")
        
        provider_config = ProviderConfig(
            primary="venice",
            venice_ai=VeniceAIConfig(api_key=api_key, model=model),
        )
    
    # ============================================
    # Step 3: Brave Search API (Optional)
    # ============================================
    print_step_indicator(3, 6, steps)
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
    # Step 4: Channel Setup
    # ============================================
    print_step_indicator(4, 6, steps)
    print_section("Messaging Channels", "Where should your agent respond?")
    console.print("│")
    console.print("│  [dim]You can skip this and set up channels later[/dim]")
    console.print("│")
    print_option("n", "Skip", "No channels right now")
    print_option("t", "Telegram", "Connect a Telegram bot")
    print_option("d", "Discord", "Connect a Discord bot")
    print_option("b", "Both", "Telegram + Discord")
    print_footer()
    
    channel_choice = Prompt.ask("\n  Select", choices=["n", "t", "d", "b"], default="n")
    
    telegram_token = None
    discord_token = None
    
    if channel_choice in ["t", "b"]:
        console.print()
        console.print("  [dim]Create a bot with @BotFather on Telegram[/dim]")
        telegram_token = await questionary.password(
            "  Telegram bot token:",
            style=CUSTOM_STYLE,
        ).ask_async()
        if telegram_token:
            console.print("  [green]✓[/green] Telegram configured")
    
    if channel_choice in ["d", "b"]:
        console.print()
        console.print("  [dim]Create a bot in Discord Developer Portal[/dim]")
        discord_token = await questionary.password(
            "  Discord bot token:",
            style=CUSTOM_STYLE,
        ).ask_async()
        if discord_token:
            console.print("  [green]✓[/green] Discord configured")
    
    # ============================================
    # Step 4: Agent Identity
    # ============================================
    print_step_indicator(5, 6, steps)
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
    # Step 5: Create Workspace
    # ============================================
    print_step_indicator(6, 6, steps)
    print_section("Creating Workspace", "Setting up your files...")
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, complete_style=f"{SAKURA_PINK}", finished_style="green"),
        transient=True,
    ) as progress:
        task = progress.add_task("Creating directories...", total=5)
        
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "memory").mkdir(exist_ok=True)
        progress.update(task, advance=1, description="Writing config...")
        
        config = Config(
            provider=provider_config,
            channels={},
            web_search=BraveSearchConfig(
                api_key=brave_api_key if brave_api_key else "",
                enabled=bool(brave_api_key),
            ) if brave_use else BraveSearchConfig()
        )
        config.to_yaml(workspace / "config.yaml")
        progress.update(task, advance=1, description="Creating identity files...")
        
        create_identity_files(
            workspace,
            agent_name=agent_name,
            personality=personality,
            telegram_token=telegram_token,
            discord_token=discord_token,
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
    console.print(f"  1. Edit [{SAKURA_PINK}]{workspace}/config.yaml[/{SAKURA_PINK}] to add API keys")
    console.print(f"  2. Run [{SAKURA_PINK}]clawlet agent[/{SAKURA_PINK}] to start your agent")
    console.print()
    
    console.print("[bold]Commands:[/bold]")
    console.print(f"  [{SAKURA_PINK}]clawlet --help[/{SAKURA_PINK}]     Show all commands")
    console.print(f"  [{SAKURA_PINK}]clawlet status[/{SAKURA_PINK}]    Check your setup")
    console.print(f"  [{SAKURA_PINK}]clawlet dashboard[/{SAKURA_PINK}]  Launch web UI")
    console.print()
    console.print(f"[dim]🌸 Docs: https://github.com/Kxrbx/Clawlet[/dim]")
    console.print()
    
    return config


def create_identity_files(
    workspace: Path,
    agent_name: str = "Clawlet",
    personality: str = None,
    telegram_token: str = None,
    discord_token: str = None,
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
    (workspace / "USER.md").write_text("# USER.md - About Your Human\n\n## Name\n[Your name]\n\n## What to call you\n[Preferred name/nickname]\n\n## Timezone\n[Your timezone, e.g., UTC, America/New_York]\n\n## Notes\n- What do you care about?\n- What projects are you working on?\n- What makes you laugh?\n\n---\n🌸 _The more your agent knows, the better it can help!_\n", encoding="utf-8")
    
    # MEMORY.md
    (workspace / "MEMORY.md").write_text("# MEMORY.md - Long-Term Memory\n\n## Key Information\n- Add important facts here\n- Decisions made\n- Lessons learned\n\n## Recent Updates\n- [Date] Initial setup\n\n---\n🌸 _Memories persist across sessions._\n", encoding="utf-8")
    
    # HEARTBEAT.md
    (workspace / "HEARTBEAT.md").write_text("# HEARTBEAT.md - Periodic Tasks\n\n## Check Interval\nEvery 2 hours\n\n## Tasks\n- [ ] Check for important updates\n- [ ] Review recent activity\n## Quiet Hours\n2am - 9am UTC\n\n---\n🌸 _Heartbeats help your agent stay proactive._\n", encoding="utf-8")
    
    # Update config with channel tokens
    if telegram_token or discord_token:
        import yaml
        config_path = workspace / "config.yaml"
        
        with open(config_path, encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if "channels" not in config_data:
            config_data["channels"] = {}
        
        if telegram_token:
            config_data["channels"]["telegram"] = {
                "enabled": True,
                "token": telegram_token,
            }
        
        if discord_token:
            config_data["channels"]["discord"] = {
                "enabled": True,
                "token": discord_token,
            }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)


if __name__ == "__main__":
    asyncio.run(run_onboarding())
