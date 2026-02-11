"""
Message bus for handling inbound and outbound messages.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Optional
from collections import deque

from loguru import logger


@dataclass
class InboundMessage:
    """Represents an incoming message from a channel."""
    channel: str
    chat_id: str
    content: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass  
class OutboundMessage:
    """Represents an outgoing message to a channel."""
    channel: str
    chat_id: str
    content: str
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MessageBus:
    """
    Async message bus for routing messages between channels and agent.
    
    Uses asyncio queues for non-blocking message handling.
    """
    
    def __init__(self, max_size: int = 1000):
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=max_size)
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=max_size)
        self._running = False
        
        logger.info(f"MessageBus initialized with max_size={max_size}")
    
    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish an inbound message to the queue."""
        await self._inbound.put(msg)
        logger.debug(f"Published inbound message from {msg.channel}/{msg.chat_id}")
    
    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish an outbound message to the queue."""
        await self._outbound.put(msg)
        logger.debug(f"Published outbound message to {msg.channel}/{msg.chat_id}")
    
    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message."""
        return await self._inbound.get()
    
    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message."""
        return await self._outbound.get()
    
    @property
    def inbound_size(self) -> int:
        """Get number of pending inbound messages."""
        return self._inbound.qsize()
    
    @property
    def outbound_size(self) -> int:
        """Get number of pending outbound messages."""
        return self._outbound.qsize()
