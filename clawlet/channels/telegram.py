"""
Telegram channel implementation.
"""

import asyncio
import re
from typing import Optional

from loguru import logger
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage
from clawlet.channels.base import BaseChannel


def convert_markdown_to_html(text: str) -> str:
    """Convert common Markdown formatting to Telegram HTML.
    
    Supports:
    - **bold** or __bold__ -> <b>bold</b>
    - *italic* or _italic_ -> <i>italic</i>
    - `inline code` -> <code>inline code</code>
    - ```code block``` -> <pre>code block</pre>
    - [text](url) -> <a href="url">text</a>
    - # Heading -> <b>Heading</b>
    - - list item -> • list item
    - ~~strikethrough~~ -> <s>strikethrough</s>
    
    Also escapes HTML special characters to prevent injection.
    """
    if not text:
        return text
    
    # First escape HTML special characters (but preserve our own tags later)
    # We escape in a way that protects against HTML injection
    text = text.replace('&', '&')
    text = text.replace('<', '<')
    text = text.replace('>', '>')
    
    # Convert Markdown to HTML (order matters - more specific patterns first)
    
    # Code blocks (```...```) -> <pre>...</pre>
    text = re.sub(r'```(\w*)\n?([\s\S]*?)```', r'<pre>\2</pre>', text)
    
    # Inline code (`...`) -> <code>...</code>
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    
    # Bold (**...** or __...__) -> <b>...</b>
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__([^_]+)__', r'<b>\1</b>', text)
    
    # Italic (*...* or _..._) -> <i>...</i> (being careful not to match already bold)
    text = re.sub(r'(?<![*_])\*([^*]+)\*(?![*_])', r'<i>\1</i>', text)
    text = re.sub(r'(?<![*_])_([^_]+)_(?![*_])', r'<i>\1</i>', text)
    
    # Links [text](url) -> <a href="url">text</a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    # Unordered lists: - item or * item -> • item
    text = re.sub(r'^[\-\*]\s+', '• ', text, flags=re.MULTILINE)
    
    # Headers: # H1, ## H2, ### H3 -> <b>H1</b>, <b>H2</b>, <b>H3</b>
    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # Strikethrough ~~text~~ -> <s>text</s>
    text = re.sub(r'~~([^~]+)~~', r'<s>\1</s>', text)
    
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
        """Send a message to Telegram with proper formatting."""
        logger.info(f"Telegram send: to={msg.chat_id}, content={msg.content[:50]}...")
        
        # DEBUG: Log content for diagnosis
        content_preview = msg.content[:200] if msg.content else "(empty)"
        logger.debug(f"Telegram message content (raw): {content_preview}")
        
        try:
            try:
                chat_id = int(msg.chat_id)
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid chat_id format: {msg.chat_id} - {e}")
                return
            
            # Try HTML parse_mode with converted Markdown
            parse_mode = "HTML"
            html_content = convert_markdown_to_html(msg.content)
            logger.debug(f"Converted HTML content: {html_content[:100]}...")
            
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=html_content,
                    parse_mode=parse_mode
                )
                logger.info(f"Sent Telegram message to {chat_id} (HTML format)")
            except Exception as parse_error:
                # Fall back to plain text if HTML parsing fails
                logger.warning(f"HTML parsing failed, falling back to plain text: {parse_error}")
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
