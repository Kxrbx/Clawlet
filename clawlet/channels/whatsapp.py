"""
WhatsApp Business API channel implementation.

Uses WhatsApp Cloud API (Meta's official API) for messaging.
Supports webhook verification, text/media messages, and mark as read.
"""

import asyncio
import json
from typing import Optional, Any
from aiohttp import web, ClientSession

from loguru import logger

from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage
from clawlet.channels.base import BaseChannel


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp Business API channel using Cloud API.
    
    Supports:
    - Webhook verification (Meta requirement)
    - Text messages
    - Image messages
    - Document messages
    - Audio messages
    - Mark as read
    - Reply to messages
    
    Configuration:
        phone_number_id: WhatsApp Business Phone Number ID
        access_token: Meta System User Access Token
        verify_token: Token for webhook verification
        allowed_users: Optional list of phone numbers to allow
    """
    
    WHATSAPP_API_BASE = "https://graph.facebook.com/v18.0"
    
    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(bus, config)
        
        self.phone_number_id = config.get("phone_number_id")
        self.access_token = config.get("access_token")
        self.verify_token = config.get("verify_token", "")
        self.allowed_users = config.get("allowed_users", [])
        
        if not self.phone_number_id:
            raise ValueError("WhatsApp phone_number_id not configured")
        if not self.access_token:
            raise ValueError("WhatsApp access_token not configured")
        
        self._running = False
        self._outbound_task: Optional[asyncio.Task] = None
        self._http_session: Optional[ClientSession] = None
        self._web_runner: Optional[web.AppRunner] = None
        self._web_site: Optional[web.TCPSite] = None
        
        # Rate limiting
        self._last_send_time = 0.0
        self._min_send_interval = 0.1  # 100ms between sends
        
        logger.info(f"WhatsAppChannel initialized with phone_number_id: {self.phone_number_id}")
    
    @property
    def name(self) -> str:
        return "whatsapp"
    
    async def start(self) -> None:
        """Start the WhatsApp webhook server and outbound loop."""
        logger.info("Starting WhatsApp channel...")
        
        self._running = True
        
        # Create HTTP session for API calls
        self._http_session = ClientSession()
        
        # Create webhook server
        app = web.Application()
        app.router.add_get("/webhook/whatsapp", self._handle_webhook_verification)
        app.router.add_post("/webhook/whatsapp", self._handle_webhook_message)
        
        self._web_runner = web.AppRunner(app)
        await self._web_runner.setup()
        
        # Get port from config or use default
        port = self.config.get("port", 8080)
        host = self.config.get("host", "0.0.0.0")
        
        self._web_site = web.TCPSite(self._web_runner, host, port)
        await self._web_site.start()
        
        # Start outbound loop
        self._outbound_task = asyncio.create_task(self._run_outbound_loop())
        
        logger.info(f"WhatsApp webhook server started on {host}:{port}")
        logger.info(f"Webhook URL: {host}:{port}/webhook/whatsapp")
    
    async def stop(self) -> None:
        """Stop the WhatsApp channel."""
        logger.info("Stopping WhatsApp channel...")
        
        self._running = False
        
        if self._outbound_task:
            self._outbound_task.cancel()
            try:
                await self._outbound_task
            except asyncio.CancelledError:
                pass
        
        if self._web_runner:
            await self._web_runner.cleanup()
        
        if self._http_session:
            await self._http_session.close()
        
        logger.info("WhatsApp channel stopped")
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message via WhatsApp Cloud API."""
        logger.info(f"WhatsApp send: to={msg.chat_id}, content={msg.content[:50]}...")
        
        try:
            # Rate limiting
            await self._rate_limit()
            
            # Check if this is a reply
            reply_to = msg.metadata.get("reply_to") if msg.metadata else None
            
            # Send text message
            await self._send_text_message(msg.chat_id, msg.content, reply_to)
            
            logger.info(f"Sent WhatsApp message to {msg.chat_id}")
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
    
    async def _rate_limit(self) -> None:
        """Apply rate limiting between sends."""
        import time
        elapsed = time.time() - self._last_send_time
        if elapsed < self._min_send_interval:
            await asyncio.sleep(self._min_send_interval - elapsed)
        self._last_send_time = time.time()
    
    async def _send_text_message(
        self, 
        to: str, 
        text: str, 
        reply_to: Optional[str] = None
    ) -> dict:
        """Send a text message via WhatsApp API."""
        url = f"{self.WHATSAPP_API_BASE}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
            }
        }
        
        if reply_to:
            payload["context"] = {"message_id": reply_to}
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        async with self._http_session.post(url, json=payload, headers=headers) as response:
            result = await response.json()
            
            if response.status != 200:
                logger.error(f"WhatsApp API error: {result}")
                raise Exception(f"WhatsApp API error: {result.get('error', {}).get('message', 'Unknown error')}")
            
            return result
    
    async def send_image(
        self, 
        to: str, 
        image_url: str, 
        caption: Optional[str] = None
    ) -> dict:
        """Send an image message via WhatsApp API."""
        url = f"{self.WHATSAPP_API_BASE}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {
                "link": image_url
            }
        }
        
        if caption:
            payload["image"]["caption"] = caption
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        async with self._http_session.post(url, json=payload, headers=headers) as response:
            result = await response.json()
            
            if response.status != 200:
                logger.error(f"WhatsApp API error: {result}")
                raise Exception(f"WhatsApp API error: {result.get('error', {}).get('message', 'Unknown error')}")
            
            return result
    
    async def send_document(
        self, 
        to: str, 
        document_url: str, 
        filename: Optional[str] = None,
        caption: Optional[str] = None
    ) -> dict:
        """Send a document message via WhatsApp API."""
        url = f"{self.WHATSAPP_API_BASE}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {
                "link": document_url
            }
        }
        
        if filename:
            payload["document"]["filename"] = filename
        if caption:
            payload["document"]["caption"] = caption
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        async with self._http_session.post(url, json=payload, headers=headers) as response:
            result = await response.json()
            
            if response.status != 200:
                logger.error(f"WhatsApp API error: {result}")
                raise Exception(f"WhatsApp API error: {result.get('error', {}).get('message', 'Unknown error')}")
            
            return result
    
    async def mark_as_read(self, message_id: str) -> dict:
        """Mark a message as read."""
        url = f"{self.WHATSAPP_API_BASE}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        async with self._http_session.post(url, json=payload, headers=headers) as response:
            result = await response.json()
            
            if response.status != 200:
                logger.warning(f"Failed to mark message as read: {result}")
            
            return result
    
    async def _handle_webhook_verification(self, request: web.Request) -> web.Response:
        """
        Handle webhook verification from Meta.
        
        Meta sends a GET request with:
        - hub.mode: "subscribe"
        - hub.challenge: Challenge string to echo back
        - hub.verify_token: Token to verify
        """
        mode = request.query.get("hub.mode")
        challenge = request.query.get("hub.challenge")
        verify_token = request.query.get("hub.verify_token")
        
        logger.info(f"Webhook verification request: mode={mode}")
        
        if mode == "subscribe" and verify_token == self.verify_token:
            logger.info("Webhook verification successful")
            return web.Response(text=challenge, status=200)
        else:
            logger.warning(f"Webhook verification failed: token mismatch")
            return web.Response(text="Verification failed", status=403)
    
    async def _handle_webhook_message(self, request: web.Request) -> web.Response:
        """
        Handle incoming webhook messages from WhatsApp.
        
        Meta sends POST requests with message data in the request body.
        """
        try:
            data = await request.json()
            logger.debug(f"Received webhook data: {json.dumps(data, indent=2)}")
            
            # Parse the webhook data
            await self._process_webhook_data(data)
            
            return web.Response(text="OK", status=200)
            
        except Exception as e:
            logger.error(f"Error processing webhook message: {e}")
            return web.Response(text="Error", status=500)
    
    async def _process_webhook_data(self, data: dict) -> None:
        """Process incoming webhook data and extract messages."""
        try:
            # Navigate the webhook structure
            entry = data.get("entry", [])
            
            for entry_item in entry:
                changes = entry_item.get("changes", [])
                
                for change in changes:
                    value = change.get("value", {})
                    
                    # Check if this is a message
                    messages = value.get("messages", [])
                    
                    for message in messages:
                        await self._process_message(message, value)
                        
        except Exception as e:
            logger.error(f"Error processing webhook data: {e}")
    
    async def _process_message(self, message: dict, value: dict) -> None:
        """Process a single incoming message."""
        try:
            # Extract basic info
            from_number = message.get("from", "")
            message_id = message.get("id", "")
            message_type = message.get("type", "")
            timestamp = message.get("timestamp", "")
            
            # Check allowed users
            if self.allowed_users and from_number not in self.allowed_users:
                logger.warning(f"Message from unauthorized user: {from_number}")
                return
            
            # Get contact info
            contacts = value.get("contacts", [])
            contact_name = ""
            if contacts:
                profile = contacts[0].get("profile", {})
                contact_name = profile.get("name", "")
            
            # Extract content based on type
            content = ""
            metadata = {
                "message_id": message_id,
                "timestamp": timestamp,
                "contact_name": contact_name,
                "message_type": message_type,
            }
            
            if message_type == "text":
                text_data = message.get("text", {})
                content = text_data.get("body", "")
                
            elif message_type == "image":
                image_data = message.get("image", {})
                content = "[Image]"
                metadata["media_id"] = image_data.get("id", "")
                metadata["caption"] = image_data.get("caption", "")
                metadata["mime_type"] = image_data.get("mime_type", "")
                
            elif message_type == "document":
                doc_data = message.get("document", {})
                content = f"[Document: {doc_data.get('filename', 'unknown')}]"
                metadata["media_id"] = doc_data.get("id", "")
                metadata["filename"] = doc_data.get("filename", "")
                metadata["caption"] = doc_data.get("caption", "")
                metadata["mime_type"] = doc_data.get("mime_type", "")
                
            elif message_type == "audio":
                audio_data = message.get("audio", {})
                content = "[Audio]"
                metadata["media_id"] = audio_data.get("id", "")
                metadata["mime_type"] = audio_data.get("mime_type", "")
                
            elif message_type == "video":
                video_data = message.get("video", {})
                content = "[Video]"
                metadata["media_id"] = video_data.get("id", "")
                metadata["caption"] = video_data.get("caption", "")
                metadata["mime_type"] = video_data.get("mime_type", "")
                
            elif message_type == "location":
                location_data = message.get("location", {})
                lat = location_data.get("latitude", 0)
                lng = location_data.get("longitude", 0)
                content = f"[Location: {lat}, {lng}]"
                metadata["latitude"] = lat
                metadata["longitude"] = lng
                
            else:
                content = f"[{message_type.capitalize()}]"
            
            # Check for reply context
            context = message.get("context", {})
            if context:
                metadata["reply_to"] = context.get("id", "")
            
            # Create inbound message
            inbound = InboundMessage(
                channel=self.name,
                chat_id=from_number,
                content=content,
                user_id=from_number,
                user_name=contact_name,
                metadata=metadata
            )
            
            logger.info(f"Received WhatsApp message from {from_number}: {content[:50]}...")
            
            # Publish to bus
            await self._publish_inbound(inbound)
            
            # Mark as read
            if self.config.get("mark_read", True):
                await self.mark_as_read(message_id)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def get_media_url(self, media_id: str) -> Optional[str]:
        """Get the URL for a media file."""
        url = f"{self.WHATSAPP_API_BASE}/{media_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            async with self._http_session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("url")
        except Exception as e:
            logger.error(f"Error getting media URL: {e}")
        
        return None
    
    async def download_media(self, media_url: str) -> Optional[bytes]:
        """Download media content from URL."""
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            async with self._http_session.get(media_url, headers=headers) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as e:
            logger.error(f"Error downloading media: {e}")
        
        return None
