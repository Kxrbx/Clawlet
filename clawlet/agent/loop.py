"""
Agent loop - the core processing engine.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from clawlet.agent.identity import Identity, IdentityLoader
from clawlet.providers.base import BaseProvider, LLMResponse


@dataclass
class Message:
    """Represents a message."""
    role: str  # "user", "assistant", "system"
    content: str
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from channels
    2. Builds context with identity and history
    3. Calls the LLM provider
    4. Executes tool calls (TODO)
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: "MessageBus",
        workspace: Path,
        identity: Identity,
        provider: BaseProvider,
        model: Optional[str] = None,
        max_iterations: int = 20,
    ):
        self.bus = bus
        self.workspace = workspace
        self.identity = identity
        self.provider = provider
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        
        self._running = False
        self._history: list[Message] = []
        
        logger.info(f"AgentLoop initialized with provider={provider.name}, model={self.model}")
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    from clawlet.bus.queue import OutboundMessage
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in agent loop: {e}")
                await asyncio.sleep(1)
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: "InboundMessage") -> Optional["OutboundMessage"]:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message
            
        Returns:
            OutboundMessage or None
        """
        user_message = msg.content
        channel = msg.channel
        chat_id = msg.chat_id
        
        logger.info(f"Processing message from {channel}/{chat_id}: {user_message[:50]}...")
        
        # Add to history
        self._history.append(Message(role="user", content=user_message))
        
        # Build messages for LLM
        messages = self._build_messages()
        
        try:
            # Call LLM provider
            response: LLMResponse = await self.provider.complete(
                messages=messages,
                model=self.model,
                temperature=0.7,
            )
            
            response_content = response.content
            
            # Add to history
            self._history.append(Message(role="assistant", content=response_content))
            
            logger.info(f"LLM response: {len(response_content)} chars")
            
            from clawlet.bus.queue import OutboundMessage
            return OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=response_content,
            )
            
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            raise
    
    def _build_messages(self) -> list[dict]:
        """Build messages list for LLM."""
        messages = []
        
        # System prompt from identity
        system_prompt = self.identity.build_system_prompt()
        messages.append({"role": "system", "content": system_prompt})
        
        # Add recent history
        recent = self._history[-20:]  # Last 20 messages
        for msg in recent:
            messages.append(msg.to_dict())
        
        return messages
    
    async def close(self):
        """Clean up resources."""
        if hasattr(self.provider, 'close'):
            await self.provider.close()
