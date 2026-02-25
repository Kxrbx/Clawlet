"""
Init command module.
"""

from pathlib import Path

import typer

from clawlet.cli import SAKURA_PINK, app, console, get_workspace_path


@app.command()
def init(
    workspace: Path = typer.Option(
        None, "--workspace", "-w", help="Workspace directory"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
):
    """🌸 Quick workspace initialization.
    
    For guided setup, use 'clawlet onboard' instead.
    """
    from clawlet.cli import print_section, print_footer
    from clawlet.cli.commands.init import get_soul_template, get_user_template, get_memory_template, get_heartbeat_template, get_config_template
    
    workspace_path = workspace or get_workspace_path()
    
    # If workspace doesn't exist, suggest onboard
    if not workspace_path.exists():
        print_section("Quick Setup", "Creating workspace with defaults")
        console.print("│  [dim]💡 For guided setup, use: clawlet onboard[/dim]")
    else:
        print_section("Quick Setup", f"Updating {workspace_path}")
    
    console.print("│")
    
    # Create workspace directory
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "memory").mkdir(exist_ok=True)
    (workspace_path / "workspace").mkdir(exist_ok=True)
    
    # Create identity files
    identity_files = {
        "SOUL.md": get_soul_template(),
        "USER.md": get_user_template(),
        "MEMORY.md": get_memory_template(),
        "HEARTBEAT.md": get_heartbeat_template(),
    }
    
    for filename, content in identity_files.items():
        file_path = workspace_path / filename
        if file_path.exists() and not force:
            console.print(f"│  [yellow]→[/yellow] {filename} [dim](exists, skipped)[/dim]")
        else:
            file_path.write_text(content)
            console.print(f"│  [green]✓[/green] {filename}")
    
    # Create config file
    config_path = workspace_path / "config.yaml"
    if not config_path.exists() or force:
        config_path.write_text(get_config_template())
        console.print(f"│  [green]✓[/green] config.yaml")
    
    print_footer()
    
    console.print()
    console.print(f"[bold green]✓ Workspace ready![/bold green]")
    console.print(f"  Location: [{SAKURA_PINK}]{workspace_path}[/{SAKURA_PINK}]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Edit [{SAKURA_PINK}]config.yaml[/{SAKURA_PINK}] to add API keys")
    console.print(f"  2. Run [{SAKURA_PINK}]clawlet agent[/{SAKURA_PINK}] to start")
    console.print()


# Template functions

def get_soul_template() -> str:
    return """# SOUL.md - Who You Are

This file defines your agent's core identity, personality, and values.

## Name
Clawlet

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


def get_user_template() -> str:
    return """# USER.md - About Your Human

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
- What annoys you?
- What makes you laugh?

---

_The more your agent knows, the better it can help!_
"""


def get_memory_template() -> str:
    return """# MEMORY.md - Long-Term Memory

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
"""


def get_heartbeat_template() -> str:
    return """# HEARTBEAT.md - Periodic Tasks

This file defines tasks your agent performs periodically.

## Check Interval
Every 30 minutes

## Tasks
- [ ] Check for important updates
- [ ] Review recent activity
- [ ] Update memory if needed

## Quiet Hours
2am - 9am UTC (no heartbeats during this time)

---

_Heartbeats help your agent stay proactive._
"""


def get_config_template() -> str:
    return """# Clawlet Configuration

# LLM Provider Settings
provider:
  # Primary provider: openrouter, ollama, lmstudio
  primary: openrouter
  
  # OpenRouter settings
  openrouter:
    api_key: "YOUR_OPENROUTER_API_KEY"
    model: "anthropic/claude-sonnet-4"
  
  # Ollama settings (local)
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.2"
  
  # LM Studio settings (local)
  lmstudio:
    base_url: "http://localhost:1234"
    model: "local-model"

# Channel Settings (individual fields - not 'channels:' key)
 telegram:
   enabled: false
   token: "YOUR_TELEGRAM_BOT_TOKEN"
 
 discord:
   enabled: false
   token: "YOUR_DISCORD_BOT_TOKEN"
 
 whatsapp:
   enabled: false
 
 slack:
   enabled: false

# Storage Settings
storage:
  # backend: sqlite or postgres
  backend: sqlite
  
  # SQLite settings
  sqlite:
    path: "~/.clawlet/clawlet.db"
  
  # PostgreSQL settings
  postgres:
    host: "localhost"
    port: 5432
    database: "clawlet"
    user: "clawlet"
    password: "your_password"

# Agent Settings
agent:
  max_iterations: 20
  context_window: 20
  temperature: 0.7

# Heartbeat Settings
heartbeat:
  interval_minutes: 30
  quiet_hours_start: 2  # 2am UTC
  quiet_hours_end: 9    # 9am UTC

# Multi-Agent Routing (optional)
routing:
  enabled: false
  default_agent: "default"
  routes: []
"""
