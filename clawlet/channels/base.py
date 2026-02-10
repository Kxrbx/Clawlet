"""
Base channel interface.
"""

from abc import ABC, abstractmethod
from typing import Optional

from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage


class BaseChannel(ABC):
    """
    Base class for all messaging channels.
    
    Channels are responsible for:
    1. Receiving messages from their platform
    2. Converting to InboundMessage format
    3. Publishing to the message bus
    4. Consuming outbound messages and sending to platform
    """
    
    def __init__(self, bus: MessageBus, config: dict):
        self.bus = bus
        self.config = config
        self._running = False
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Channel name (e.g., 'telegram', 'discord')."""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the channel (connect to platform)."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel (disconnect from platform)."""
        pass
    
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to the platform."""
        pass
    
    async def _run_outbound_loop(self) -> None:
        """Consume outbound messages and send them."""
        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0
                )
                
                # Only handle messages for this channel
                if msg.channel == self.name:
                    await self.send(msg)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in outbound loop for {self.name}: {e}")
                await asyncio.sleep(1)


import asyncio
from loguru import logger
