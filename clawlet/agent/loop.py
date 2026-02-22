"""
Agent loop - the core processing engine.
"""

import asyncio
import json
import os
import re
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from clawlet.agent.identity import Identity, IdentityLoader
from clawlet.agent.tool_parser import ToolCallParser
from clawlet.exceptions import (
    ProviderError,
    ProviderConnectionError,
    ProviderAuthError,
    ProviderRateLimitError,
    ToolExecutionError,
    AgentError,
    ClawletError,
)
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
    
    # Memory management limits
    MAX_MESSAGE_SIZE = 10 * 1024  # 10KB max per message content
    MAX_TOTAL_HISTORY_SIZE = 1024 * 1024  # 1MB max total history size
    
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
        self._tool_parser = ToolCallParser()
        
        logger.info(f"AgentLoop initialized with provider={provider.name}, model={self.model}, tools={len(self.tools.all_tools())}")
        
        # Set up signal handlers for graceful shutdown
        self.setup_signal_handlers()
    
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
                    # Send error response with sanitized message
                    from clawlet.bus.queue import OutboundMessage
                    user_message = self._get_user_friendly_error(e, "message processing")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=user_message
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
    
    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.stop()
        
        # Register signal handlers
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler)
        logger.debug("Signal handlers registered for graceful shutdown")
    
    def _get_user_friendly_error(self, error: Exception, context: str = "") -> str:
        """Generate a user-friendly error message while logging details internally.
        
        This method sanitizes error messages to prevent leaking internal
        information to users, while still logging detailed errors for debugging.
        
        Args:
            error: The exception that was raised
            context: Optional context about where the error occurred
            
        Returns:
            A sanitized, user-friendly error message
        """
        # Log the detailed error internally
        error_type = type(error).__name__
        error_details = str(error)
        
        if isinstance(error, ProviderConnectionError):
            logger.error(f"Provider connection error in {context}: {error_details}")
            return "Sorry, I'm having trouble connecting to the AI service. Please try again."
        
        elif isinstance(error, ProviderAuthError):
            logger.error(f"Provider authentication error in {context}: {error_details}")
            return "Sorry, there's an issue with the AI service configuration. Please contact support."
        
        elif isinstance(error, ProviderRateLimitError):
            retry_after = getattr(error, 'retry_after', None)
            logger.warning(f"Rate limit exceeded in {context}: {error_details}")
            if retry_after:
                return f"Sorry, I'm receiving too many requests. Please try again in {retry_after} seconds."
            return "Sorry, I'm receiving too many requests. Please try again later."
        
        elif isinstance(error, ProviderError):
            logger.error(f"Provider error in {context}: {error_type} - {error_details}")
            return "Sorry, I encountered an issue with the AI service. Please try again."
        
        elif isinstance(error, ToolExecutionError):
            tool_name = error.details.get("tool", "unknown")
            logger.error(f"Tool execution error in {context}: {tool_name} - {error_details}")
            return f"Sorry, I encountered an error while trying to use a tool. Please try again."
        
        elif isinstance(error, AgentError):
            logger.error(f"Agent error in {context}: {error_type} - {error_details}")
            return "Sorry, I encountered an error processing your request. Please try again."
        
        elif isinstance(error, ClawletError):
            logger.error(f"Clawlet error in {context}: {error_type} - {error_details}")
            return "Sorry, I encountered an error. Please try again."
        
        else:
            # For unknown exceptions, log full details but show generic message
            logger.exception(f"Unexpected error in {context}: {error_type} - {error_details}")
            return "Sorry, I encountered an unexpected error. Please try again."
    
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
        
        # Truncate user message if needed before adding to history
        user_msg = Message(role="user", content=user_message)
        user_msg = self._truncate_message(user_msg)
        self._history.append(user_msg)
        
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
                    # Add assistant message with tool calls (truncate if needed)
                    assistant_msg = Message(
                        role="assistant",
                        content=response_content,
                        tool_calls=[{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in tool_calls]
                    )
                    assistant_msg = self._truncate_message(assistant_msg)
                    self._history.append(assistant_msg)
                    
                    # Execute each tool call
                    for tc in tool_calls:
                        result = await self._execute_tool(tc)
                        
                        # Add tool result to history (truncate if needed - tool results can be large)
                        tool_content = result.output if result.success else f"Error: {result.error}"
                        tool_msg = Message(
                            role="tool",
                            content=tool_content,
                            metadata={"tool_call_id": tc.id, "tool_name": tc.name}
                        )
                        tool_msg = self._truncate_message(tool_msg)
                        self._history.append(tool_msg)
                    
                    # Continue loop to get next response
                    continue
                
                # No tool calls - this is the final response
                final_assistant_msg = Message(role="assistant", content=response_content)
                final_assistant_msg = self._truncate_message(final_assistant_msg)
                self._history.append(final_assistant_msg)
                final_response = response_content
                break
                
            except Exception as e:
                logger.error(f"Error in agent loop iteration {iteration}: {e}")
                final_response = self._get_user_friendly_error(e, f"agent loop iteration {iteration}")
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
        """Extract tool calls from LLM response content.
        
        Delegates to ToolCallParser for parsing various formats.
        """
        parsed = self._tool_parser.parse(content)
        return [
            ToolCall(id=p.id, name=p.name, arguments=p.arguments)
            for p in parsed
        ]
    
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
        """Trim history to prevent memory issues.
        
        Trims based on:
        1. Maximum number of messages (MAX_HISTORY)
        2. Maximum total history size in bytes (MAX_TOTAL_HISTORY_SIZE)
        """
        # First, truncate oversized messages
        self._history = [self._truncate_message(msg) for msg in self._history]
        
        # Trim by message count
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]
            logger.debug(f"Trimmed history to {len(self._history)} messages (count limit)")
        
        # Trim by total size
        self._trim_by_size()
        
        # Log memory usage after trimming
        # Note: Removed debug level check since loguru doesn't have simple level property
        stats = self.get_history_stats()
        logger.debug(f"History stats: {stats['message_count']} messages, "
                    f"{stats['memory_kb']}KB ({stats['utilization_percent']}% of max)")
    
    def _trim_by_size(self) -> None:
        """Trim history to stay within MAX_TOTAL_HISTORY_SIZE."""
        current_size = self.get_memory_usage()
        
        if current_size <= self.MAX_TOTAL_HISTORY_SIZE:
            return
        
        # Remove oldest messages until under limit
        while current_size > self.MAX_TOTAL_HISTORY_SIZE and len(self._history) > 1:
            removed_msg = self._history.pop(0)
            removed_size = self._estimate_message_size(removed_msg)
            current_size -= removed_size
        
        logger.info(f"Trimmed history by size: {len(self._history)} messages, ~{current_size / 1024:.1f}KB")
    
    def _truncate_message(self, msg: Message) -> Message:
        """Truncate a message if it exceeds MAX_MESSAGE_SIZE.
        
        Args:
            msg: The message to potentially truncate
            
        Returns:
            Message with truncated content if needed
        """
        content_size = len(msg.content.encode('utf-8'))
        
        if content_size <= self.MAX_MESSAGE_SIZE:
            return msg
        
        # Calculate how much to keep (leave room for truncation notice)
        truncation_notice = f"\n\n[... Content truncated. Original size: {content_size} bytes ...]"
        max_content_size = self.MAX_MESSAGE_SIZE - len(truncation_notice.encode('utf-8'))
        
        if max_content_size < 0:
            max_content_size = 0
        
        truncated_content = msg.content[:max_content_size] + truncation_notice
        
        logger.debug(f"Truncated message from {content_size} to {len(truncated_content.encode('utf-8'))} bytes")
        
        # Return a new message with truncated content
        return Message(
            role=msg.role,
            content=truncated_content,
            metadata=msg.metadata,
            tool_calls=msg.tool_calls
        )
    
    def _estimate_message_size(self, msg: Message) -> int:
        """Estimate the size of a message in bytes.
        
        Args:
            msg: The message to estimate
            
        Returns:
            Approximate size in bytes
        """
        size = len(msg.content.encode('utf-8'))
        
        # Add size for tool calls
        if msg.tool_calls:
            size += len(str(msg.tool_calls).encode('utf-8'))
        
        # Add size for metadata
        if msg.metadata:
            size += len(str(msg.metadata).encode('utf-8'))
        
        return size
    
    def get_memory_usage(self) -> int:
        """Get the current memory usage of the history in bytes.
        
        Returns:
            Total size of all messages in bytes
        """
        total_size = 0
        for msg in self._history:
            total_size += self._estimate_message_size(msg)
        
        return total_size
    
    def clear_history(self) -> None:
        """Clear all history."""
        self._history.clear()
        logger.info("Agent history cleared")
    
    def get_history_length(self) -> int:
        """Get current history length."""
        return len(self._history)
    
    def get_history_stats(self) -> dict:
        """Get detailed statistics about the history.
        
        Returns:
            Dictionary with history statistics
        """
        memory_bytes = self.get_memory_usage()
        message_count = len(self._history)
        
        return {
            "message_count": message_count,
            "memory_bytes": memory_bytes,
            "memory_kb": round(memory_bytes / 1024, 2),
            "memory_mb": round(memory_bytes / (1024 * 1024), 2),
            "max_messages": self.MAX_HISTORY,
            "max_size_bytes": self.MAX_TOTAL_HISTORY_SIZE,
            "max_size_mb": self.MAX_TOTAL_HISTORY_SIZE / (1024 * 1024),
            "utilization_percent": round((memory_bytes / self.MAX_TOTAL_HISTORY_SIZE) * 100, 2) if self.MAX_TOTAL_HISTORY_SIZE > 0 else 0
        }
    
    async def close(self):
        """Clean up resources."""
        if hasattr(self.provider, 'close'):
            await self.provider.close()
