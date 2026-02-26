"""
Agent loop - the core processing engine.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import httpx

from loguru import logger

if TYPE_CHECKING:
    from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage

from clawlet.agent.identity import Identity
from clawlet.providers.base import BaseProvider, LLMResponse
from clawlet.tools.registry import ToolRegistry, ToolResult, validate_tool_params
from clawlet.agent.memory import MemoryManager
from clawlet.storage.sqlite import SQLiteStorage
from clawlet.config import StorageConfig
from clawlet.metrics import get_metrics


UTC_TZ = timezone.utc



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
        if self.role == "tool":
            tool_call_id = self.metadata.get("tool_call_id")
            if tool_call_id:
                d["tool_call_id"] = tool_call_id
            tool_name = self.metadata.get("tool_name")
            if tool_name:
                d["name"] = tool_name
        return d


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""
    id: str
    name: str
    arguments: dict


@dataclass
class ConversationState:
    """Per-conversation runtime state."""

    session_id: str
    history: list[Message] = field(default_factory=list)


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
    CONTEXT_CHAR_BUDGET = 12000  # Approximate character budget for prompt context
    MAX_TOOL_OUTPUT_CHARS = 4000
    NO_PROGRESS_LIMIT = 3
    TOOL_ALIASES = {
        "list_files": "list_dir",
    }
    
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
        # Validate model parameter
        if not self.model or not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Model must be a non-empty string")
        self.model = self.model.strip()
        self.max_iterations = max_iterations
        
        # Load tool aliases from registry, fall back to class constant for backward compatibility
        self._tool_aliases = self.tools.get_aliases() if self.tools else {}
        if not self._tool_aliases:
            # Use class-level aliases as fallback
            self._tool_aliases = self.TOOL_ALIASES.copy()
        logger.info(f"Loaded tool aliases: {self._tool_aliases}")
        
        # DEBUG: Log available tools at initialization
        if hasattr(self.tools, '_tools'):
            logger.info(f"DEBUG: Registered tools at init: {list(self.tools._tools.keys())}")
        
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
        self._session_id = ""
        self._conversations: dict[str, ConversationState] = {}
        
        # Circuit breaker for provider failures
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5
        self._circuit_open_until: Optional[datetime] = None
        self._circuit_timeout_seconds = 30
        
        # Tool circuit breaker tracking
        self._tool_failures: dict[str, int] = {}
        self._tool_circuit_open_until: dict[str, datetime] = {}
        self._tool_failure_threshold = 3
        self._tool_circuit_timeout_seconds = 60
        self._tool_stats = {
            "calls_requested": 0,
            "calls_executed": 0,
            "calls_rejected": 0,
            "calls_failed": 0,
        }
        
        # Persistence failure tracking
        self._persist_failures = 0
        
        # Event to signal that storage initialization is complete
        self._storage_ready = asyncio.Event()
        self._persist_tasks: set[asyncio.Task] = set()
        
        logger.info(f"AgentLoop initialized with provider={provider.name}, model={self.model}, tools={len(self.tools.all_tools())}")

    def _queue_persist(self, session_id: str, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """Queue persistence task with lifecycle tracking."""
        task = asyncio.create_task(self._persist_message(session_id, role, content, metadata))
        self._persist_tasks.add(task)
        task.add_done_callback(self._persist_tasks.discard)
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        # Ensure storage is initialized
        if not self.storage.is_initialized():
            await self._initialize_storage()
        # Signal that storage is ready (whether initialization succeeded or not)
        self._storage_ready.set()
        
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

    async def clear_conversation(self, channel: str, chat_id: str) -> bool:
        """
        Clear conversation history for a specific channel/chat.
        
        This clears both in-memory history and persisted messages in storage.
        
        Args:
            channel: The channel name (e.g., 'telegram', 'discord')
            chat_id: The chat/conversation ID
            
        Returns:
            True if history was cleared successfully
        """
        key = f"{channel}:{chat_id}"
        
        # Clear in-memory conversation state
        if key in self._conversations:
            self._conversations[key].history.clear()
            logger.info(f"Cleared in-memory history for {key}")
        
        # Generate session ID and clear stored messages
        session_id = self._generate_session_id(channel, chat_id)
        
        try:
            if self.storage.is_initialized():
                # Try clear_messages first (SQLite), fallback to clear_history (PostgreSQL)
                if hasattr(self.storage, 'clear_messages'):
                    await self.storage.clear_messages(session_id)
                elif hasattr(self.storage, 'clear_history'):
                    await self.storage.clear_history(session_id)
                logger.info(f"Cleared stored messages for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear conversation history: {e}")
            return False

    def _generate_session_id(self, channel: str, chat_id: str) -> str:
        """Generate a stable session ID per workspace/channel/chat combination."""
        import hashlib
        seed = f"{self.workspace.resolve()}::{channel}::{chat_id}"
        return hashlib.md5(seed.encode()).hexdigest()[:12]

    async def _get_conversation_state(self, channel: str, chat_id: str) -> ConversationState:
        """Get or create conversation state for an inbound channel/chat."""
        key = f"{channel}:{chat_id}"
        state = self._conversations.get(key)
        if state is not None:
            return state

        session_id = self._generate_session_id(channel, chat_id)
        state = ConversationState(session_id=session_id)

        if self.storage.is_initialized():
            stored_messages = await self.storage.get_messages(session_id, limit=self.MAX_HISTORY)
            for msg in stored_messages:
                state.history.append(Message(role=msg.role, content=msg.content, metadata={}, tool_calls=[]))
            if stored_messages:
                logger.info(f"Loaded {len(stored_messages)} messages for conversation {key}")

        self._conversations[key] = state
        return state

    async def _initialize_storage(self) -> None:
        """Initialize storage and load recent history."""
        try:
            await self.storage.initialize()
            logger.info("Storage initialized")
        except Exception as e:
            logger.error(f"Failed to initialize storage: {e}")
        finally:
            # Signal that storage initialization attempt has completed
            self._storage_ready.set()

    async def _persist_message(self, session_id: str, role: str, content: str, metadata: dict = None) -> None:
        """Persist a message to storage and long-term memory."""
        # Wait for storage to be ready (initialization attempt completed)
        if not self._storage_ready.is_set():
            await self._storage_ready.wait()
        
        # Save to storage
        try:
            if self.storage.is_initialized():
                await self.storage.store_message(
                    session_id=session_id,
                    role=role,
                    content=content
                )
                # Reset failure count on success
                self._persist_failures = 0
            else:
                # Storage not initialized (initialization failed), skip DB persistence
                logger.debug("Storage not initialized, skipping DB persistence")
        except Exception as e:
            logger.warning(f"Failed to store message in DB: {e}")
            # Increment storage error metric
            get_metrics().inc_storage_errors()
            self._persist_failures += 1
            if self._persist_failures >= 5:
                logger.error("Too many storage failures, aborting persistence.")
                raise
        
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
            
            key = f"{role}_{session_id}_{int(datetime.now(UTC_TZ).timestamp())}"
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
        now = datetime.now(UTC_TZ)
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
                    tools=self.tools.to_openai_tools(),
                    tool_choice="auto",
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
        convo = await self._get_conversation_state(channel, chat_id)
        self._session_id = convo.session_id
        self._history = convo.history
        
        # Get metrics instance
        metrics = get_metrics()
        
        # Validate input size (max 10k chars)
        if len(user_message) > 10000:
            logger.warning(f"Message from {chat_id} exceeds 10k chars, truncating")
            user_message = user_message[:10000]
        
        logger.info(f"Processing message from {channel}/{chat_id}: {user_message[:50]}...")
        
        # Add to history
        convo.history.append(Message(role="user", content=user_message))
        # Persist message
        self._queue_persist(convo.session_id, "user", user_message)
        
        # Trim history periodically
        self._trim_history(convo.history)
        
        # Iterative tool calling loop
        iteration = 0
        final_response = None
        is_error = False
        no_progress_count = 0
        last_signature: Optional[str] = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Build messages for LLM
            messages = self._build_messages(convo.history)
            
            try:
                # Call LLM provider with retry and circuit breaker
                response: LLMResponse = await self._call_provider_with_retry(messages)
                
                response_content = response.content
                
                # Prefer provider-native tool calls; fallback to text parser.
                tool_calls = self._extract_provider_tool_calls(response)
                if not tool_calls:
                    tool_calls = self._extract_tool_calls(response_content)

                # Detect repeated no-progress loop signatures.
                signature = json.dumps(
                    {
                        "content": response_content[:500],
                        "tool_calls": [{"name": t.name, "args": t.arguments} for t in tool_calls],
                    },
                    sort_keys=True,
                )
                if signature == last_signature:
                    no_progress_count += 1
                else:
                    no_progress_count = 0
                last_signature = signature

                if no_progress_count >= self.NO_PROGRESS_LIMIT:
                    logger.warning("Stopping loop due to repeated no-progress model responses")
                    final_response = "I am stuck repeating the same step. Please refine your request."
                    is_error = True
                    break
                
                if tool_calls:
                    self._tool_stats["calls_requested"] += len(tool_calls)
                    # Add assistant message with tool calls
                    convo.history.append(Message(
                        role="assistant",
                        content=response_content,
                        tool_calls=[
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in tool_calls
                        ]
                    ))
                    self._queue_persist(convo.session_id, "assistant", response_content)
                    
                    # Execute each tool call
                    for tc in tool_calls:
                        # Map tool name early for use in both execution and metadata
                        requested_tool_name = tc.name
                        mapped_tool_name = self._tool_aliases.get(requested_tool_name, requested_tool_name)
                        if mapped_tool_name != requested_tool_name:
                            logger.info(f"Mapping tool alias '{requested_tool_name}' -> '{mapped_tool_name}'")
                        
                        # Execute with mapped name
                        tc.name = mapped_tool_name
                        result = await self._execute_tool(tc)
                        rendered_tool_output = self._render_tool_result(result)
                        
                        # Add tool result to history - use mapped name in metadata
                        convo.history.append(Message(
                            role="tool",
                            content=rendered_tool_output,
                            metadata={"tool_call_id": tc.id, "tool_name": mapped_tool_name}
                        ))
                        self._queue_persist(convo.session_id, "tool", rendered_tool_output)
                    
                    # Continue loop to get next response
                    continue
                
                # No tool calls - this is the final response
                convo.history.append(Message(role="assistant", content=response_content))
                self._queue_persist(convo.session_id, "assistant", response_content)
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

    def _extract_provider_tool_calls(self, response: LLMResponse) -> list[ToolCall]:
        """Normalize provider-native tool calls into internal ToolCall objects."""
        if not response.tool_calls:
            return []

        normalized: list[ToolCall] = []
        for i, call in enumerate(response.tool_calls):
            if not isinstance(call, dict):
                continue

            call_id = call.get("id") or f"provider_call_{i}"
            function_payload = call.get("function", {}) if isinstance(call.get("function"), dict) else {}
            name = function_payload.get("name") or call.get("name")
            raw_arguments = function_payload.get("arguments", call.get("arguments", {}))

            if not name:
                logger.warning("Skipping provider tool call without name")
                continue

            if isinstance(raw_arguments, str):
                try:
                    raw_arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    logger.warning(f"Skipping tool call '{name}' due to invalid JSON arguments")
                    continue

            if not isinstance(raw_arguments, dict):
                raw_arguments = {"value": raw_arguments}

            normalized.append(ToolCall(id=call_id, name=name, arguments=raw_arguments))

        if normalized:
            logger.info(f"Using {len(normalized)} provider-native tool call(s)")

        return normalized

    def _render_tool_result(self, result: ToolResult) -> str:
        """Render bounded tool output for history/context safety."""
        raw = result.output if result.success else f"Error: {result.error}"
        if len(raw) <= self.MAX_TOOL_OUTPUT_CHARS:
            return raw

        head = raw[: self.MAX_TOOL_OUTPUT_CHARS // 2]
        tail = raw[-self.MAX_TOOL_OUTPUT_CHARS // 2 :]
        omitted = len(raw) - len(head) - len(tail)
        return f"{head}\n\n...[truncated {omitted} chars]...\n\n{tail}"
    
    def _extract_tool_calls(self, content: str) -> list[ToolCall]:
        """Extract tool calls from LLM response content."""
        tool_calls = []

        # Handle raw JSON tool call payloads (common provider behavior)
        stripped = content.strip()
        if stripped and (stripped.startswith("{") or stripped.startswith("[")):
            try:
                raw = json.loads(stripped)
                if isinstance(raw, dict) and "name" in raw:
                    args = raw.get("arguments", raw.get("parameters", {}))
                    if not isinstance(args, dict):
                        args = {"value": args}
                    tool_calls.append(ToolCall(id="call_raw_json_0", name=raw["name"], arguments=args))
                elif isinstance(raw, list):
                    for i, item in enumerate(raw):
                        if isinstance(item, dict) and "name" in item:
                            args = item.get("arguments", item.get("parameters", {}))
                            if not isinstance(args, dict):
                                args = {"value": args}
                            tool_calls.append(ToolCall(id=f"call_raw_json_{i}", name=item["name"], arguments=args))
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls
        
        logger.debug(f"Tool-call parser fallback on content length={len(content)}")
        
        # Check for MCP-like format first
        if "<function=" in content:
            logger.info("Found MCP-like format in content, using ToolCallParser")
            from clawlet.agent.tool_parser import ToolCallParser
            parser = ToolCallParser()
            parsed = parser.parse(content)
            logger.info(f"ToolCallParser found {len(parsed)} tool calls")
            for p in parsed:
                tool_calls.append(ToolCall(
                    id=p.id,
                    name=p.name,
                    arguments=p.arguments,
                ))
        
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
        """Execute a tool call with circuit breaker protection."""
        # Use the already-mapped name from the tool call (set in the loop)
        # But also check for aliases in case this method is called directly
        requested_tool_name = tool_call.name
        tool_name = self._tool_aliases.get(requested_tool_name, requested_tool_name)
        if tool_name != requested_tool_name:
            logger.info(f"Mapping tool alias '{requested_tool_name}' -> '{tool_name}'")
            tool_call.name = tool_name  # Update the tool call name
        now = datetime.now(UTC_TZ)
        
        # Check if circuit is open for this tool
        if tool_name in self._tool_circuit_open_until:
            if now < self._tool_circuit_open_until[tool_name]:
                # Circuit is open, skip execution
                logger.warning(f"Circuit open for tool '{tool_name}'. Skipping execution.")
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Tool '{tool_name}' is temporarily unavailable due to repeated failures.",
                )
            else:
                # Circuit timeout expired, reset
                logger.info(f"Circuit breaker timeout for tool '{tool_name}' expired, allowing test call")
                self._tool_circuit_open_until.pop(tool_name, None)
                self._tool_failures[tool_name] = 0  # reset failures
        
        logger.info(f"Executing tool: {tool_name} with args: {tool_call.arguments}")

        # DEBUG: Log available tools when tool is not found
        if self.tools.get(tool_name) is None:
            logger.warning(f"Rejected unknown tool call: {tool_name}")
            logger.warning(f"DEBUG: Available tools: {list(self.tools._tools.keys()) if hasattr(self.tools, '_tools') else 'N/A'}")
            self._tool_stats["calls_rejected"] += 1
            return ToolResult(success=False, output="", error=f"Unknown tool: {tool_name}")

        # Validate tool invocation before execution.
        tool = self.tools.get(tool_name)
        schema = tool.parameters_schema if tool else None
        valid, error_msg, sanitized = validate_tool_params(
            tool_name=tool_name,
            params=tool_call.arguments,
            schema=schema,
        )
        if not valid:
            logger.warning(f"Rejected tool call for '{tool_name}': {error_msg}")
            self._tool_stats["calls_rejected"] += 1
            return ToolResult(success=False, output="", error=f"Invalid tool call: {error_msg}")
        args = sanitized.get("params", tool_call.arguments)
        
        try:
            result = await self.tools.execute(tool_name, **args)
            self._tool_stats["calls_executed"] += 1
        except Exception as e:
            # Unexpected exception, wrap in ToolResult
            result = ToolResult(success=False, output="", error=str(e))
        
        if result.success:
            # Reset failure count on success
            if tool_name in self._tool_failures:
                self._tool_failures[tool_name] = 0
            logger.info(f"Tool {tool_name} succeeded: {result.output[:100]}...")
        else:
            self._tool_stats["calls_failed"] += 1
            # Increment failure count
            failures = self._tool_failures.get(tool_name, 0) + 1
            self._tool_failures[tool_name] = failures
            # Increment tool error metric
            get_metrics().inc_tool_errors()
            logger.warning(f"Tool {tool_name} failed: {result.error} (failures: {failures})")
            
            if failures >= self._tool_failure_threshold:
                # Trip circuit breaker
                open_until = now + timedelta(seconds=self._tool_circuit_timeout_seconds)
                self._tool_circuit_open_until[tool_name] = open_until
                logger.error(f"Circuit breaker tripped for tool '{tool_name}'! Open until {open_until.isoformat()}")
        
        return result
    
    def _build_messages(self, history: list[Message]) -> list[dict]:
        """Build messages list for LLM."""
        messages = []
        
        # System prompt from identity (include tools)
        tools_list = self.tools.all_tools() if self.tools else None
        system_prompt = self.identity.build_system_prompt(
            tools=tools_list,
            workspace_path=str(self.workspace)
        )
        messages.append({"role": "system", "content": system_prompt})
        
        # Add recent history (limited by CONTEXT_WINDOW)
        recent = history[-self.CONTEXT_WINDOW:]
        while recent:
            content_size = sum(len((m.content or "")) for m in recent)
            if content_size <= self.CONTEXT_CHAR_BUDGET:
                break
            recent = recent[1:]
        
        for msg in recent:
            msg_dict = msg.to_dict()
            # Skip tool messages without tool_call_id (they cause API errors)
            # This can happen when messages are loaded from storage without metadata
            if msg.role == "tool" and not msg_dict.get("tool_call_id"):
                logger.warning(
                    f"Skipping tool message without tool_call_id: {msg.content[:50]}..."
                )
                continue
            messages.append(msg_dict)
        
        return messages
    
    def _trim_history(self, history: list[Message]) -> None:
        """Trim history to prevent unbounded growth."""
        if len(history) > self.MAX_HISTORY:
            # Keep the most recent messages
            del history[:-self.MAX_HISTORY]
            logger.debug(f"Trimmed history to {len(history)} messages")
    
    def clear_history(self) -> None:
        """Clear all history."""
        for state in self._conversations.values():
            state.history.clear()
        self._history.clear()
        logger.info("Agent history cleared")
    
    def get_history_length(self) -> int:
        """Get current history length."""
        return sum(len(state.history) for state in self._conversations.values())
    
    async def close(self):
        """Clean up resources."""
        if self._persist_tasks:
            logger.info(f"Waiting for {len(self._persist_tasks)} persistence tasks to complete")
            await asyncio.gather(*list(self._persist_tasks), return_exceptions=True)

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

        logger.info(
            "Tool stats: requested={calls_requested}, executed={calls_executed}, "
            "rejected={calls_rejected}, failed={calls_failed}".format(**self._tool_stats)
        )
