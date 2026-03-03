"""Shared CLI display helpers."""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.text import Text

# Sakura color scheme
SAKURA_PINK = "#FF69B4"
SAKURA_LIGHT = "#FFB7C5"

console = Console()


def print_section(title: str, subtitle: str = None):
    """Print a section header with sakura styling."""
    console.print()
    text = Text()
    text.append("+- ", style=f"bold {SAKURA_PINK}")
    text.append(title, style=f"bold {SAKURA_LIGHT}")
    console.print(text)

    if subtitle:
        console.print(f"|  [dim]{subtitle}[/dim]")


def print_command(name: str, description: str, shortcut: str = None):
    """Print a command in menu style."""
    if shortcut:
        console.print(
            f"|  [bold {SAKURA_PINK}]{name:15}[/bold {SAKURA_PINK}] {description} [dim]({shortcut})[/dim]"
        )
    else:
        console.print(f"|  [bold {SAKURA_PINK}]{name:15}[/bold {SAKURA_PINK}] {description}")


def print_footer():
    """Print footer line."""
    console.print("|")
    console.print(f"+- {'-' * 50}")


def _filter_breach_lines(
    breach_lines: list[str],
    breach_category: Optional[str],
) -> tuple[list[str], Optional[str]]:
    category = (breach_category or "").strip().lower()
    if not category:
        return breach_lines, None
    valid_categories = {"local", "corpus", "lane", "context", "coding", "rust", "comparison", "other"}
    if category not in valid_categories:
        return breach_lines, (
            "Invalid --breach-category. Use one of: "
            "local, corpus, lane, context, coding, rust, comparison, other"
        )
    filtered = [item for item in breach_lines if item.lower().startswith(f"{category}:")]
    return filtered, None
