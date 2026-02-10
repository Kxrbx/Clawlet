"""
Agent loop - the core processing engine.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from clawlet.agent.identity import Identity, IdentityLoader


@dataclass
class Message:
    """Represents a message."""
    role: str  # "user", "assistant", "system"
    content: str
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from channels
    2. Builds context with identity and history
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: "MessageBus",
        workspace: Path,
        identity: Identity,
        model: Optional[str] = None,
        max_iterations: int = 20,
    ):
        self.bus = bus
        self.workspace = workspace
        self.identity = identity
        self.model = model or "anthropic/claude-sonnet-4"
        self.max_iterations = max_iterations
        
        self._running = False
        self._history: list[Message] = []
        
        logger.info(f"AgentLoop initialized with model={self.model}")
    
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
                    await self.bus.publish_outbound({
                        "content": f"Sorry, I encountered an error: {str(e)}",
                        "channel": msg.get("channel"),
                        "chat_id": msg.get("chat_id"),
                    })
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in agent loop: {e}")
                await asyncio.sleep(1)
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: dict) -> Optional[dict]:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message with 'content', 'channel', 'chat_id'
            
        Returns:
            Response dict or None
        """
        user_message = msg.get("content", "")
        channel = msg.get("channel")
        chat_id = msg.get("chat_id")
        
        logger.info(f"Processing message from {channel}/{chat_id}: {user_message[:50]}...")
        
        # Add to history
        self._history.append(Message(role="user", content=user_message))
        
        # Build context
        system_prompt = self.identity.build_system_prompt()
        context = self._build_context()
        
        # Call LLM (placeholder - will implement provider abstraction)
        response_content = await self._call_llm(system_prompt, context, user_message)
        
        # Add to history
        self._history.append(Message(role="assistant", content=response_content))
        
        return {
            "content": response_content,
            "channel": channel,
            "chat_id": chat_id,
        }
    
    def _build_context(self) -> str:
        """Build context from recent history."""
        # Get last N messages
        recent = self._history[-10:]
        
        if not recent:
            return ""
        
        parts = []
        for msg in recent:
            role = msg.role.capitalize()
            parts.append(f"{role}: {msg.content}")
        
        return "\n\n".join(parts)
    
    async def _call_llm(
        self, 
        system_prompt: str, 
        context: str, 
        user_message: str
    ) -> str:
        """
        Call the LLM provider.
        
        TODO: Implement provider abstraction
        """
        # Placeholder - will implement real provider calls
        logger.info("Calling LLM...")
        
        # Simulate response for now
        await asyncio.sleep(0.5)
        
        return f"I received your message: '{user_message[:50]}...'\n\nI'm {self.identity.agent_name}, and I'm here to help! (LLM integration coming soon)"
