"""
Slack channel implementation using Slack Bolt for Python.

Supports:
- Socket Mode (no public endpoint needed) - recommended
- HTTP mode with signature verification
- App mentions (@BotName message)
- Direct messages (DMs)
- Channel messages
- Thread replies for organized conversations
- Rich message formatting (blocks, attachments)
- File sharing
- Reaction handling
"""

import asyncio
import json
from typing import Optional, Any

from loguru import logger

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    from slack_bolt.adapter.aiohttp import SlackRequestHandler
    from slack_sdk.web.async_client import AsyncWebClient
    from slack_sdk.errors import SlackApiError
    SLACK_BOLT_AVAILABLE = True
except ImportError:
    SLACK_BOLT_AVAILABLE = False
    # Create dummy types for type hints
    App = None
    SocketModeHandler = None
    SlackRequestHandler = None
    AsyncWebClient = None
    SlackApiError = Exception

from aiohttp import web

from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage
from clawlet.channels.base import BaseChannel


class SlackChannel(BaseChannel):
    """
    Slack channel using Slack Bolt for Python.
    
    Supports two modes:
    1. Socket Mode (recommended): No public endpoint needed, uses WebSocket
    2. HTTP Mode: Requires public endpoint with signature verification
    
    Configuration:
        bot_token: Slack Bot User OAuth Token (xoxb-...)
        app_token: Slack App-Level Token (xapp-...) - required for Socket Mode
        signing_secret: Slack Signing Secret - required for HTTP mode
        socket_mode: Use Socket Mode (default: True)
        allowed_channels: Optional list of channel IDs to allow
        allowed_users: Optional list of user IDs to allow
    """
    
    def __init__(self, bus: MessageBus, config: dict):
        """Initialize Slack channel."""
        if not SLACK_BOLT_AVAILABLE:
            raise RuntimeError(
                "slack_bolt not installed. Run: pip install slack_bolt slack_sdk"
            )
        
        super().__init__(bus, config)
        
        # Required tokens
        self.bot_token = config.get("bot_token", "")
        self.app_token = config.get("app_token", "")
        self.signing_secret = config.get("signing_secret", "")
        
        # Mode configuration
        self.socket_mode = config.get("socket_mode", True)
        
        # Access control
        self.allowed_channels = config.get("allowed_channels", [])
        self.allowed_users = config.get("allowed_users", [])
        
        # Validate configuration
        if not self.bot_token:
            raise ValueError("Slack bot_token is required")
        
        if self.socket_mode and not self.app_token:
            raise ValueError("Slack app_token is required for Socket Mode")
        
        if not self.socket_mode and not self.signing_secret:
            raise ValueError("Slack signing_secret is required for HTTP mode")
        
        # Initialize Slack app and client
        self.app: Optional[App] = None
        self.client: Optional[AsyncWebClient] = None
        self.socket_handler: Optional[SocketModeHandler] = None
        self.http_handler: Optional[SlackRequestHandler] = None
        
        # HTTP server for HTTP mode
        self._web_runner: Optional[web.AppRunner] = None
        self._web_site: Optional[web.TCPSite] = None
        
        # Outbound loop task
        self._outbound_task: Optional[asyncio.Task] = None
        
        # Bot info
        self._bot_user_id: Optional[str] = None
        
        logger.info(f"SlackChannel initialized (socket_mode={self.socket_mode})")
    
    @property
    def name(self) -> str:
        return "slack"
    
    async def start(self) -> None:
        """Start the Slack channel."""
        logger.info("Starting Slack channel...")
        
        self._running = True
        
        # Create Slack app
        if self.socket_mode:
            self.app = App(token=self.bot_token)
        else:
            self.app = App(
                token=self.bot_token,
                signing_secret=self.signing_secret
            )
        
        # Create async web client
        self.client = AsyncWebClient(token=self.bot_token)
        
        # Get bot user ID
        try:
            auth_result = await self.client.auth_test()
            self._bot_user_id = auth_result["user_id"]
            logger.info(f"Slack bot authenticated as {auth_result['user']} (ID: {self._bot_user_id})")
        except SlackApiError as e:
            logger.error(f"Failed to authenticate Slack bot: {e}")
            raise
        
        # Set up event handlers
        self._setup_handlers()
        
        # Start based on mode
        if self.socket_mode:
            await self._start_socket_mode()
        else:
            await self._start_http_mode()
        
        # Start outbound loop
        self._outbound_task = asyncio.create_task(self._run_outbound_loop())
        
        logger.info("Slack channel started successfully")
    
    def _setup_handlers(self) -> None:
        """Set up Slack event handlers."""
        
        @self.app.event("app_mention")
        async def handle_app_mention(event, say, client):
            """Handle @mentions of the bot."""
            await self._process_message_event(event, say, client, is_mention=True)
        
        @self.app.event("message")
        async def handle_message(event, say, client):
            """Handle direct messages and channel messages."""
            # Skip bot messages and message_changed/deleted events
            if event.get("bot_id") or event.get("subtype"):
                return
            
            # Check if this is a DM
            channel_type = event.get("channel_type", "")
            is_dm = channel_type == "im"
            
            # For channel messages, only respond to mentions if not in DM
            if not is_dm:
                # Check if bot is mentioned in the text
                text = event.get("text", "")
                if f"<@{self._bot_user_id}>" not in text:
                    # Not a mention, skip
                    return
            
            await self._process_message_event(event, say, client, is_mention=not is_dm)
        
        @self.app.event("reaction_added")
        async def handle_reaction_added(event, client):
            """Handle reactions to messages."""
            await self._process_reaction_event(event, client)
    
    async def _process_message_event(
        self, 
        event: dict, 
        say, 
        client,
        is_mention: bool = False
    ) -> None:
        """Process an incoming message event."""
        try:
            user_id = event.get("user", "")
            channel_id = event.get("channel", "")
            text = event.get("text", "")
            thread_ts = event.get("thread_ts", "")
            message_ts = event.get("ts", "")
            channel_type = event.get("channel_type", "")
            
            # Check access control
            if self.allowed_users and user_id not in self.allowed_users:
                logger.warning(f"Message from unauthorized user: {user_id}")
                return
            
            if self.allowed_channels and channel_id not in self.allowed_channels:
                # Allow DMs even if channel not in allowed list
                if channel_type != "im":
                    logger.warning(f"Message from unauthorized channel: {channel_id}")
                    return
            
            # Clean text - remove bot mention if present
            if self._bot_user_id:
                text = text.replace(f"<@{self._bot_user_id}>", "").strip()
            
            # Get user info
            user_name = ""
            try:
                user_info = await client.users_info(user=user_id)
                user_name = user_info["user"]["real_name"] or user_info["user"]["name"]
            except Exception as e:
                logger.warning(f"Could not get user info: {e}")
            
            # Get channel info
            channel_name = ""
            if channel_type != "im":
                try:
                    channel_info = await client.conversations_info(channel=channel_id)
                    channel_name = channel_info["channel"]["name"]
                except Exception as e:
                    logger.warning(f"Could not get channel info: {e}")
            else:
                channel_name = "DM"
            
            # Create inbound message
            inbound = InboundMessage(
                channel=self.name,
                chat_id=channel_id,
                content=text,
                user_id=user_id,
                user_name=user_name,
                metadata={
                    "message_ts": message_ts,
                    "thread_ts": thread_ts,
                    "channel_type": channel_type,
                    "channel_name": channel_name,
                    "is_mention": is_mention,
                    "is_dm": channel_type == "im",
                }
            )
            
            logger.info(f"Received Slack message from {user_name} in {channel_name}: {text[:50]}...")
            
            # Publish to bus
            await self._publish_inbound(inbound)
            
        except Exception as e:
            logger.error(f"Error processing Slack message: {e}")
    
    async def _process_reaction_event(self, event: dict, client) -> None:
        """Process a reaction event."""
        try:
            user_id = event.get("user", "")
            reaction = event.get("reaction", "")
            item = event.get("item", {})
            channel_id = item.get("channel", "")
            message_ts = item.get("ts", "")
            
            # Check access control
            if self.allowed_users and user_id not in self.allowed_users:
                return
            
            logger.debug(f"Reaction '{reaction}' added by {user_id} in {channel_id}")
            
            # Create inbound message for reaction
            inbound = InboundMessage(
                channel=self.name,
                chat_id=channel_id,
                content=f"[reaction:{reaction}]",
                user_id=user_id,
                metadata={
                    "event_type": "reaction_added",
                    "reaction": reaction,
                    "message_ts": message_ts,
                }
            )
            
            await self._publish_inbound(inbound)
            
        except Exception as e:
            logger.error(f"Error processing reaction: {e}")
    
    async def _start_socket_mode(self) -> None:
        """Start in Socket Mode (WebSocket connection)."""
        logger.info("Starting Slack in Socket Mode...")
        
        # Create socket mode handler
        self.socket_handler = SocketModeHandler(
            app=self.app,
            app_token=self.app_token
        )
        
        # Start in a separate thread (SocketModeHandler is blocking)
        # We need to use the async approach
        import threading
        
        def run_socket_mode():
            self.socket_handler.connect()
            logger.info("Slack Socket Mode connected")
        
        # Run in thread to not block
        self._socket_thread = threading.Thread(target=run_socket_mode, daemon=True)
        self._socket_thread.start()
        
        # Give it a moment to connect
        await asyncio.sleep(1)
    
    async def _start_http_mode(self) -> None:
        """Start in HTTP mode with webhook endpoint."""
        logger.info("Starting Slack in HTTP Mode...")
        
        # Create HTTP handler
        self.http_handler = SlackRequestHandler(self.app)
        
        # Create aiohttp app
        aiohttp_app = web.Application()
        aiohttp_app.router.add_post("/slack/events", self._handle_slack_events)
        
        self._web_runner = web.AppRunner(aiohttp_app)
        await self._web_runner.setup()
        
        # Get port from config or use default
        port = self.config.get("port", 3000)
        host = self.config.get("host", "0.0.0.0")
        
        self._web_site = web.TCPSite(self._web_runner, host, port)
        await self._web_site.start()
        
        logger.info(f"Slack HTTP webhook server started on {host}:{port}")
        logger.info(f"Webhook URL: http://{host}:{port}/slack/events")
    
    async def _handle_slack_events(self, request: web.Request) -> web.Response:
        """Handle incoming Slack events via HTTP."""
        return await self.http_handler.handle(request)
    
    async def stop(self) -> None:
        """Stop the Slack channel."""
        logger.info("Stopping Slack channel...")
        
        self._running = False
        
        # Cancel outbound task
        if self._outbound_task:
            self._outbound_task.cancel()
            try:
                await self._outbound_task
            except asyncio.CancelledError:
                pass
        
        # Close socket mode
        if self.socket_handler:
            try:
                self.socket_handler.close()
            except Exception as e:
                logger.warning(f"Error closing socket handler: {e}")
        
        # Close HTTP server
        if self._web_runner:
            await self._web_runner.cleanup()
        
        logger.info("Slack channel stopped")
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to Slack."""
        logger.info(f"Slack send: to={msg.chat_id}, content={msg.content[:50]}...")
        
        try:
            # Extract metadata
            thread_ts = msg.metadata.get("thread_ts") if msg.metadata else None
            blocks = msg.metadata.get("blocks") if msg.metadata else None
            attachments = msg.metadata.get("attachments") if msg.metadata else None
            reply_broadcast = msg.metadata.get("reply_broadcast", False) if msg.metadata else False
            
            # Build message kwargs
            kwargs = {
                "channel": msg.chat_id,
                "text": msg.content,
            }
            
            # Add thread reply if specified
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
                if reply_broadcast:
                    kwargs["reply_broadcast"] = True
            
            # Add blocks if specified
            if blocks:
                kwargs["blocks"] = blocks
            
            # Add attachments if specified
            if attachments:
                kwargs["attachments"] = attachments
            
            # Send message
            result = await self.client.chat_postMessage(**kwargs)
            
            logger.info(f"Sent Slack message to {msg.chat_id} (ts: {result['ts']})")
            
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")
    
    async def send_ephemeral(
        self, 
        channel: str, 
        user: str, 
        text: str,
        thread_ts: Optional[str] = None,
        blocks: Optional[list] = None
    ) -> Optional[dict]:
        """
        Send an ephemeral message (visible only to specific user).
        
        Args:
            channel: Channel ID
            user: User ID to show message to
            text: Message text
            thread_ts: Thread timestamp to reply in
            blocks: Rich message blocks
            
        Returns:
            API response or None on error
        """
        try:
            kwargs = {
                "channel": channel,
                "user": user,
                "text": text,
            }
            
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            if blocks:
                kwargs["blocks"] = blocks
            
            result = await self.client.chat_postEphemeral(**kwargs)
            return result
            
        except SlackApiError as e:
            logger.error(f"Error sending ephemeral message: {e}")
            return None
    
    async def send_file(
        self,
        channel: str,
        file_content: bytes,
        filename: str,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> Optional[dict]:
        """
        Upload and share a file in a channel.
        
        Args:
            channel: Channel ID
            file_content: File bytes
            filename: Name of the file
            title: File title
            initial_comment: Comment to post with file
            thread_ts: Thread timestamp to reply in
            
        Returns:
            API response or None on error
        """
        try:
            kwargs = {
                "channels": channel,
                "file": file_content,
                "filename": filename,
            }
            
            if title:
                kwargs["title"] = title
            if initial_comment:
                kwargs["initial_comment"] = initial_comment
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            
            result = await self.client.files_upload_v2(**kwargs)
            return result
            
        except SlackApiError as e:
            logger.error(f"Error uploading file: {e}")
            return None
    
    async def add_reaction(
        self, 
        channel: str, 
        timestamp: str, 
        emoji: str
    ) -> bool:
        """
        Add a reaction to a message.
        
        Args:
            channel: Channel ID
            timestamp: Message timestamp
            emoji: Emoji name (without colons)
            
        Returns:
            True if successful
        """
        try:
            await self.client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=emoji
            )
            return True
            
        except SlackApiError as e:
            logger.error(f"Error adding reaction: {e}")
            return False
    
    async def remove_reaction(
        self, 
        channel: str, 
        timestamp: str, 
        emoji: str
    ) -> bool:
        """
        Remove a reaction from a message.
        
        Args:
            channel: Channel ID
            timestamp: Message timestamp
            emoji: Emoji name (without colons)
            
        Returns:
            True if successful
        """
        try:
            await self.client.reactions_remove(
                channel=channel,
                timestamp=timestamp,
                name=emoji
            )
            return True
            
        except SlackApiError as e:
            logger.error(f"Error removing reaction: {e}")
            return False
    
    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """Get information about a user."""
        try:
            result = await self.client.users_info(user=user_id)
            return result["user"]
        except SlackApiError as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    async def get_channel_info(self, channel_id: str) -> Optional[dict]:
        """Get information about a channel."""
        try:
            result = await self.client.conversations_info(channel=channel_id)
            return result["channel"]
        except SlackApiError as e:
            logger.error(f"Error getting channel info: {e}")
            return None
    
    async def get_thread_replies(
        self, 
        channel: str, 
        thread_ts: str,
        limit: int = 100
    ) -> Optional[list]:
        """
        Get replies in a thread.
        
        Args:
            channel: Channel ID
            thread_ts: Thread timestamp
            limit: Maximum number of replies
            
        Returns:
            List of messages or None on error
        """
        try:
            result = await self.client.conversations_replies(
                channel=channel,
                ts=thread_ts,
                limit=limit
            )
            return result["messages"]
        except SlackApiError as e:
            logger.error(f"Error getting thread replies: {e}")
            return None
    
    async def mark_as_read(
        self, 
        channel: str, 
        timestamp: str
    ) -> bool:
        """Mark a channel as read up to a timestamp."""
        try:
            await self.client.conversations_mark(channel=channel, ts=timestamp)
            return True
        except SlackApiError as e:
            logger.error(f"Error marking as read: {e}")
            return False
    
    @staticmethod
    def build_blocks_from_text(text: str, max_block_chars: int = 3000) -> list:
        """
        Build Slack blocks from text, splitting if necessary.
        
        Args:
            text: Text content
            max_block_chars: Maximum characters per block
            
        Returns:
            List of block dictionaries
        """
        blocks = []
        
        # Split text into chunks if too long
        chunks = []
        if len(text) <= max_block_chars:
            chunks = [text]
        else:
            # Split on newlines when possible
            lines = text.split("\n")
            current_chunk = ""
            for line in lines:
                if len(current_chunk) + len(line) + 1 <= max_block_chars:
                    current_chunk += "\n" + line if current_chunk else line
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = line
            if current_chunk:
                chunks.append(current_chunk)
        
        # Build blocks
        for chunk in chunks:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": chunk
                }
            })
        
        return blocks
    
    @staticmethod
    def build_attachment(
        title: str,
        text: str,
        color: str = "#36a64f",
        fields: Optional[list] = None,
        footer: Optional[str] = None
    ) -> dict:
        """
        Build a Slack attachment.
        
        Args:
            title: Attachment title
            text: Attachment text
            color: Sidebar color (hex)
            fields: List of field dicts with 'title' and 'value'
            footer: Footer text
            
        Returns:
            Attachment dictionary
        """
        attachment = {
            "title": title,
            "text": text,
            "color": color,
        }
        
        if fields:
            attachment["fields"] = [
                {"title": f["title"], "value": f["value"], "short": f.get("short", False)}
                for f in fields
            ]
        
        if footer:
            attachment["footer"] = footer
        
        return attachment
