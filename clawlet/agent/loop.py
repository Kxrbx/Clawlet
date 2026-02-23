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
from clawlet.agent.memory import MemoryManager
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
        import json
        from loguru import logger
        
        d = {"role": self.role, "content": self.content}
        if self.tool_calls:
            # Transform tool_calls to OpenAI API format:
            # {"id": "...", "type": "function", "function": {"name": "...", "arguments": "{...}"}}
            formatted_tool_calls = []
            for tc in self.tool_calls:
                # Handle both dict and object formats
                if isinstance(tc, dict):
                    tc_id = tc.get("id")
                    tc_name = tc.get("name")
                    tc_args = tc.get("arguments", {})
                else:
                    tc_id = tc.id
                    tc_name = tc.name
                    tc_args = tc.arguments
                
                # Convert arguments dict to JSON string
                if isinstance(tc_args, dict):
                    args_str = json.dumps(tc_args)
                else:
                    args_str = str(tc_args)
                
                formatted_tool_calls.append({
                    "id": tc_id,
                    "type": "function",
                    "function": {
                        "name": tc_name,
                        "arguments": args_str
                    }
                })
            
            d["tool_calls"] = formatted_tool_calls
            logger.debug(f"Message.to_dict: role={self.role}, tool_calls={formatted_tool_calls}")
        
        # Include tool_call_id for tool role messages
        if self.role == "tool" and self.metadata.get("tool_call_id"):
            d["tool_call_id"] = self.metadata["tool_call_id"]
            logger.debug(f"Message.to_dict: tool with tool_call_id={self.metadata['tool_call_id']}")
        
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
        memory: Optional[MemoryManager] = None,
        streaming: bool = False,
    ):
        self.bus = bus
        self.workspace = workspace
        self.identity = identity
        self.provider = provider
        self.tools = tools or ToolRegistry()
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.memory = memory or MemoryManager(self.workspace)
        self.streaming = streaming
        
        self._running = False
        self._task = None
        self._history: list[Message] = []
        self._tool_parser = ToolCallParser()
        
        logger.info(f"AgentLoop initialized with provider={provider.name}, model={self.model}, tools={len(self.tools.all_tools())}")
        logger.debug(f"Available tools: {[t.name for t in self.tools.all_tools()]}")
        
        # Set up signal handlers for graceful shutdown
        self.setup_signal_handlers()
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        self._task = asyncio.current_task()
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
        # DEBUG: Log that we're stopping and save memory
        logger.info("[DEBUG] Agent loop stopping, saving memory before shutdown")
        self.memory.save_long_term()
        logger.debug("[DEBUG] Memory saved successfully")
        # END DEBUG
        
        self._running = False
        logger.info("Agent loop stopping")
    
    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.stop()
            raise KeyboardInterrupt()
        
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
            
            # Periodic memory save every 5 iterations
            if iteration % 5 == 0:
                self.memory.save_long_term()
                logger.debug(f"Memory saved at iteration {iteration}")
            
            # Build messages for LLM
            messages = self._build_messages()
            
            try:
                # Call LLM provider (streaming or non-streaming)
                if self.streaming:
                    response: LLMResponse = await self._process_streaming_response(
                        messages=messages,
                        model=self.model,
                        temperature=0.7,
                    )
                else:
                    # DEBUG: Log what's being passed to provider
                    openai_tools = self.tools.to_openai_tools() if self.tools else []
                    logger.debug(f"[DEBUG] Calling provider.complete with tools: {len(openai_tools)} tools")
                    response: LLMResponse = await self.provider.complete(
                        messages=messages,
                        model=self.model,
                        temperature=0.7,
                        tools=openai_tools if openai_tools else None,
                    )
                
                response_content = response.content
                
                # DEBUG: Log response details
                logger.debug(f"[DEBUG] Response content: {repr(response_content[:200]) if response_content else '(empty)'}")
                logger.debug(f"[DEBUG] Response finish_reason: {getattr(response, 'finish_reason', 'N/A')}")
                
                # Check for streaming errors (empty response with error finish_reason)
                if not response_content and hasattr(response, 'finish_reason') and response.finish_reason == "error":
                    logger.error("Streaming response failed with error")
                    raise Exception("Streaming response failed")
                
                # Check for tool calls in response
                # First check if tool_calls exist in the response object (from API)
                # Then fall back to parsing from content text
                tool_calls = []
                
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    # Convert API tool_calls format to ToolCall objects
                    logger.debug(f"[DEBUG] Using tool_calls from API response")
                    for tc in response.tool_calls:
                        # OpenAI API format: {id, type, function: {name, arguments}}
                        tc_id = tc.get("id", f"call_{id(tc)}")
                        func = tc.get("function", {})
                        tc_name = func.get("name", "")
                        tc_args = func.get("arguments", "{}")
                        
                        # Parse arguments as JSON
                        try:
                            args_dict = json.loads(tc_args) if isinstance(tc_args, str) else tc_args
                        except json.JSONDecodeError:
                            args_dict = {"raw": tc_args}
                        
                        tool_calls.append(ToolCall(id=tc_id, name=tc_name, arguments=args_dict))
                else:
                    # Fall back to parsing from content text
                    tool_calls = self._extract_tool_calls(response_content)
                
                # DEBUG: Log tool call extraction results
                logger.debug(f"[DEBUG] Extracted tool_calls: {len(tool_calls)} calls")
                if tool_calls:
                    for tc in tool_calls:
                        logger.debug(f"[DEBUG] Tool call: {tc.name} with args: {tc.arguments}")
                        # Validate tool exists in registry
                        tool_exists = self.tools.get(tc.name) is not None if self.tools else False
                        logger.debug(f"[DEBUG] Tool '{tc.name}' exists in registry: {tool_exists}")
                        if not tool_exists:
                            logger.warning(f"[DIAGNOSTIC] Tool '{tc.name}' not found in registry - possible false positive!")
                
                # DEBUG: Log if response content exists alongside tool calls
                if tool_calls and response_content and len(response_content.strip()) > 20:
                    logger.warning(f"[DIAGNOSTIC] Response has both content ({len(response_content)} chars) AND {len(tool_calls)} tool calls - checking if we should continue")
                    logger.debug(f"[DIAGNOSTIC] Response content preview: {response_content[:200]}...")
                
                if tool_calls:
                    # Filter out tool calls that don't exist in the registry
                    valid_tool_calls = []
                    for tc in tool_calls:
                        tool_exists = self.tools.get(tc.name) is not None if self.tools else False
                        if tool_exists:
                            valid_tool_calls.append(tc)
                        else:
                            logger.warning(f"[OPTIMIZE] Filtering out invalid tool '{tc.name}' - not in registry")
                    
                    # Check if we should use the response content instead of tool calls
                    # If response has meaningful content (not just empty/tool noise), prefer it
                    has_meaningful_content = response_content and len(response_content.strip()) > 50
                    has_only_invalid_tools = len(valid_tool_calls) == 0
                    
                    if has_meaningful_content and has_only_invalid_tools:
                        # Only content, no valid tools - use content as final response
                        logger.info("[OPTIMIZE] Response has meaningful content but only invalid tool calls - using content as response")
                        final_assistant_msg = Message(role="assistant", content=response_content)
                        final_assistant_msg = self._truncate_message(final_assistant_msg)
                        self._history.append(final_assistant_msg)
                        final_response = response_content
                        break
                    
                    if has_meaningful_content and not has_only_invalid_tools:
                        # Both content AND valid tool calls - prefer content for simple tasks
                        # Only use tools if content is very short (seems like an instruction)
                        if len(response_content.strip()) < 100:
                            logger.info("[OPTIMIZE] Short content with valid tools - using tools")
                        else:
                            # Content seems complete - use it instead of tools
                            logger.info("[OPTIMIZE] Content appears complete, ignoring tool calls")
                            final_assistant_msg = Message(role="assistant", content=response_content)
                            final_assistant_msg = self._truncate_message(final_assistant_msg)
                            self._history.append(final_assistant_msg)
                            final_response = response_content
                            break
                    
                    # Use only valid tool calls
                    tool_calls = valid_tool_calls
                    
                    if not tool_calls:
                        # No valid tool calls and no meaningful content
                        logger.warning("[OPTIMIZE] No valid tool calls and no meaningful content")
                        final_response = response_content or "I couldn't process that request."
                        break
                    
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
    
    async def _process_streaming_response(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
    ) -> LLMResponse:
        """Process a streaming response from the LLM provider.
        
        Accumulates all chunks into a full response before processing
        tool calls (which come after content in streaming mode).
        
        Args:
            messages: The messages to send to the LLM
            model: The model to use
            temperature: The temperature setting
            
        Returns:
            LLMResponse with accumulated content
        """
        logger.debug("Starting streaming response processing")
        
        # Get tools for streaming
        openai_tools = self.tools.to_openai_tools() if self.tools else []
        
        # Accumulate chunks
        accumulated_content = ""
        try:
            async for chunk in self.provider.stream(
                messages=messages,
                model=model,
                temperature=temperature,
                tools=openai_tools if openai_tools else None,
            ):
                accumulated_content += chunk
                logger.debug(f"Stream chunk received: {len(chunk)} chars, total: {len(accumulated_content)}")
        except Exception as e:
            logger.error(f"Error during streaming response: {e}")
            # Return empty content on error - the caller will handle the failure
            return LLMResponse(
                content="",
                model=model,
                usage={},
                finish_reason="error"
            )
        
        logger.debug(f"Streaming complete, total content: {len(accumulated_content)} chars")
        
        # Return as LLMResponse for consistent handling
        return LLMResponse(
            content=accumulated_content,
            model=model,
            usage={},  # Usage info not available in streaming
            finish_reason="stop"
        )
    
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
        
        # DEBUG: Log tools being passed to provider
        openai_tools = self.tools.to_openai_tools() if self.tools else []
        logger.debug(f"[DEBUG] Tools available: {[t.get('function', {}).get('name') for t in openai_tools]}")
        logger.debug(f"[DEBUG] Tools count: {len(openai_tools)}")
        # END DEBUG
        
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
        # Save memory on shutdown
        self.memory.save_long_term()
        logger.info("Memory saved on shutdown")
        
        if hasattr(self.provider, 'close'):
            await self.provider.close()
