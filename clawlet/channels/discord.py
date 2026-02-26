"""
Discord channel integration.
"""

import asyncio
from typing import Optional
from collections import defaultdict

from loguru import logger

try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    # Create dummy types for type hints
    discord = None
    commands = None

from clawlet.channels.base import BaseChannel
from clawlet.bus.queue import InboundMessage, OutboundMessage, MessageBus


class DiscordChannel(BaseChannel):
    """
    Discord channel using discord.py.
    
    Supports:
    - Guild (server) messages
    - DMs
    - Reactions
    - Slash commands (optional)
    """
    
    def __init__(self, bus: MessageBus, config: dict, agent=None):
        """
        Initialize Discord channel.
        
        Args:
            bus: Message bus for publishing/consuming
            config: Configuration dict with 'token' and optional 'command_prefix'
            agent: Optional agent loop for command handling
        """
        if not DISCORD_AVAILABLE:
            raise RuntimeError("discord.py not installed. Run: pip install discord.py")
        
        super().__init__(bus, config, agent)
        
        self.token = config.get("token", "")
        self.command_prefix = config.get("command_prefix", "!")
        
        if not self.token:
            raise ValueError("Discord token is required in config")
        
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        self.intents = intents
        
        # Create bot
        self.bot = commands.Bot(
            command_prefix=self.command_prefix,
            intents=intents,
            description="Clawlet AI Assistant",
        )
        
        # Set up event handlers
        self._setup_handlers()
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._typing_refcounts: defaultdict[str, int] = defaultdict(int)
        
        logger.info(f"DiscordChannel initialized with prefix '{self.command_prefix}'")
    
    @property
    def name(self) -> str:
        return "discord"
    
    def _setup_handlers(self):
        """Set up Discord event handlers."""
        
        @self.bot.command(name="new", help="Start a new conversation and clear history")
        async def new_command(ctx):
            """Handle !new command - start a new conversation and clear history."""
            chat_id = str(ctx.channel.id)
            user_name = ctx.author.name or "there"
            
            # Clear conversation history if agent is available
            if self.agent:
                success = await self.agent.clear_conversation(self.name, chat_id)
                if success:
                    await ctx.send(
                        f"✨ {user_name}, I've started a new conversation! "
                        f"Previous chat history has been cleared."
                    )
                else:
                    await ctx.send(
                        f"✨ {user_name}, I've started a new conversation! "
                        f"(Note: Could not clear stored history)"
                    )
            else:
                # Agent not available, just respond
                await ctx.send(
                    f"✨ {user_name}, I've started a new conversation!"
                )
        
        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.bot.user} (ID: {self.bot.user.id})")
        
        @self.bot.event
        async def on_message(message: discord.Message):
            # Ignore own messages
            if message.author == self.bot.user:
                return
            
            # Let discord.py handle registered commands like !new.
            ctx = await self.bot.get_context(message)
            if ctx.valid:
                await self.bot.process_commands(message)
                return
            
            if not message.content or not message.content.strip():
                return
            
            try:
                # Create inbound message
                guild_id = str(message.guild.id) if message.guild else None
                inbound = InboundMessage(
                    channel="discord",
                    chat_id=str(message.channel.id),
                    content=message.content,
                    user_id=str(message.author.id),
                    metadata={
                        "guild_id": guild_id,
                        "channel_name": message.channel.name if hasattr(message.channel, 'name') else "DM",
                        "is_dm": isinstance(message.channel, discord.DMChannel),
                        "message_id": str(message.id),
                        "reply_to": str(message.reference.message_id) if message.reference else None,
                    }
                )
                
                logger.info(f"Discord message from {message.author}: {message.content[:50]}...")
                
                # Publish to message bus
                await self._start_typing(str(message.channel.id))
                try:
                    await self._publish_inbound(inbound)
                except Exception:
                    await self._stop_typing(str(message.channel.id))
                    raise
                
            except Exception as e:
                logger.error(f"Error processing Discord message: {e}", exc_info=True)
    
    async def start(self) -> None:
        """Start the Discord bot and outbound loop."""
        self._running = True
        
        # Start outbound loop as background task
        outbound_task = asyncio.create_task(self._run_outbound_loop())
        
        # Start bot (this blocks until stopped)
        try:
            logger.info("Starting Discord bot...")
            await self.bot.start(self.token)
        finally:
            self._running = False
            outbound_task.cancel()
            try:
                await outbound_task
            except asyncio.CancelledError:
                pass
            await self._stop_all_typing()
    
    async def stop(self) -> None:
        """Stop the Discord bot."""
        self._running = False
        logger.info("Stopping Discord bot...")
        await self.bot.close()
    
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
        finally:
            await self._stop_typing(msg.chat_id)
    
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

    async def _stop_all_typing(self) -> None:
        """Cancel all active typing keepalive tasks."""
        for chat_id in list(self._typing_tasks.keys()):
            await self._stop_typing(chat_id)

    async def _start_typing(self, chat_id: str) -> None:
        """Start keepalive typing indicator for a chat."""
        self._typing_refcounts[chat_id] += 1
        if chat_id in self._typing_tasks:
            return
        self._typing_tasks[chat_id] = asyncio.create_task(self._typing_keepalive_loop(chat_id))

    async def _stop_typing(self, chat_id: str) -> None:
        """Decrease typing reference count and stop indicator when no work remains."""
        count = self._typing_refcounts.get(chat_id, 0)
        if count <= 0:
            return
        count -= 1
        if count > 0:
            self._typing_refcounts[chat_id] = count
            return
        self._typing_refcounts.pop(chat_id, None)
        task = self._typing_tasks.pop(chat_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _typing_keepalive_loop(self, chat_id: str) -> None:
        """Send typing indicator periodically until stopped."""
        try:
            while self._running and self._typing_refcounts.get(chat_id, 0) > 0:
                channel = self.bot.get_channel(int(chat_id))
                if channel is None:
                    try:
                        channel = await self.bot.fetch_channel(int(chat_id))
                    except Exception as e:
                        logger.debug(f"Could not fetch Discord channel {chat_id} for typing: {e}")
                        await asyncio.sleep(4.0)
                        continue
                try:
                    await channel.trigger_typing()
                except Exception as e:
                    logger.debug(f"Could not send Discord typing action for {chat_id}: {e}")
                await asyncio.sleep(4.0)
        except asyncio.CancelledError:
            raise
