"""
Agent loop - the core processing engine.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import httpx

from loguru import logger

if TYPE_CHECKING:
    from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage

from clawlet.agent.identity import Identity
from clawlet.providers.base import BaseProvider, LLMResponse
from clawlet.tools.registry import ToolRegistry, ToolResult
from clawlet.agent.memory import MemoryManager
from clawlet.storage.sqlite import SQLiteStorage
from clawlet.config import StorageConfig
from clawlet.metrics import get_metrics



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
        storage_config: Optional[StorageConfig] = None,
    ):
        self.bus = bus
        self.workspace = workspace
        self.identity = identity
        self.provider = provider
        self.tools = tools or ToolRegistry()
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        
        # Initialize memory manager (long-term persistence to MEMORY.md)
        self.memory = MemoryManager(workspace)
        
        # Initialize storage backend (SQLite for message history)
        if storage_config is None:
            storage_config = StorageConfig(backend="sqlite")
        
        if storage_config.backend == "sqlite":
            db_path = Path(storage_config.sqlite.path).expanduser()
            self.storage = SQLiteStorage(db_path)
        elif storage_config.backend == "postgres":
            from clawlet.storage.postgres import PostgresStorage
            pg = storage_config.postgres
            self.storage = PostgresStorage(
                host=pg.host,
                port=pg.port,
                database=pg.database,
                user=pg.user,
                password=pg.password,
            )
        else:
            raise ValueError(f"Unsupported storage backend: {storage_config.backend}")
        
        # Initialize storage and load recent history
        self._running = False
        self._history: list[Message] = []
        self._session_id = self._generate_session_id()
        
        # Circuit breaker for provider failures
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5
        self._circuit_open_until: Optional[datetime] = None
        self._circuit_timeout_seconds = 30
        
        logger.info(f"AgentLoop initialized with provider={provider.name}, model={self.model}, tools={len(self.tools.all_tools())}")
    
    async def _initialize_storage(self) -> None:
        """Initialize storage and load recent history."""
        try:
            await self.storage.initialize()
            # Load recent messages from storage to populate history
            stored_messages = await self.storage.get_messages(self._session_id, limit=self.MAX_HISTORY)
            # stored are in chronological order (oldest first due to reversal), convert to our Message format
            for msg in stored_messages:
                self._history.append(Message(
                    role=msg.role,
                    content=msg.content,
                    metadata={},
                    tool_calls=[]
                ))
            logger.info(f"Loaded {len(self._history)} messages from storage")
        except Exception as e:
            logger.error(f"Failed to initialize storage: {e}")
            # Continue without storage — will use in-memory only

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        # Ensure storage is initialized
        if not hasattr(self.storage, '_db') or self.storage._db is None:
            await self._initialize_storage()
        
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


    def _generate_session_id(self) -> str:
        """Generate a unique session ID based on workspace and start time."""
        import hashlib
        seed = f"{self.workspace}-{datetime.now(UTC).isoformat()}"
        return hashlib.md5(seed.encode()).hexdigest()[:12]

    async def _initialize_storage(self) -> None:
        """Initialize storage and load recent history."""
        try:
            await self.storage.initialize()
            # Load recent messages from storage to populate history
            stored_messages = await self.storage.get_messages(self._session_id, limit=self.MAX_HISTORY)
            for msg in stored_messages:
                self._history.append(Message(
                    role=msg.role,
                    content=msg.content,
                    metadata={},
                    tool_calls=[]
                ))
            logger.info(f"Loaded {len(self._history)} messages from storage")
        except Exception as e:
            logger.error(f"Failed to initialize storage: {e}")

    async def _persist_message(self, role: str, content: str, metadata: dict = None) -> None:
        """Persist a message to storage and long-term memory."""
        # Save to storage
        try:
            if hasattr(self.storage, "_db") and self.storage._db:
                await self.storage.store_message(
                    session_id=self._session_id,
                    role=role,
                    content=content
                )
        except Exception as e:
            logger.warning(f"Failed to store message in DB: {e}")
        
        # Save to long-term memory (MEMORY.md) — only important messages
        if role in ("assistant", "user"):
            importance = 5
            if role == "assistant":
                importance = 7
            if len(content) > 200:
                importance += 1
            keywords = ["important", "remember", "todo", "task", "remind", "note", "save", "key", "critical"]
            if any(k in content.lower() for k in keywords):
                importance += 2
            
            key = f"{role}_{len(self._history)}_{int(datetime.now(UTC).timestamp())}"
            try:
                self.memory.remember(
                    key=key,
                    value=content,
                    category="conversation",
                    importance=importance
                )
            except Exception as e:
                logger.warning(f"Failed to save to memory: {e}")
    
    async def _call_provider_with_retry(self, messages: list[dict]) -> LLMResponse:
        """Call LLM provider with retry, exponential backoff, and circuit breaker."""
        # Check circuit breaker first
        now = datetime.now(UTC)
        if self._circuit_open_until and now < self._circuit_open_until:
            raise RuntimeError(f"Circuit breaker open until {self._circuit_open_until.isoformat()}")
        elif self._circuit_open_until and now >= self._circuit_open_until:
            logger.info("Circuit breaker timeout elapsed, resetting")
            self._circuit_open_until = None
            self._consecutive_errors = 0
        
        max_retries = 3
        base_delay = 2  # seconds
        start_time = time.time()
        
        for attempt in range(1, max_retries + 1):
            try:
                response = await self.provider.complete(
                    messages=messages,
                    model=self.model,
                    temperature=0.7,
                )
                # Success: reset error counter
                self._consecutive_errors = 0
                elapsed = time.time() - start_time
                if elapsed > 10.0:
                    logger.warning(f"LLM call took {elapsed:.2f}s (exceeds 10s threshold)")
                else:
                    logger.debug(f"LLM call completed in {elapsed:.2f}s")
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                self._consecutive_errors += 1
                logger.warning(f"Provider call failed (attempt {attempt}/{max_retries}): {e}")
                if attempt >= max_retries:
                    # Check if we need to trip circuit breaker
                    if self._consecutive_errors >= self._max_consecutive_errors:
                        self._circuit_open_until = now + timedelta(seconds=self._circuit_timeout_seconds)
                        logger.error(f"Circuit breaker tripped! Open until {self._circuit_open_until.isoformat()}")
                    raise
                # Exponential backoff
                delay = base_delay * (2 ** (attempt - 1))
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)
        raise RuntimeError("Unreachable: retry loop exhausted")

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
        
        # Get metrics instance
        metrics = get_metrics()
        
        # Validate input size (max 10k chars)
        if len(user_message) > 10000:
            logger.warning(f"Message from {chat_id} exceeds 10k chars, truncating")
            user_message = user_message[:10000]
        
        logger.info(f"Processing message from {channel}/{chat_id}: {user_message[:50]}...")
        
        # Add to history
        self._history.append(Message(role="user", content=user_message))
        # Persist message
        asyncio.create_task(self._persist_message("user", user_message))
        
        # Trim history periodically
        self._trim_history()
        
        # Iterative tool calling loop
        iteration = 0
        final_response = None
        is_error = False
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Build messages for LLM
            messages = self._build_messages()
            
            try:
                # Call LLM provider with retry and circuit breaker
                response: LLMResponse = await self._call_provider_with_retry(messages)
                
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
                    asyncio.create_task(self._persist_message("assistant", response_content))
                    
                    # Execute each tool call
                    for tc in tool_calls:
                        result = await self._execute_tool(tc)
                        
                        # Add tool result to history
                        self._history.append(Message(
                            role="tool",
                            content=result.output if result.success else f"Error: {result.error}",
                            metadata={"tool_call_id": tc.id, "tool_name": tc.name}
                        ))
                        asyncio.create_task(self._persist_message("tool", result.output if result.success else f"Error: {result.error}"))
                    
                    # Continue loop to get next response
                    continue
                
                # No tool calls - this is the final response
                self._history.append(Message(role="assistant", content=response_content))
                asyncio.create_task(self._persist_message("assistant", response_content))
                final_response = response_content
                break
                
            except Exception as e:
                logger.error(f"Error in agent loop iteration {iteration}: {e}")
                final_response = f"Sorry, I encountered an error: {str(e)}"
                is_error = True
                break
        
        if final_response is None:
            final_response = "I reached my maximum number of iterations. Please try again."
            is_error = True
        
        logger.info(f"Final response: {len(final_response)} chars (iterations: {iteration})")
        
        # Update metrics
        if is_error:
            metrics.inc_errors()
        else:
            metrics.inc_messages()
        
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
        # Save long-term memories
        try:
            self.memory.save_long_term()
        except Exception as e:
            logger.error(f"Failed to save long-term memory: {e}")
        
        # Close storage
        try:
            await self.storage.close()
        except Exception as e:
            logger.error(f"Failed to close storage: {e}")
        
        # Close provider
        if hasattr(self.provider, 'close'):
            await self.provider.close()
