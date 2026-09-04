"""
Channels module - Communication backends.

Available channels:
- TelegramChannel: Telegram bot
- DiscordChannel: Discord bot
- WhatsAppChannel: WhatsApp Business API
- SlackChannel: Slack using Slack Bolt
"""

from clawlet.channels.base import BaseChannel

__all__ = [
    "BaseChannel",
]
