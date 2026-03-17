"""
Base channel interface.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

from loguru import logger

from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage
from clawlet.runtime.events import EVENT_CHANNEL_FAILED, RuntimeEvent
from clawlet.runtime.failures import classify_error_text, to_payload

if TYPE_CHECKING:
    from clawlet.agent.loop import AgentLoop


class BaseChannel(ABC):
    """
    Base class for all messaging channels.
    
    Channels are responsible for:
    1. Receiving messages from their platform
    2. Converting to InboundMessage format
    3. Publishing to the message bus
    4. Consuming outbound messages and sending to platform
    """
    
    def __init__(self, bus: MessageBus, config: dict, agent: Optional["AgentLoop"] = None):
        self.bus = bus
        self.config = config
        self.agent = agent
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
    
    async def _publish_inbound(self, msg: InboundMessage) -> None:
        """Publish an inbound message to the bus."""
        await self.bus.publish_inbound(msg)
    
    async def _run_outbound_loop(self) -> None:
        """Consume outbound messages and send them."""
        logger.info(f"Outbound loop started for channel: {self.name}")
        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound_for(self.name),
                    timeout=1.0
                )
                logger.debug(f"Outbound message received for {msg.channel}: {msg.content[:50]}...")
                logger.debug(f"Sending message to {self.name} channel")
                await self.send(msg)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in outbound loop for {self.name}: {e}")
                if 'msg' in locals():
                    await self._handle_outbound_failure(msg, e)
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def _handle_outbound_failure(self, msg: OutboundMessage, error: Exception) -> None:
        """Emit runtime telemetry and retry bounded channel delivery failures."""
        metadata = dict(msg.metadata or {})
        attempt = max(1, int(metadata.get("_delivery_attempt", 1)))
        self._emit_channel_failure(msg, error, attempt)

        max_attempts = max(1, int(self.config.get("delivery_retries", 2)) + 1)
        if attempt >= max_attempts or not self._running:
            return

        retry_metadata = dict(metadata)
        retry_metadata["_delivery_attempt"] = attempt + 1
        backoff = max(0.0, float(self.config.get("delivery_retry_backoff_seconds", 0.5)))
        if backoff > 0:
            await asyncio.sleep(backoff * attempt)

        await self.bus.publish_outbound(
            OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=msg.content,
                metadata=retry_metadata,
            )
        )
        logger.warning(
            f"Re-queued outbound message for {self.name} {msg.chat_id} "
            f"(delivery attempt {attempt + 1}/{max_attempts})"
        )

    def _emit_channel_failure(self, msg: OutboundMessage, error: Exception, attempt: int) -> None:
        """Persist channel delivery failure telemetry when runtime context is available."""
        if self.agent is None:
            return
        runtime_config = getattr(self.agent, "runtime_config", None)
        event_store = getattr(self.agent, "_event_store", None)
        if runtime_config is None or event_store is None or not runtime_config.replay.enabled:
            return

        metadata = dict(msg.metadata or {})
        session_id = str(metadata.get("_session_id") or "").strip()
        run_id = str(metadata.get("_run_id") or "").strip()
        if not session_id or not run_id:
            return

        failure = classify_error_text(str(error))
        event_store.append(
            RuntimeEvent(
                event_type=EVENT_CHANNEL_FAILED,
                run_id=run_id,
                session_id=session_id,
                payload={
                    "channel": msg.channel,
                    "chat_id": msg.chat_id,
                    "attempt": attempt,
                    "error": str(error),
                    **to_payload(failure),
                },
            )
        )
