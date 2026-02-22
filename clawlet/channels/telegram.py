"""
Telegram channel implementation.
"""

import asyncio
from typing import Optional

from loguru import logger
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage
from clawlet.channels.base import BaseChannel


def escape_markdown_v2(text: str) -> str:
    """Escape reserved characters for Telegram MarkdownV2.
    
    MarkdownV2 requires these characters to be escaped with a preceding backslash:
    _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    if not text:
        return text
    
    # Order matters: escape backslash first to avoid double-escaping
    escape_chars = ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    
    return text


class TelegramChannel(BaseChannel):
    """Telegram channel using python-telegram-bot."""
    
    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(bus, config)
        
        self.token = config.get("token")
        if not self.token:
            raise ValueError("Telegram token not configured")
        
        self.app: Optional[Application] = None
        self._outbound_task: Optional[asyncio.Task] = None
    
    @property
    def name(self) -> str:
        return "telegram"
    
    async def start(self) -> None:
        """Start the Telegram bot."""
        logger.info(f"Starting Telegram channel...")
        
        # Create application
        self.app = Application.builder().token(self.token).build()
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        
        # Initialize and start
        await self.app.initialize()
        await self.app.start()
        
        # Start polling in background
        await self.app.updater.start_polling()
        
        # Start outbound loop
        self._running = True
        self._outbound_task = asyncio.create_task(self._run_outbound_loop())
        
        logger.info("Telegram channel started successfully")
    
    async def stop(self) -> None:
        """Stop the Telegram bot."""
        logger.info("Stopping Telegram channel...")
        
        self._running = False
        
        if self._outbound_task:
            self._outbound_task.cancel()
            try:
                await self._outbound_task
            except asyncio.CancelledError:
                pass
        
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        
        logger.info("Telegram channel stopped")
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to Telegram."""
        logger.info(f"Telegram send: to={msg.chat_id}, content={msg.content[:50]}...")
        
        # DEBUG: Log content for diagnosis
        content_preview = msg.content[:200] if msg.content else "(empty)"
        logger.debug(f"Telegram message content (raw): {content_preview}")
        
        # Check for unescaped MarkdownV2 reserved characters
        reserved_chars = {'_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '\\'}
        found_chars = {c: msg.content.count(c) for c in reserved_chars if c in (msg.content or '')}
        if found_chars:
            logger.warning(f"Telegram message contains unescaped MarkdownV2 reserved chars: {found_chars}")
        
        try:
            try:
                chat_id = int(msg.chat_id)
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid chat_id format: {msg.chat_id} - {e}")
                return
            
            # Try MarkdownV2 with properly escaped content
            parse_mode = "MarkdownV2"
            escaped_content = escape_markdown_v2(msg.content)
            logger.debug(f"Escaped content: {escaped_content[:100]}...")
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=escaped_content,
                    parse_mode=parse_mode
                )
                logger.info(f"Sent Telegram message to {chat_id}")
            except Exception as parse_error:
                # Fall back to plain text if even escaped MarkdownV2 fails
                logger.warning(f"MarkdownV2 parsing failed even with escaping, falling back to plain text: {parse_error}")
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=msg.content,  # Use original unescaped content for plain text
                    parse_mode=None
                )
                logger.info(f"Sent Telegram message to {chat_id} (plain text)")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        chat_id = str(update.effective_chat.id)
        user_name = update.effective_user.first_name or "there"
        
        await update.message.reply_text(
            f"👋 Hello {user_name}! I'm Clawlet, your AI assistant.\n\n"
            f"Just send me a message and I'll help you out!"
        )
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text message."""
        chat_id = str(update.effective_chat.id)
        user_id = str(update.effective_user.id)
        content = update.message.text
        
        logger.info(f"Received Telegram message from {chat_id}: {content[:50]}...")
        
        # Create inbound message
        msg = InboundMessage(
            channel=self.name,
            chat_id=chat_id,
            content=content,
            user_id=user_id,
            metadata={
                "user_name": update.effective_user.first_name,
                "username": update.effective_user.username,
            }
        )
        
        # Publish to bus
        await self.bus.publish_inbound(msg)
