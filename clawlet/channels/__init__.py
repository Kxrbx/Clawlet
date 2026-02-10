"""
Channels module - Communication backends.

Available channels:
- TelegramChannel: Telegram bot
- DiscordChannel: Discord bot
"""

from clawlet.channels.base import BaseChannel

# Lazy imports to avoid dependency issues
def get_telegram():
    from clawlet.channels.telegram import TelegramChannel
    return TelegramChannel

def get_discord():
    from clawlet.channels.discord import DiscordChannel
    return DiscordChannel

__all__ = [
    "BaseChannel",
    "get_telegram",
    "get_discord",
]
