"""
Agent loop - the core processing engine.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from clawlet.agent.identity import Identity, IdentityLoader
from clawlet.providers.base import BaseProvider, LLMResponse
from clawlet.tools.registry import ToolRegistry, ToolResult


@dataclass
class Message:
    """Represents a message."""
    role: str  # "user", "assistant", "system"
    content: str
    metadata: dict = field(default_factory=dict)
    tool_calls: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        d = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""
    id: str
    name: str
    arguments: dict


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from channels
    2. Builds context with identity and history
    3. Calls the LLM provider
    4. Executes tool calls
    5. Sends responses back
    """
    
    # History limits
    MAX_HISTORY = 100  # Maximum messages to keep
    CONTEXT_WINDOW = 20  # Messages to include in LLM context
    
    def __init__(
        self,
        bus: "MessageBus",
        workspace: Path,
        identity: Identity,
        provider: BaseProvider,
        tools: Optional[ToolRegistry] = None,
        model: Optional[str] = None,
        max_iterations: int = 10,
    ):
        self.bus = bus
        self.workspace = workspace
        self.identity = identity
        self.provider = provider
        self.tools = tools or ToolRegistry()
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        
        self._running = False
        self._history: list[Message] = []
        
        logger.info(f"AgentLoop initialized with provider={provider.name}, model={self.model}, tools={len(self.tools.all_tools())}")
    
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
                
                logger.info(f"Received message from bus: {msg.channel}/{msg.chat_id} - {msg.content[:50]}...")
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        logger.info(f"Sending response: {response.content[:50]}...")
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
        Process a single inbound message with tool calling support.
        
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
        
        # Trim history periodically
        self._trim_history()
        
        # Iterative tool calling loop
        iteration = 0
        final_response = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
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
                
                # Check for tool calls in response
                tool_calls = self._extract_tool_calls(response_content)
                
                if tool_calls:
                    # Add assistant message with tool calls
                    self._history.append(Message(
                        role="assistant",
                        content=response_content,
                        tool_calls=[{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in tool_calls]
                    ))
                    
                    # Execute each tool call
                    for tc in tool_calls:
                        result = await self._execute_tool(tc)
                        
                        # Add tool result to history
                        self._history.append(Message(
                            role="tool",
                            content=result.output if result.success else f"Error: {result.error}",
                            metadata={"tool_call_id": tc.id, "tool_name": tc.name}
                        ))
                    
                    # Continue loop to get next response
                    continue
                
                # No tool calls - this is the final response
                self._history.append(Message(role="assistant", content=response_content))
                final_response = response_content
                break
                
            except Exception as e:
                logger.error(f"Error in agent loop iteration {iteration}: {e}")
                final_response = f"Sorry, I encountered an error: {str(e)}"
                break
        
        if final_response is None:
            final_response = "I reached my maximum number of iterations. Please try again."
        
        logger.info(f"Final response: {len(final_response)} chars (iterations: {iteration})")
        
        from clawlet.bus.queue import OutboundMessage
        return OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=final_response,
        )
    
    def _extract_tool_calls(self, content: str) -> list[ToolCall]:
        """Extract tool calls from LLM response content."""
        tool_calls = []
        
        # Pattern for tool calls in various formats
        # Format 1: <tool_call name="..." arguments="..."/>
        pattern1 = r'<tool_call\s+name="([^"]+)"\s+arguments=\'([^\']+)\'\s*/?>'
        matches1 = re.findall(pattern1, content)
        
        for i, (name, args_str) in enumerate(matches1):
            try:
                args = json.loads(args_str)
                tool_calls.append(ToolCall(
                    id=f"call_{i}",
                    name=name,
                    arguments=args,
                ))
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tool arguments: {args_str}")
        
        # Format 2: JSON block with tool_call
        pattern2 = r'```json\s*\n(tool_call)?\s*\n?([\s\S]*?)\n```'
        matches2 = re.findall(pattern2, content, re.IGNORECASE)
        
        for i, (_, json_str) in enumerate(matches2):
            try:
                data = json.loads(json_str)
                if isinstance(data, dict) and "name" in data:
                    tool_calls.append(ToolCall(
                        id=f"call_json_{i}",
                        name=data["name"],
                        arguments=data.get("arguments", data.get("parameters", {})),
                    ))
            except json.JSONDecodeError:
                pass
        
        if tool_calls:
            logger.info(f"Extracted {len(tool_calls)} tool call(s)")
        
        return tool_calls
    
    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call."""
        logger.info(f"Executing tool: {tool_call.name} with args: {tool_call.arguments}")
        
        result = await self.tools.execute(tool_call.name, **tool_call.arguments)
        
        if result.success:
            logger.info(f"Tool {tool_call.name} succeeded: {result.output[:100]}...")
        else:
            logger.warning(f"Tool {tool_call.name} failed: {result.error}")
        
        return result
    
    def _build_messages(self) -> list[dict]:
        """Build messages list for LLM."""
        messages = []
        
        # System prompt from identity (include tools)
        tools_list = self.tools.all_tools() if self.tools else None
        system_prompt = self.identity.build_system_prompt(tools=tools_list)
        messages.append({"role": "system", "content": system_prompt})
        
        # Add recent history (limited by CONTEXT_WINDOW)
        recent = self._history[-self.CONTEXT_WINDOW:]
        for msg in recent:
            messages.append(msg.to_dict())
        
        return messages
    
    def _trim_history(self) -> None:
        """Trim history to prevent unbounded growth."""
        if len(self._history) > self.MAX_HISTORY:
            # Keep the most recent messages
            self._history = self._history[-self.MAX_HISTORY:]
            logger.debug(f"Trimmed history to {len(self._history)} messages")
    
    def clear_history(self) -> None:
        """Clear all history."""
        self._history.clear()
        logger.info("Agent history cleared")
    
    def get_history_length(self) -> int:
        """Get current history length."""
        return len(self._history)
    
    async def close(self):
        """Clean up resources."""
        if hasattr(self.provider, 'close'):
            await self.provider.close()
