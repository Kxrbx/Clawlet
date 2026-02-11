"""
Interactive onboarding experience for Clawlet.
"""

import asyncio
from pathlib import Path
from typing import Optional
import os

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

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


def print_banner():
    """Print the Clawlet welcome banner with ASCII art."""
    banner = """
[cyan]
   ██████╗██╗      ██████╗ ██╗   ██╗██████╗  █████╗ ██╗    ██╗
  ██╔════╝██║     ██╔═══██╗██║   ██║██╔══██╗██╔══██╗██║    ██║
  ██║     ██║     ██║   ██║██║   ██║██║  ██║███████║██║ █╗ ██║
  ██║     ██║     ██║   ██║██║   ██║██║  ██║██╔══██║██║███╗██║
  ╚██████╗███████╗╚██████╔╝╚██████╔╝██████╔╝██║  ██║╚███╔███╔╝
   ╚═════╝╚══════╝ ╚═════╝  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝ ╚══╝╚══╝ 
[/cyan]
[bold magenta]🌸 A lightweight AI agent framework with identity awareness 🌸[/bold magenta]
"""
    console.print(banner)


def print_step(step: int, total: int, title: str):
    """Print a step header."""
    console.print()
    console.print(Panel(
        f"[bold magenta]Step {step}/{total}:[/bold magenta] {title}",
        style=f"bold {SAKURA_LIGHT}",
    ))


def print_success(message: str):
    """Print a success message."""
    console.print(f"  [green]✓[/green] {message}")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"  [yellow]⚠[/yellow] {message}")


def print_info(message: str):
    """Print an info message."""
    console.print(f"  [dim]→[/dim] {message}")


async def run_onboarding(workspace: Optional[Path] = None) -> Config:
    """
    Run interactive onboarding flow.
    
    Args:
        workspace: Workspace directory (defaults to ~/.clawlet)
        
    Returns:
        Config object with user's choices
    """
    workspace = workspace or Path.home() / ".clawlet"
    
    # Welcome
    print_banner()
    console.print()
    console.print("[bold]Welcome to Clawlet![/bold]")
    console.print()
    console.print("This setup will guide you through configuring your AI agent.")
    console.print("You can always change these settings later by editing the config file.")
    console.print()
    
    # Check if workspace exists
    existing = workspace.exists()
    if existing:
        console.print(f"[yellow]Workspace already exists at {workspace}[/yellow]")
        overwrite = Confirm.ask("Overwrite existing configuration?", default=False)
        if not overwrite:
            console.print("[dim]Keeping existing configuration.[/dim]")
            return Config.from_yaml(workspace / "config.yaml")
    
    total_steps = 5
    
    # ============================================
    # Step 1: Choose Provider
    # ============================================
    print_step(1, total_steps, "Choose your AI Provider")
    
    console.print()
    console.print("[dim]Clawlet supports multiple AI backends:[/dim]")
    console.print()
    
    provider_table = Table(show_header=False, box=None)
    provider_table.add_column("Option", style="cyan")
    provider_table.add_column("Description")
    
    provider_table.add_row("OpenRouter", "☁️  Cloud API - Best models, requires API key")
    provider_table.add_row("Ollama", "🏠 Local - Free, runs on your machine")
    provider_table.add_row("LM Studio", "🏠 Local - Free, runs on your machine")
    
    console.print(provider_table)
    console.print()
    
    provider_choice = questionary.select(
        "Which provider would you like to use?",
        choices=[
            questionary.Choice("OpenRouter (cloud)", value="openrouter"),
            questionary.Choice("Ollama (local)", value="ollama"),
            questionary.Choice("LM Studio (local)", value="lmstudio"),
        ],
        style=CUSTOM_STYLE,
    ).ask()
    
    if provider_choice is None:
        console.print("[red]Setup cancelled.[/red]")
        raise KeyboardInterrupt
    
    print_success(f"Selected: {provider_choice}")
    
    # ============================================
    # Step 2: Configure Provider
    # ============================================
    print_step(2, total_steps, "Configure Provider Settings")
    
    provider_config = None
    
    if provider_choice == "openrouter":
        console.print()
        console.print("[dim]OpenRouter requires an API key from https://openrouter.ai/keys[/dim]")
        console.print()
        
        api_key = questionary.password(
            "Enter your OpenRouter API key:",
            style=CUSTOM_STYLE,
        ).ask()
        
        if not api_key:
            print_warning("No API key provided. You'll need to add it manually later.")
            api_key = "YOUR_OPENROUTER_API_KEY"
        else:
            print_success("API key saved")
        
        console.print()
        console.print("[dim]Popular models:[/dim]")
        console.print("  • anthropic/claude-sonnet-4 (recommended)")
        console.print("  • anthropic/claude-3.5-sonnet")
        console.print("  • openai/gpt-4-turbo")
        console.print("  • meta-llama/llama-3.3-70b-instruct")
        console.print()
        
        model = questionary.text(
            "Which model?",
            default="anthropic/claude-sonnet-4",
            style=CUSTOM_STYLE,
        ).ask()
        
        provider_config = ProviderConfig(
            primary="openrouter",
            openrouter=OpenRouterConfig(
                api_key=api_key,
                model=model,
            ),
        )
        print_success(f"Model: {model}")
        
    elif provider_choice == "ollama":
        console.print()
        console.print("[dim]Ollama runs locally on your machine.[/dim]")
        console.print("[dim]Make sure Ollama is installed: https://ollama.ai[/dim]")
        console.print()
        
        # Check if Ollama is running
        print_info("Checking if Ollama is running...")
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await asyncio.wait_for(
                    client.get("http://localhost:11434/api/tags"),
                    timeout=2.0
                )
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    if models:
                        print_success(f"Ollama running with {len(models)} model(s)")
                        console.print(f"[dim]  Available: {', '.join(models[:3])}[/dim]")
                    else:
                        print_warning("Ollama running but no models installed")
                        console.print("[dim]  Run: ollama pull llama3.2[/dim]")
        except:
            print_warning("Ollama not detected. Make sure it's running.")
        
        console.print()
        
        model = questionary.text(
            "Which model?",
            default="llama3.2",
            style=CUSTOM_STYLE,
        ).ask()
        
        provider_config = ProviderConfig(
            primary="ollama",
            ollama=OllamaConfig(model=model),
        )
        print_success(f"Model: {model}")
        
    elif provider_choice == "lmstudio":
        console.print()
        console.print("[dim]LM Studio provides an OpenAI-compatible local API.[/dim]")
        console.print("[dim]Make sure LM Studio is running with the server enabled (port 1234).[/dim]")
        console.print()
        
        # Check if LM Studio is running
        print_info("Checking if LM Studio is running...")
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await asyncio.wait_for(
                    client.get("http://localhost:1234/v1/models"),
                    timeout=2.0
                )
                if response.status_code == 200:
                    print_success("LM Studio detected!")
        except:
            print_warning("LM Studio not detected. Make sure the server is running.")
        
        provider_config = ProviderConfig(
            primary="lmstudio",
            lmstudio=LMStudioConfig(),
        )
        print_success("LM Studio configured")
    
    # ============================================
    # Step 3: Channel Setup
    # ============================================
    print_step(3, total_steps, "Channel Setup")
    
    console.print()
    console.print("[dim]Clawlet can connect to messaging platforms.[/dim]")
    console.print("[dim]You can skip this and set up channels later.[/dim]")
    console.print()
    
    setup_telegram = questionary.confirm(
        "Set up Telegram bot?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()
    
    telegram_token = None
    if setup_telegram:
        console.print()
        console.print("[dim]Create a bot with @BotFather on Telegram[/dim]")
        console.print()
        telegram_token = questionary.password(
            "Enter your Telegram bot token:",
            style=CUSTOM_STYLE,
        ).ask()
        
        if telegram_token:
            print_success("Telegram token saved")
        else:
            print_warning("No token provided, skipping Telegram")
    
    setup_discord = questionary.confirm(
        "Set up Discord bot?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()
    
    discord_token = None
    if setup_discord:
        console.print()
        console.print("[dim]Create a bot in Discord Developer Portal[/dim]")
        console.print()
        discord_token = questionary.password(
            "Enter your Discord bot token:",
            style=CUSTOM_STYLE,
        ).ask()
        
        if discord_token:
            print_success("Discord token saved")
        else:
            print_warning("No token provided, skipping Discord")
    
    # ============================================
    # Step 4: Agent Identity
    # ============================================
    print_step(4, total_steps, "Agent Identity")
    
    console.print()
    console.print("[dim]Give your agent a personality![/dim]")
    console.print("[dim]This helps define who your agent is and how it behaves.[/dim]")
    console.print()
    
    agent_name = questionary.text(
        "What should I call your agent?",
        default="Clawlet",
        style=CUSTOM_STYLE,
    ).ask()
    
    customize_identity = questionary.confirm(
        "Customize personality (SOUL.md)?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()
    
    soul_content = None
    if customize_identity:
        console.print()
        console.print("[dim]Describe your agent's personality in a few words:[/dim]")
        console.print("[dim](e.g., 'friendly and helpful assistant with a dry sense of humor')[/dim]")
        console.print()
        
        personality = questionary.text(
            "Personality:",
            style=CUSTOM_STYLE,
        ).ask()
        
        if personality:
            soul_content = generate_soul_template(agent_name, personality)
            print_success("Custom SOUL.md created")
    
    # ============================================
    # Step 5: Create Workspace
    # ============================================
    print_step(5, total_steps, "Creating Workspace")
    
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Create directories
        task = progress.add_task("Creating workspace...", total=None)
        await asyncio.sleep(0.5)
        
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "memory").mkdir(exist_ok=True)
        
        progress.update(task, description="Writing config...")
        await asyncio.sleep(0.3)
        
        # Create config
        config = Config(provider=provider_config)
        config.to_yaml(workspace / "config.yaml")
        
        progress.update(task, description="Creating identity files...")
        await asyncio.sleep(0.3)
        
        # Create identity files
        create_identity_files(
            workspace,
            agent_name=agent_name,
            soul_content=soul_content,
            telegram_token=telegram_token,
            discord_token=discord_token,
        )
        
        progress.update(task, description="Finalizing...")
        await asyncio.sleep(0.2)
    
    console.print()
    console.print(Panel.fit(
        "[bold green]✓ Workspace created![/bold green]\n\n"
        f"Location: [cyan]{workspace}[/cyan]",
        style="green",
    ))
    
    # ============================================
    # Done!
    # ============================================
    console.print()
    console.print(Panel(
        "[bold]🎉 Setup Complete![/bold]\n\n"
        "Your Clawlet agent is ready to go!\n\n"
        "[bold]Next steps:[/bold]\n\n"
        "  1. Review your config:\n"
        f"     [dim]cat {workspace}/config.yaml[/dim]\n\n"
        "  2. Start your agent:\n"
        "     [cyan]clawlet agent[/cyan]\n\n"
        "  3. For help:\n"
        "     [cyan]clawlet --help[/cyan]\n\n"
        "[dim]Docs: https://github.com/Kxrbx/Clawlet[/dim]",
        style="blue",
    ))
    
    return config


def generate_soul_template(name: str, personality: str) -> str:
    """Generate a custom SOUL.md based on user input."""
    return f"""# SOUL.md - Who You Are

## Name
{name}

## Personality
{personality}

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

_This file defines who I am. I can evolve over time._
"""


def create_identity_files(
    workspace: Path,
    agent_name: str = "Clawlet",
    soul_content: str = None,
    telegram_token: str = None,
    discord_token: str = None,
):
    """Create identity files in workspace."""
    
    # SOUL.md
    soul_path = workspace / "SOUL.md"
    if soul_content:
        soul_path.write_text(soul_content)
    else:
        soul_path.write_text(get_default_soul(agent_name))
    
    # USER.md
    user_path = workspace / "USER.md"
    user_path.write_text("""# USER.md - About Your Human

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
- What makes you laugh?

---

_The more your agent knows, the better it can help!_
""")
    
    # MEMORY.md
    memory_path = workspace / "MEMORY.md"
    memory_path.write_text("""# MEMORY.md - Long-Term Memory

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
""")
    
    # HEARTBEAT.md
    heartbeat_path = workspace / "HEARTBEAT.md"
    heartbeat_path.write_text("""# HEARTBEAT.md - Periodic Tasks

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
""")
    
    # Update config with channel tokens if provided
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


def get_default_soul(name: str = "Clawlet") -> str:
    """Get default SOUL.md content."""
    return f"""# SOUL.md - Who You Are

## Name
{name}

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


if __name__ == "__main__":
    asyncio.run(run_onboarding())
