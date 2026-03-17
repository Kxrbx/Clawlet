"""Telegram menu and shortcut helpers."""

from __future__ import annotations


TEXT_MENU_ACTIONS = {
    "status": "status",
    "settings": "settings",
    "memory": "memory",
    "heartbeat": "heartbeat",
    "approve": "approve",
    "cancel": "cancel",
    "new conversation": "new",
    "stop updates": "stop",
}


def resolve_text_menu_action(content: str) -> str | None:
    return TEXT_MENU_ACTIONS.get(content.strip().lower())
