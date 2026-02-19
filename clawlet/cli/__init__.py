"""
Clawlet CLI commands.
"""

import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import Optional
import getpass

import typer
from rich.console import Console
from rich.text import Text
from rich.table import Table
from loguru import logger

from clawlet import __version__

# Sakura color scheme
SAKURA_PINK = "#FF69B4"
SAKURA_LIGHT = "#FFB7C5"

app = typer.Typer(
    name="clawlet",
    help="🌸 Clawlet - A lightweight AI agent framework",
    no_args_is_help=False,
)

console = Console()


from clawlet.config import get_default_config_path


def get_workspace_path() -> Path:
    """Get the default workspace path."""
    return Path.home() / ".clawlet"


def print_sakura_banner():
    """Print ASCII art banner."""
    console.print(r"""
[bold magenta]     *  . 　　 　　　✦ 　　 　 ‍ ‍ ‍ ‍ 　. 　　　　 　　　[/bold magenta]
[bold cyan]
  _____ _          __          ___      ______ _______ 
 / ____| |        /\ \        / / |    |  ____|__   __|
| |    | |       /  \ \  /\  / /| |    | |__     | |   
| |    | |      / /\ \ \/  \/ / | |    |  __|    | |   
| |____| |____ / ____ \  /\  /  | |____| |____   | |   
 \_____|______/_/    \_\\/  \/   |______|______|  |_|   
[/bold cyan]
[bold magenta]🌸 A lightweight AI agent framework with identity awareness[/bold magenta]
""")


def print_section(title: str, subtitle: str = None):
    """Print a section header with sakura styling."""
    console.print()
    text = Text()
    text.append("┌─ ", style=f"bold {SAKURA_PINK}")
    text.append(title, style=f"bold {SAKURA_LIGHT}")
    console.print(text)
    
    if subtitle:
        console.print(f"│  [dim]{subtitle}[/dim]")


def print_command(name: str, description: str, shortcut: str = None):
    """Print a command in menu style."""
    if shortcut:
        console.print(f"│  [bold {SAKURA_PINK}]{name:15}[/bold {SAKURA_PINK}] {description} [dim]({shortcut})[/dim]")
    else:
        console.print(f"│  [bold {SAKURA_PINK}]{name:15}[/bold {SAKURA_PINK}] {description}")


def print_footer():
    """Print footer line."""
    console.print("│")
    console.print(f"└─ {'─' * 50}")


def print_main_menu():
    """Print the main menu when clawlet is invoked without args."""
    print_sakura_banner()
    
    print_section("Commands", "What would you like to do?")
    
    print_command("onboard", "Interactive setup wizard (recommended)", "clawlet onboard")
    print_command("init", "Quick workspace initialization", "clawlet init")
    print_command("agent", "Start your AI agent", "clawlet agent")
    print_command("models", "Manage AI models", "clawlet models")
    print_command("dashboard", "Launch web dashboard", "clawlet dashboard")
    print_command("status", "Check workspace status", "clawlet status")
    print_command("health", "Run health checks", "clawlet health")
    print_command("validate", "Validate configuration", "clawlet validate")
    print_command("config", "View/edit configuration", "clawlet config")
    
    print_footer()
    
    console.print()
    console.print(f"[dim]🌸 Run 'clawlet <command> --help' for more info[/dim]")
    console.print(f"[dim]🌸 Version: {__version__} | https://github.com/Kxrbx/Clawlet[/dim]")
    console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
):
    """🌸 Clawlet - A lightweight AI agent framework with identity awareness."""
    if version:
        console.print(f"[magenta]🌸 clawlet version {__version__}[/magenta]")
        raise typer.Exit()
    
    # If no command provided, show custom sakura menu
    if ctx.invoked_subcommand is None:
        print_main_menu()
        raise typer.Exit()


# Import and register all command modules
# These imports trigger the @app.command() decorators to register commands
from clawlet.cli.commands import (
    agent,
    config,
    dashboard,
    health,
    models,
    status,
    validate,
    init,
    onboard,
    workspace,
    routing,
)

__all__ = [
    "app",
    "console",
    "SAKURA_PINK",
    "SAKURA_LIGHT",
    "get_workspace_path",
    "print_sakura_banner",
    "print_section",
    "print_command",
    "print_footer",
    "print_main_menu",
    "main",
]


if __name__ == "__main__":
    app()
