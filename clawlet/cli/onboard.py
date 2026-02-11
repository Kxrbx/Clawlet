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

from clawlet.config import Config, ProviderConfig, OpenRouterConfig, OllamaConfig, LMStudioConfig


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

[cyan]   ██████╗██╗      ██████╗ ██╗   ██╗██████╗  █████╗ ██╗    ██╗
  ██╔════╝██║     ██╔═══██╗██║   ██║██╔══██╗██╔══██╗██║    ██║
  ██║     ██║     ██║   ██║██║   ██║██║  ██║███████║██║ █╗ ██║
  ██║     ██║     ██║   ██║██║   ██║██║  ██║██╔══██║██║███╗██║
  ╚██████╗███████╗╚██████╔╝╚██████╔╝██████╔╝██║  ██║╚███╔███╔╝
   ╚═════╝╚══════╝ ╚═════╝  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝ ╚══╝╚══╝[/cyan]

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


async def run_onboarding(workspace: Optional[Path] = None) -> Config:
    """
    Run interactive onboarding flow with unique UI.
    """
    workspace = workspace or Path.home() / ".clawlet"
    
    steps = [
        "Provider",
        "API Key",
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
        overwrite = questionary.confirm(
            "Overwrite existing configuration?",
            default=False,
            style=CUSTOM_STYLE,
        ).ask()
        if not overwrite:
            console.print("[dim]Keeping existing configuration.[/dim]")
            return Config.from_yaml(workspace / "config.yaml")
    
    # ============================================
    # Step 1: Choose Provider
    # ============================================
    print_step_indicator(1, 5, steps)
    print_section("Choose Your AI Provider", "Where should your agent get its intelligence?")
    
    print_option("1", "OpenRouter", "Cloud API - Best models, requires API key")
    print_option("2", "Ollama", "Local - Free, runs on your machine")
    print_option("3", "LM Studio", "Local - Free, runs on your machine")
    print_footer()
    
    choice = Prompt.ask(
        "\n  Select",
        choices=["1", "2", "3"],
        default="1",
    )
    
    provider_choice = {"1": "openrouter", "2": "ollama", "3": "lmstudio"}[choice]
    console.print(f"  [green]✓[/green] Selected: [bold]{provider_choice}[/bold]")
    
    provider_config = None
    
    # ============================================
    # Step 2: Configure Provider
    # ============================================
    print_step_indicator(2, 5, steps)
    
    if provider_choice == "openrouter":
        print_section("OpenRouter API Key", "Get your key at openrouter.ai/keys")
        console.print("│")
        
        api_key = questionary.password(
            "  Enter your API key:",
            style=CUSTOM_STYLE,
        ).ask()
        
        if not api_key:
            console.print("  [yellow]! No key provided, you'll need to add it later[/yellow]")
            api_key = "YOUR_OPENROUTER_API_KEY"
        else:
            console.print("  [green]✓[/green] Key saved")
        
        console.print()
        print_section("Choose Model", "Which AI model should power your agent?")
        print_option("1", "claude-sonnet-4", "Recommended - Fast and capable")
        print_option("2", "claude-3.5-sonnet", "Previous generation")
        print_option("3", "gpt-4-turbo", "OpenAI's best")
        print_option("4", "llama-3.3-70b", "Meta's open model")
        print_footer()
        
        model_choice = Prompt.ask("\n  Select", choices=["1", "2", "3", "4"], default="1")
        models = {
            "1": "anthropic/claude-sonnet-4",
            "2": "anthropic/claude-3.5-sonnet",
            "3": "openai/gpt-4-turbo",
            "4": "meta-llama/llama-3.3-70b-instruct",
        }
        model = models[model_choice]
        console.print(f"  [green]✓[/green] Model: [bold]{model}[/bold]")
        
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
                if response.status_code == 200:
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
    
    # ============================================
    # Step 3: Channel Setup
    # ============================================
    print_step_indicator(3, 5, steps)
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
        telegram_token = questionary.password(
            "  Telegram bot token:",
            style=CUSTOM_STYLE,
        ).ask()
        if telegram_token:
            console.print("  [green]✓[/green] Telegram configured")
    
    if channel_choice in ["d", "b"]:
        console.print()
        console.print("  [dim]Create a bot in Discord Developer Portal[/dim]")
        discord_token = questionary.password(
            "  Discord bot token:",
            style=CUSTOM_STYLE,
        ).ask()
        if discord_token:
            console.print("  [green]✓[/green] Discord configured")
    
    # ============================================
    # Step 4: Agent Identity
    # ============================================
    print_step_indicator(4, 5, steps)
    print_section("Agent Identity", "Give your agent a personality")
    console.print("│")
    
    agent_name = Prompt.ask("  │  Name your agent", default="Clawlet")
    console.print(f"  │  [green]✓[/green] Name: [bold]{agent_name}[/bold]")
    
    console.print("│")
    console.print("│  [dim]Describe your agent in a few words (optional)[/dim]")
    console.print("│  [dim]e.g., 'friendly helper with a dry sense of humor'[/dim]")
    console.print("│")
    
    personality = questionary.text(
        "  Personality:",
        style=CUSTOM_STYLE,
    ).ask()
    
    if personality:
        console.print(f"  [green]✓[/green] Custom personality set")
    
    print_footer()
    
    # ============================================
    # Step 5: Create Workspace
    # ============================================
    print_step_indicator(5, 5, steps)
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
        
        config = Config(provider=provider_config)
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
    (workspace / "SOUL.md").write_text(soul_content)
    
    # USER.md
    (workspace / "USER.md").write_text("""# USER.md - About Your Human

## Name
[Your name]

## What to call you
[Preferred name/nickname]

## Timezone
[Your timezone, e.g., UTC, America/New_York]

## Notes
- What do you care about?
- What projects are you working on?
- What makes you laugh?

---
🌸 _The more your agent knows, the better it can help!_
""")
    
    # MEMORY.md
    (workspace / "MEMORY.md").write_text("""# MEMORY.md - Long-Term Memory

## Key Information
- Add important facts here
- Decisions made
- Lessons learned

## Recent Updates
- [Date] Initial setup

---
🌸 _Memories persist across sessions._
""")
    
    # HEARTBEAT.md
    (workspace / "HEARTBEAT.md").write_text("""# HEARTBEAT.md - Periodic Tasks

## Check Interval
Every 2 hours

## Tasks
- [ ] Check for important updates
- [ ] Review recent activity
## Quiet Hours
2am - 9am UTC

---
🌸 _Heartbeats help your agent stay proactive._
""")
    
    # Update config with channel tokens
    if telegram_token or discord_token:
        import yaml
        config_path = workspace / "config.yaml"
        
        with open(config_path) as f:
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
