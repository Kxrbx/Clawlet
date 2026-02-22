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
        try:
            try:
                chat_id = int(msg.chat_id)
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid chat_id format: {msg.chat_id} - {e}")
                return
            
            # Try MarkdownV2 first, fall back to None if parsing fails
            parse_mode = "MarkdownV2"
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=msg.content,
                    parse_mode=parse_mode
                )
                logger.info(f"Sent Telegram message to {chat_id}")
            except Exception as parse_error:
                # Fall back to None if MarkdownV2 parsing fails
                logger.warning(f"MarkdownV2 parsing failed, falling back to plain text: {parse_error}")
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=msg.content,
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
