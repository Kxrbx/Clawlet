"""
Discord channel integration.
"""

import asyncio
from typing import Optional, Callable, Any

from loguru import logger

try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    logger.warning("discord.py not installed. Discord channel unavailable.")

from clawlet.channels.base import BaseChannel
from clawlet.bus.queue import InboundMessage, OutboundMessage


class DiscordChannel(BaseChannel):
    """
    Discord channel using discord.py.
    
    Supports:
    - Guild (server) messages
    - DMs
    - Reactions
    - Slash commands (optional)
    """
    
    def __init__(
        self,
        token: str,
        command_prefix: str = "!",
        intents: Optional[discord.Intents] = None,
    ):
        """
        Initialize Discord channel.
        
        Args:
            token: Discord bot token
            command_prefix: Prefix for text commands
            intents: Discord intents (default: all message intents)
        """
        if not DISCORD_AVAILABLE:
            raise RuntimeError("discord.py not installed. Run: pip install discord.py")
        
        self.token = token
        self.command_prefix = command_prefix
        
        # Set up intents
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True
        
        self.intents = intents
        
        # Create bot
        self.bot = commands.Bot(
            command_prefix=command_prefix,
            intents=intents,
            description="Clawlet AI Assistant",
        )
        
        # Set up event handlers
        self._setup_handlers()
        
        # Message handler
        self._message_handler: Optional[Callable[[InboundMessage], Any]] = None
        
        logger.info(f"DiscordChannel initialized with prefix '{command_prefix}'")
    
    @property
    def name(self) -> str:
        return "discord"
    
    def _setup_handlers(self):
        """Set up Discord event handlers."""
        
        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.bot.user} (ID: {self.bot.user.id})")
        
        @self.bot.event
        async def on_message(message: discord.Message):
            # Ignore own messages
            if message.author == self.bot.user:
                return
            
            # Create inbound message
            inbound = InboundMessage(
                channel="discord",
                chat_id=str(message.channel.id),
                content=message.content,
                user_id=str(message.author.id),
                user_name=message.author.display_name,
                metadata={
                    "guild_id": str(message.guild.id) if message.guild else None,
                    "channel_name": message.channel.name if hasattr(message.channel, 'name') else "DM",
                    "is_dm": isinstance(message.channel, discord.DMChannel),
                    "message_id": str(message.id),
                    "reply_to": str(message.reference.message_id) if message.reference else None,
                }
            )
            
            logger.info(f"Discord message from {message.author}: {message.content[:50]}...")
            
            # Call handler if set
            if self._message_handler:
                await self._message_handler(inbound)
    
    async def start(self) -> None:
        """Start the Discord bot."""
        logger.info("Starting Discord bot...")
        await self.bot.start(self.token)
    
    async def stop(self) -> None:
        """Stop the Discord bot."""
        logger.info("Stopping Discord bot...")
        await self.bot.close()
    
    def on_message(self, handler: Callable[[InboundMessage], Any]) -> None:
        """Register message handler."""
        self._message_handler = handler
    
    async def send(self, msg: OutboundMessage) -> bool:
        """
        Send a message to Discord.
        
        Args:
            msg: Outbound message
            
        Returns:
            True if sent successfully
        """
        try:
            # Find channel
            channel = self.bot.get_channel(int(msg.chat_id))
            if not channel:
                logger.error(f"Discord channel {msg.chat_id} not found")
                return False
            
            # Send message
            await channel.send(msg.content)
            logger.info(f"Sent Discord message to {msg.chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")
            return False
    
    async def react(self, chat_id: str, message_id: str, emoji: str) -> bool:
        """Add reaction to a message."""
        try:
            channel = self.bot.get_channel(int(chat_id))
            if not channel:
                return False
            
            message = await channel.fetch_message(int(message_id))
            await message.add_reaction(emoji)
            return True
            
        except Exception as e:
            logger.error(f"Error adding reaction: {e}")
            return False
    
    async def reply(
        self,
        chat_id: str,
        message_id: str,
        content: str,
        mention: bool = False,
    ) -> bool:
        """Reply to a specific message."""
        try:
            channel = self.bot.get_channel(int(chat_id))
            if not channel:
                return False
            
            message = await channel.fetch_message(int(message_id))
            
            if mention:
                await message.reply(content)
            else:
                await message.reply(content, mention_author=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Error replying to message: {e}")
            return False
    
    def get_guilds(self) -> list[dict]:
        """Get list of guilds the bot is in."""
        return [
            {
                "id": str(guild.id),
                "name": guild.name,
                "member_count": guild.member_count,
            }
            for guild in self.bot.guilds
        ]
    
    def get_channels(self, guild_id: str) -> list[dict]:
        """Get channels in a guild."""
        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return []
        
        return [
            {
                "id": str(channel.id),
                "name": channel.name,
                "type": str(channel.type),
            }
            for channel in guild.channels
            if isinstance(channel, discord.TextChannel)
        ]
