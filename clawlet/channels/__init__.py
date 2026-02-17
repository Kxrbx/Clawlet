"""
Channels module - Communication backends.

Available channels:
- TelegramChannel: Telegram bot
- DiscordChannel: Discord bot
- WhatsAppChannel: WhatsApp Business API
- SlackChannel: Slack using Slack Bolt
"""

from clawlet.channels.base import BaseChannel

# Lazy imports to avoid dependency issues
def get_telegram_channel():
    """Get TelegramChannel class."""
    from clawlet.channels.telegram import TelegramChannel
    return TelegramChannel

def get_discord_channel():
    """Get DiscordChannel class."""
    from clawlet.channels.discord import DiscordChannel
    return DiscordChannel

def get_whatsapp_channel():
    """Get WhatsAppChannel class."""
    from clawlet.channels.whatsapp import WhatsAppChannel
    return WhatsAppChannel

def get_slack_channel():
    """Get SlackChannel class."""
    from clawlet.channels.slack import SlackChannel
    return SlackChannel

__all__ = [
    "BaseChannel",
    "get_telegram_channel",
    "get_discord_channel",
    "get_whatsapp_channel",
    "get_slack_channel",
]
