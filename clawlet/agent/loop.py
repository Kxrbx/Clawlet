"""
Agent loop - the core processing engine.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import asdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from uuid import uuid4
import httpx

from loguru import logger

if TYPE_CHECKING:
    from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage

from clawlet.agent.identity import Identity
from clawlet.agent.memory import MemoryManager
from clawlet.providers.base import BaseProvider, LLMResponse
from clawlet.tools.registry import ToolRegistry, ToolResult, validate_tool_params
from clawlet.agent.memory import MemoryManager
from clawlet.storage.sqlite import SQLiteStorage
from clawlet.config import RuntimeSettings, StorageConfig
from clawlet.context import ContextEngine
from clawlet.metrics import get_metrics
from clawlet.runtime import (
    EVENT_CHANNEL_FAILED,
    EVENT_PROVIDER_FAILED,
    EVENT_RUN_COMPLETED,
    EVENT_RUN_STARTED,
    EVENT_SCHEDULED_RUN_COMPLETED,
    EVENT_SCHEDULED_RUN_FAILED,
    EVENT_SCHEDULED_RUN_STARTED,
    SCHED_PAYLOAD_JOB_ID,
    SCHED_PAYLOAD_RUN_ID,
    SCHED_PAYLOAD_SESSION_TARGET,
    SCHED_PAYLOAD_SOURCE,
    SCHED_PAYLOAD_WAKE_MODE,
    EVENT_STORAGE_FAILED,
    DeterministicToolRuntime,
    RecoveryManager,
    RuntimeEvent,
    RuntimeEventStore,
    RuntimePolicyEngine,
    RunCheckpoint,
    ToolCallEnvelope,
)
from clawlet.runtime.failures import classify_error_text, classify_exception, to_payload as failure_payload
from clawlet.runtime.rust_bridge import is_available as rust_core_available


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
    summary: str = ""


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
    MAX_TOOL_OUTPUT_CHARS = 4000
    NO_PROGRESS_LIMIT = 3
    MAX_TOOL_CALLS_PER_MESSAGE = 20
    MAX_AUTONOMOUS_FOLLOWUP_DEPTH = 1
    TOOL_ALIASES = {
        "list_files": "list_dir",
    }
    INSTALL_KEYWORDS = ("install", "add", "setup", "set up")
    TOOL_INTENT_PATTERNS = [
        r"\blist\b",
        r"\bliste\b",
        r"\binstall\b",
        r"\bsearch\b",
        r"\brecherche\b",
        r"\bcherche\b",
        r"\bfind\b",
        r"\btrouve\b",
        r"\blook up\b",
        r"\blatest\b",
        r"\bcurrent\b",
        r"\bnews\b",
        r"\bweb\b",
        r"\bprice\b",
        r"\bweather\b",
        r"\bstock\b",
        r"\bfile\b",
        r"\bfiles\b",
        r"\bfolder\b",
        r"\bfolders\b",
        r"\bdossier\b",
        r"\bdossiers\b",
        r"\bdirectory\b",
        r"\bdirectories\b",
        r"\bworkspace\b",
        r"\bespace de travail\b",
        r"\bcontent\b",
        r"\bcontents\b",
        r"\bcontenu\b",
        r"\bread\b",
        r"\blire\b",
        r"\bwrite\b",
        r"\bécrire\b",
        r"\bedit\b",
        r"\bmodifier\b",
        r"\bcreate\b",
        r"\bcréer\b",
        r"\bdelete\b",
        r"\bsupprimer\b",
        r"\brun\b",
        r"\bexecute\b",
        r"\bexécuter\b",
        r"\bcommand\b",
        r"\bcommande\b",
        r"\bshell\b",
        r"\bgit\b",
        r"\bgithub\b",
        r"\bclawhub\b",
        r"\bskill\b",
        r"\bapi\b",
        r"\burl\b",
        r"https?://",
        r"`[^`]+`",
    ]
    AUTONOMOUS_COMMITMENT_PATTERN = re.compile(
        r"\b(i will|i'll|i am going to|i'm going to|let me)\b.*\b"
        r"(install|search|check|look|find|fetch|download|read|open|run|execute|create|update|send|handle|do)\b",
        re.IGNORECASE,
    )
    AUTONOMOUS_BLOCKING_PATTERN = re.compile(
        r"\b(would you like|do you want|can you confirm|please confirm|which one|"
        r"i need|i can't|cannot|unable|if you want)\b",
        re.IGNORECASE,
    )
    AUTONOMOUS_EXECUTION_NUDGE = (
        "Autonomous execution mode: do not promise future action. "
        "Either use tools now to perform the task, or reply with a concrete blocker explaining why "
        "the action could not be executed automatically."
    )
    COMMITMENT_FOLLOWTHROUGH_NUDGE = (
        "Do not narrate future action. "
        "If you said you would do something, perform the next concrete step now using tools when needed. "
        "Only reply to the user after you have either completed the action or hit a concrete blocker."
    )
    POST_TOOL_FINALIZATION_NUDGE = (
        "You have already used tools in this turn. "
        "Do not send intermediate status updates or describe next steps. "
        "Either provide the final answer grounded in the tool results you already have, "
        "or explain the concrete blocker that prevents completion."
    )
    CONTINUATION_PATTERN = re.compile(
        r"\b(let me|i'll|i will|i am going to|i'm going to|then)\b|"
        r"\bcontent was truncated\b|"
        r"\bfetch the full\b|"
        r"\bdownload the\b|"
        r"\bread the full\b",
        re.IGNORECASE,
    )
    FINAL_RESPONSE_CONTINUATION_SPLIT = re.compile(
        r"\b(now i need to|next i need to|next i'll|next i will|let me)\b",
        re.IGNORECASE,
    )
    URL_PATTERN = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)
    
    def __init__(
        self,
        bus: "MessageBus",
        workspace: Path,
        identity: Identity,
        provider: BaseProvider,
        tools: Optional[ToolRegistry] = None,
        memory_manager: Optional[MemoryManager] = None,
        model: Optional[str] = None,
        max_iterations: int = 50,
        max_tool_calls_per_message: Optional[int] = None,
        storage_config: Optional[StorageConfig] = None,
        runtime_config: Optional[RuntimeSettings] = None,
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
        self.max_tool_calls_per_message = max(
            1,
            int(max_tool_calls_per_message or self.MAX_TOOL_CALLS_PER_MESSAGE),
        )
        
        # Load registry aliases and merge class defaults for backward compatibility.
        self._tool_aliases = self.TOOL_ALIASES.copy()
        if self.tools:
            self._tool_aliases.update(self.tools.get_aliases())
        logger.info(f"Loaded tool aliases: {self._tool_aliases}")
        
        
        # Initialize memory manager (long-term persistence to MEMORY.md)
        self.memory = memory_manager or MemoryManager(workspace)
        
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
        self._current_run_id = ""
        self._current_channel = ""
        self._current_chat_id = ""
        self._current_user_id = ""
        self._current_user_name = ""
        self._current_source = ""
        self._last_route: dict[str, str] = {}
        self._conversations: dict[str, ConversationState] = {}
        self._pending_confirmations: dict[str, dict] = {}
        
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
            "parallel_batches": 0,
            "parallel_batch_tools": 0,
            "serial_batches": 0,
        }
        
        # Persistence failure tracking
        self._persist_failures = 0
        
        # Event to signal that storage initialization is complete
        self._storage_ready = asyncio.Event()
        self._persist_tasks: set[asyncio.Task] = set()

        # Deterministic runtime + replay infrastructure
        self.runtime_config = runtime_config or RuntimeSettings()
        self._runtime_engine = self.runtime_config.engine
        self._enable_parallel_read_batches = bool(
            getattr(self.runtime_config, "enable_parallel_read_batches", True)
        )
        self._max_parallel_read_tools = max(1, int(getattr(self.runtime_config, "max_parallel_read_tools", 4) or 4))
        if self._runtime_engine == "hybrid_rust" and not rust_core_available():
            logger.warning("runtime.engine=hybrid_rust requested but Rust core is unavailable; falling back to python")
            self._runtime_engine = "python"
        replay_dir = Path(self.runtime_config.replay.directory).expanduser()
        if not replay_dir.is_absolute():
            replay_dir = self.workspace / replay_dir
        event_path = replay_dir / "events.jsonl"
        self._event_store = RuntimeEventStore(
            event_path,
            redact_tool_output=self.runtime_config.replay.redact_tool_outputs,
            validate_events=self.runtime_config.replay.validate_events,
            validation_mode=self.runtime_config.replay.validation_mode,
        )
        allowed_modes = tuple(self.runtime_config.policy.allowed_modes)  # type: ignore[arg-type]
        require_approval_for = tuple(self.runtime_config.policy.require_approval_for)  # type: ignore[arg-type]
        self._runtime_policy = RuntimePolicyEngine(
            allowed_modes=allowed_modes or ("read_only", "workspace_write"),
            require_approval_for=require_approval_for or ("elevated",),
        )
        self._tool_runtime = DeterministicToolRuntime(
            registry=self.tools,
            event_store=self._event_store,
            policy=self._runtime_policy,
            enable_idempotency=self.runtime_config.enable_idempotency_cache,
            engine=self._runtime_engine,
            remote_executor=self._build_remote_executor(),
            lane_defaults=dict(self.runtime_config.policy.lanes),
        )
        self._context_engine = ContextEngine(workspace=self.workspace, cache_dir=replay_dir / "context")
        self._recovery_manager = RecoveryManager(replay_dir / "checkpoints")
        
        logger.info(
            "AgentLoop initialized with provider=%s, model=%s, tools=%s, max_tool_calls_per_message=%s"
            % (
                provider.name,
                self.model,
                len(self.tools.all_tools()),
                self.max_tool_calls_per_message,
            )
        )

    def _build_remote_executor(self):
        """Create optional remote executor (local-first fallback when unavailable)."""
        remote_cfg = getattr(self.runtime_config, "remote", None)
        if not remote_cfg or not getattr(remote_cfg, "enabled", False):
            return None
        endpoint = str(getattr(remote_cfg, "endpoint", "") or "").strip()
        if not endpoint:
            logger.warning("runtime.remote.enabled=true but endpoint is empty; remote execution disabled")
            return None
        api_key_env = str(getattr(remote_cfg, "api_key_env", "CLAWLET_REMOTE_API_KEY") or "CLAWLET_REMOTE_API_KEY")
        api_key = os.environ.get(api_key_env, "")
        timeout_seconds = float(getattr(remote_cfg, "timeout_seconds", 60.0) or 60.0)
        try:
            from clawlet.runtime.remote import RemoteToolExecutor

            logger.info(f"Remote executor enabled at {endpoint}")
            return RemoteToolExecutor(endpoint=endpoint, api_key=api_key, timeout_seconds=timeout_seconds)
        except Exception as e:
            logger.warning(f"Remote executor unavailable; using local-only execution: {e}")
            return None

    def _queue_persist(self, session_id: str, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """Queue persistence task with lifecycle tracking."""
        task = asyncio.create_task(self._persist_message(session_id, role, content, metadata))
        self._persist_tasks.add(task)
        task.add_done_callback(self._persist_tasks.discard)

    def _next_run_id(self, session_id: str) -> str:
        """Generate a deterministic-looking unique run identifier."""
        return f"{session_id}-{uuid4().hex[:12]}"

    def _emit_runtime_event(self, event_type: str, session_id: str, payload: Optional[dict] = None) -> None:
        """Persist structured runtime event for replay/diagnostics."""
        if not self.runtime_config.replay.enabled:
            return
        if not self._current_run_id:
            return
        self._event_store.append(
            RuntimeEvent(
                event_type=event_type,
                run_id=self._current_run_id,
                session_id=session_id,
                payload=payload or {},
            )
        )

    def _save_checkpoint(self, stage: str, iteration: int = 0, notes: str = "") -> None:
        """Persist checkpoint for interrupted-run recovery."""
        if not self._current_run_id or not self._session_id:
            return
        pending = self._pending_confirmations.get(f"{self._current_channel}:{self._current_chat_id}") or {}
        checkpoint = RunCheckpoint(
            run_id=self._current_run_id,
            session_id=self._session_id,
            channel=self._current_channel,
            chat_id=self._current_chat_id,
            stage=stage,
            iteration=iteration,
            user_message=self._history[-1].content if self._history and self._history[-1].role == "user" else "",
            user_id=self._current_user_id,
            user_name=self._current_user_name,
            tool_stats=dict(self._tool_stats),
            pending_confirmation=pending,
            notes=notes,
        )
        self._recovery_manager.save(checkpoint)

    def _complete_checkpoint(self) -> None:
        """Mark current run as completed."""
        if not self._current_run_id:
            return
        self._recovery_manager.mark_completed(self._current_run_id)

    async def resume_checkpoint(self, run_id: str) -> bool:
        """Resume an interrupted run by queueing a recovery inbound message."""
        payload = self._recovery_manager.build_resume_message(run_id)
        if not payload:
            return False
        from clawlet.bus.queue import InboundMessage

        await self.bus.publish_inbound(InboundMessage(**payload))
        return True
    
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
                        await self._publish_outbound_with_retry(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    from clawlet.bus.queue import OutboundMessage
                    await self._publish_outbound_with_retry(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=self._format_user_facing_error(e)
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

    def get_last_route(self) -> Optional[dict[str, str]]:
        """Return best-effort last active route for heartbeat target='last'."""
        if not self._last_route.get("channel") or not self._last_route.get("chat_id"):
            return None
        return dict(self._last_route)

    def get_runtime_status(self, channel: str, chat_id: str) -> dict:
        """Expose lightweight per-chat runtime state for channel UX surfaces."""
        key = f"{channel}:{chat_id}"
        state = self._conversations.get(key)
        pending = self._pending_confirmations.get(key) or {}
        return {
            "channel": channel,
            "chat_id": chat_id,
            "session_id": state.session_id if state else self._generate_session_id(channel, chat_id),
            "history_messages": len(state.history) if state else 0,
            "pending_confirmation": bool(pending),
            "pending_confirmation_token": pending.get("token", ""),
            "pending_confirmation_tool": getattr(pending.get("tool_call"), "name", ""),
            "current_run_id": self._current_run_id if channel == self._current_channel and chat_id == self._current_chat_id else "",
            "last_route": dict(self._last_route),
        }

    def peek_pending_confirmation(self, channel: str, chat_id: str) -> Optional[dict]:
        """Return pending confirmation details for the given route if one exists."""
        pending = self._pending_confirmations.get(f"{channel}:{chat_id}")
        if not pending:
            return None
        tool_call = pending.get("tool_call")
        return {
            "token": pending.get("token", ""),
            "tool_name": getattr(tool_call, "name", ""),
            "arguments": dict(getattr(tool_call, "arguments", {}) or {}),
        }

    def _build_outbound_metadata(
        self,
        *,
        source: str,
        is_heartbeat: bool,
        heartbeat_ack_max_chars: int,
        scheduled_payload: Optional[dict],
        extra: Optional[dict] = None,
    ) -> dict:
        metadata = {
            "source": source,
            "heartbeat": is_heartbeat,
            "ack_max_chars": heartbeat_ack_max_chars,
            SCHED_PAYLOAD_JOB_ID: scheduled_payload.get(SCHED_PAYLOAD_JOB_ID) if scheduled_payload else "",
            SCHED_PAYLOAD_RUN_ID: scheduled_payload.get(SCHED_PAYLOAD_RUN_ID) if scheduled_payload else "",
            SCHED_PAYLOAD_SESSION_TARGET: scheduled_payload.get(SCHED_PAYLOAD_SESSION_TARGET) if scheduled_payload else "",
            SCHED_PAYLOAD_WAKE_MODE: scheduled_payload.get(SCHED_PAYLOAD_WAKE_MODE) if scheduled_payload else "",
        }
        if extra:
            metadata.update(extra)
        return metadata

    async def _publish_progress_update(
        self,
        event_type: str,
        text: str,
        *,
        detail: str = "",
        final: bool = False,
    ) -> None:
        """Publish Telegram-friendly progress updates without exposing raw reasoning."""
        if self._current_channel != "telegram" or not self._current_chat_id or not text.strip():
            return
        from clawlet.bus.queue import OutboundMessage

        try:
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=self._current_channel,
                    chat_id=self._current_chat_id,
                    content=text.strip(),
                    metadata={
                        "progress": True,
                        "progress_event": event_type,
                        "progress_detail": detail.strip(),
                        "telegram_stream_key": self._current_run_id or self._session_id or "stream",
                        "telegram_finalize_stream": final,
                        "source": self._current_source,
                    },
                )
            )
        except Exception as e:
            logger.debug(f"Could not publish progress update {event_type}: {e}")

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
            self._emit_runtime_event(
                EVENT_STORAGE_FAILED,
                session_id=session_id,
                payload={
                    "role": role,
                    "backend": type(self.storage).__name__,
                    "error": str(e),
                },
            )
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
    
    async def _call_provider_with_retry(self, messages: list[dict], enable_tools: bool = True) -> LLMResponse:
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
                request_kwargs: dict[str, object] = {}
                if enable_tools:
                    request_kwargs["tools"] = self.tools.to_openai_tools()
                    request_kwargs["tool_choice"] = "auto"
                response = await self.provider.complete(
                    messages=messages,
                    model=self.model,
                    temperature=0.7,
                    **request_kwargs,
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
                failure = classify_exception(e)
                self._consecutive_errors += 1
                logger.warning(
                    f"Provider call failed (attempt {attempt}/{max_retries}, code={failure.code}): {e}"
                )
                self._emit_runtime_event(
                    EVENT_PROVIDER_FAILED,
                    session_id=self._session_id or "session",
                    payload={
                        "provider": self.provider.name,
                        "attempt": attempt,
                        "error": str(e),
                        **failure_payload(failure),
                    },
                )
                self._save_checkpoint(
                    stage="provider_retry",
                    notes=f"attempt={attempt} code={failure.code} retryable={failure.retryable}",
                )
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

    def _format_user_facing_error(self, exc: Exception) -> str:
        """Map internal exceptions to concise, actionable user-facing messages."""
        failure = classify_exception(exc)
        if failure.code in {"provider_rate_limited", "rate_limited"}:
            return (
                "The upstream model is temporarily rate-limited (HTTP 429). "
                f"Provider: {self.provider.name}, model: {self.model}. "
                "Please retry in a minute or switch to another model."
            )
        if failure.code in {
            "provider_timeout",
            "provider_connect_error",
            "provider_read_error",
            "provider_request_error",
        }:
            return (
                "I could not reach the model provider due to a transient network/provider issue. "
                "Please try again shortly."
            )
        if failure.code in {"provider_client_error", "provider_http_error"}:
            return (
                "The model provider rejected the request. "
                "Please check provider/model configuration and try again."
            )
        return f"Sorry, I encountered an error: {str(exc)}"

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
        metadata = msg.metadata or {}
        source = str(metadata.get("source", "") or "")
        is_heartbeat = bool(metadata.get("heartbeat")) or source == "heartbeat"
        heartbeat_ack_max_chars = int(metadata.get("ack_max_chars", 24) or 24)
        scheduled_payload = self._scheduled_payload_from_metadata(metadata, source, is_heartbeat)
        is_internal_autonomous = bool(metadata.get("internal_autonomous_followup"))
        autonomous_depth = int(metadata.get("autonomous_followup_depth", 0))
        convo = await self._get_conversation_state(channel, chat_id)
        convo_key = f"{channel}:{chat_id}"
        self._session_id = convo.session_id
        self._history = convo.history
        self._current_channel = channel
        self._current_chat_id = chat_id
        self._current_user_id = str(msg.user_id or "")
        self._current_user_name = str(msg.user_name or "")
        self._current_source = source
        self._last_route = {
            "channel": channel,
            "chat_id": chat_id,
            "user_id": self._current_user_id,
            "user_name": self._current_user_name,
        }
        self._current_run_id = self._next_run_id(convo.session_id)
        self._save_checkpoint(stage="run_started", iteration=0, notes="Inbound message accepted")
        self._emit_runtime_event(
            EVENT_RUN_STARTED,
            session_id=convo.session_id,
            payload={
                "channel": channel,
                "chat_id": chat_id,
                "engine": self.runtime_config.engine,
                "engine_resolved": self._runtime_engine,
                "recovery_resume_from": metadata.get("recovery_run_id", ""),
                "recovery_resume": bool(metadata.get("recovery_resume")),
                "source": source,
                "heartbeat": is_heartbeat,
                "message_preview": user_message[:200],
            },
        )
        if scheduled_payload is not None:
            self._emit_runtime_event(
                EVENT_SCHEDULED_RUN_STARTED,
                session_id=convo.session_id,
                payload=scheduled_payload,
            )
        
        # Get metrics instance
        metrics = get_metrics()
        
        # Validate input size (max 10k chars)
        if len(user_message) > 10000:
            logger.warning(f"Message from {chat_id} exceeds 10k chars, truncating")
            user_message = user_message[:10000]
        
        logger.info(f"Processing message from {channel}/{chat_id}: {user_message[:50]}...")

        approval_response = await self._maybe_handle_confirmation_reply(
            convo_key=convo_key,
            session_id=convo.session_id,
            user_message=user_message,
            history=convo.history,
        )
        if approval_response is not None:
            from clawlet.bus.queue import OutboundMessage
            self._emit_runtime_event(
                EVENT_RUN_COMPLETED,
                session_id=convo.session_id,
                payload={"iterations": 0, "is_error": False, "response_preview": approval_response[:200]},
            )
            if scheduled_payload is not None:
                self._emit_runtime_event(
                    EVENT_SCHEDULED_RUN_COMPLETED,
                    session_id=convo.session_id,
                    payload={**scheduled_payload, "is_error": False, "response_preview": approval_response[:200]},
                )
            self._complete_checkpoint()
            return OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=approval_response,
                metadata=self._build_outbound_metadata(
                    source=source,
                    is_heartbeat=is_heartbeat,
                    heartbeat_ack_max_chars=heartbeat_ack_max_chars,
                    scheduled_payload=scheduled_payload,
                ),
            )
        
        # Add to history. Internal autonomous prompts are system context, not user content.
        if is_internal_autonomous:
            convo.history.append(Message(role="system", content=user_message))
        else:
            convo.history.append(Message(role="user", content=user_message))
            self._queue_persist(convo.session_id, "user", user_message)

        direct_install_response = await self._maybe_handle_direct_skill_install(user_message, convo.history)
        if direct_install_response is not None:
            convo.history.append(Message(role="assistant", content=direct_install_response))
            self._queue_persist(convo.session_id, "assistant", direct_install_response)
            from clawlet.bus.queue import OutboundMessage
            self._emit_runtime_event(
                EVENT_RUN_COMPLETED,
                session_id=convo.session_id,
                payload={"iterations": 0, "is_error": False, "response_preview": direct_install_response[:200]},
            )
            if scheduled_payload is not None:
                self._emit_runtime_event(
                    EVENT_SCHEDULED_RUN_COMPLETED,
                    session_id=convo.session_id,
                    payload={**scheduled_payload, "is_error": False, "response_preview": direct_install_response[:200]},
                )
            self._complete_checkpoint()
            return OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=direct_install_response,
                metadata=self._build_outbound_metadata(
                    source=source,
                    is_heartbeat=is_heartbeat,
                    heartbeat_ack_max_chars=heartbeat_ack_max_chars,
                    scheduled_payload=scheduled_payload,
                ),
            )
        
        # Trim history periodically
        self._trim_history(convo.history)
        
        # Iterative tool calling loop
        iteration = 0
        final_response = None
        is_error = False
        no_progress_count = 0
        last_signature: Optional[str] = None
        enable_tools = self._should_enable_tools(user_message)
        tool_gate_promoted = False
        action_nudge_used = False
        commitment_followthrough_used = False
        post_tool_finalization_used = False
        tool_calls_used = 0
        final_metadata_extra: dict = {}
        executed_tool_signatures: set[str] = set()
        explicit_urls = self._extract_explicit_urls(user_message)
        explicit_github_url = self._extract_github_url(user_message)
        install_skill_intent = self._is_skill_install_intent(user_message)
        action_intent = self._is_action_intent(user_message)

        await self._publish_progress_update("started", "Starting work on your request.")
        
        while iteration < self.max_iterations:
            iteration += 1
            self._save_checkpoint(stage="iteration", iteration=iteration, notes="Starting model iteration")
            
            # Build messages for LLM
            messages = self._build_messages(convo.history, query_hint=user_message)
            
            try:
                # Call LLM provider with retry and circuit breaker
                await self._publish_progress_update("provider_started", "Thinking about the next step.")
                response: LLMResponse = await self._call_provider_with_retry(messages, enable_tools=enable_tools)
                self._save_checkpoint(stage="provider_response", iteration=iteration, notes="Model response received")
                
                response_content = response.content
                
                # Prefer provider-native tool calls; fallback to text parser.
                tool_calls = self._extract_provider_tool_calls(response)
                if not tool_calls:
                    tool_calls = self._extract_tool_calls(response_content)
                tool_calls = self._dedupe_tool_calls(tool_calls)
                if (
                    not tool_calls
                    and install_skill_intent
                    and explicit_github_url
                    and tool_calls_used == 0
                    and self.tools.get("install_skill") is not None
                ):
                    forced = ToolCall(
                        id="forced_install_skill_missing_tool_call",
                        name="install_skill",
                        arguments={"github_url": explicit_github_url},
                    )
                    logger.info(
                        "Applying install-first policy: model returned no tool call, "
                        f"forcing install_skill for {explicit_github_url}"
                    )
                    tool_calls = [forced]
                if (
                    not tool_calls
                    and explicit_urls
                    and tool_calls_used == 0
                    and self.tools.get("fetch_url") is not None
                ):
                    forced = ToolCall(
                        id="forced_fetch_url_missing_tool_call",
                        name="fetch_url",
                        arguments={"url": explicit_urls[0]},
                    )
                    logger.info(
                        "Applying URL-first policy: model returned no tool call, "
                        f"forcing fetch_url for {explicit_urls[0]}"
                    )
                    tool_calls = [forced]
                tool_calls = self._prioritize_explicit_url_fetch(
                    tool_calls=tool_calls,
                    explicit_urls=explicit_urls,
                    tool_calls_used=tool_calls_used,
                )
                repeated_tool_calls: list[ToolCall] = []
                novel_tool_calls: list[ToolCall] = []
                for tc in tool_calls:
                    signature = self._tool_call_signature(tc)
                    if signature in executed_tool_signatures:
                        repeated_tool_calls.append(tc)
                        continue
                    novel_tool_calls.append(tc)
                if repeated_tool_calls:
                    logger.warning(
                        "Skipping repeated tool call(s) in same turn: "
                        f"{[t.name for t in repeated_tool_calls]}"
                    )
                    if not novel_tool_calls:
                        convo.history.append(
                            Message(
                                role="system",
                                content=(
                                    "You already executed that exact tool call in this turn. "
                                    "Reuse previous tool outputs from conversation history and do not repeat identical calls."
                                ),
                            )
                        )
                        continue
                tool_calls = novel_tool_calls

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

                if no_progress_count >= self.NO_PROGRESS_LIMIT and not tool_calls:
                    logger.warning("Stopping loop due to repeated no-progress model responses")
                    final_response = "I am stuck repeating the same step. Please refine your request."
                    is_error = True
                    break
                
                if tool_calls:
                    tool_names = ", ".join(tc.name for tc in tool_calls[:4])
                    if len(tool_calls) > 4:
                        tool_names += ", ..."
                    await self._publish_progress_update(
                        "tool_requested",
                        f"Preparing {len(tool_calls)} tool call(s).",
                        detail=tool_names,
                    )
                    if not enable_tools:
                        if (
                            not tool_gate_promoted
                            and self._should_promote_tools_for_parsed_calls(user_message, tool_calls)
                        ):
                            logger.info(
                                "Parsed tool calls while tools were disabled; "
                                "promoting this request to tools-enabled and retrying"
                            )
                            tool_gate_promoted = True
                            enable_tools = True
                            continue
                        logger.warning("Ignoring tool calls because tools are disabled for this request")
                        cleaned = self._strip_tool_call_markup(response_content)
                        if not cleaned and "<tool_call" in (response_content or "").lower():
                            cleaned = (
                                "I detected an action-style tool call but tools are disabled for this turn. "
                                "Please ask with an explicit action request."
                            )
                        if cleaned and cleaned != response_content:
                            convo.history.append(Message(role="assistant", content=cleaned))
                            self._queue_persist(convo.session_id, "assistant", cleaned)
                            final_response = cleaned
                            break
                        tool_calls = []

                if tool_calls:
                    if tool_calls_used + len(tool_calls) > self.max_tool_calls_per_message:
                        logger.warning(
                            "Stopping loop due to tool-call budget exceeded: "
                            f"{tool_calls_used + len(tool_calls)} > {self.max_tool_calls_per_message}"
                        )
                        final_response = (
                            "I stopped to avoid excessive tool calls. "
                            "Please narrow the request and I will run only the minimum needed actions."
                        )
                        is_error = True
                        break

                    tool_calls_used += len(tool_calls)
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

                    mapped_calls: list[ToolCall] = []
                    for tc in tool_calls:
                        requested_tool_name = tc.name
                        mapped_tool_name = self._tool_aliases.get(requested_tool_name, requested_tool_name)
                        if mapped_tool_name != requested_tool_name:
                            logger.info(f"Mapping tool alias '{requested_tool_name}' -> '{mapped_tool_name}'")
                        tc.name = mapped_tool_name
                        mapped_calls.append(tc)
                    for tc in mapped_calls:
                        executed_tool_signatures.add(self._tool_call_signature(tc))

                    # Confirmation checks remain serial and explicit before any execution.
                    for tc in mapped_calls:
                        confirm_reason = self._requires_confirmation(tc)
                        if confirm_reason:
                            token = str(int(time.time()))[-6:]
                            self._pending_confirmations[convo_key] = {
                                "token": token,
                                "tool_call": tc,
                            }
                            final_response = (
                                f"{confirm_reason}: `{tc.name}`.\n"
                                f"Reply with `confirm {token}` to continue or `cancel`."
                            )
                            final_metadata_extra = self._build_confirmation_outbound_metadata(
                                token=token,
                                tool_call=tc,
                                reason=confirm_reason,
                            )
                            is_error = False
                            break

                    if final_response is not None:
                        break

                    executed = await self._execute_tool_calls_optimized(mapped_calls)

                    for tc, result in executed:
                        rendered_tool_output = self._render_tool_result(result)
                        self._save_checkpoint(
                            stage="tool_executed",
                            iteration=iteration,
                            notes=f"tool={tc.name} success={result.success}",
                        )
                        convo.history.append(
                            Message(
                                role="tool",
                                content=rendered_tool_output,
                                metadata={"tool_call_id": tc.id, "tool_name": tc.name},
                            )
                        )
                        self._queue_persist(convo.session_id, "tool", rendered_tool_output)
                    
                    if final_response is not None:
                        break

                    # Continue loop to get next response
                    continue
                
                # If this looks actionable but the model skipped tools, nudge once and retry.
                if enable_tools and action_intent and tool_calls_used == 0 and not action_nudge_used:
                    logger.info("Action intent detected with no tool calls; nudging model to use tools")
                    action_nudge_used = True
                    convo.history.append(
                        Message(
                            role="system",
                            content=(
                                "This request is actionable. Use available tools when needed, "
                                "then provide the final answer. Do not output tool-call markup."
                            ),
                        )
                    )
                    continue

                if (
                    not tool_calls
                    and enable_tools
                    and self._looks_like_incomplete_followthrough(response_content, tool_calls_used)
                ):
                    if not commitment_followthrough_used:
                        logger.info(
                            "Model returned mid-task narration without action; forcing same-turn follow-through"
                        )
                        commitment_followthrough_used = True
                        convo.history.append(
                            Message(
                                role="system",
                                content=self.COMMITMENT_FOLLOWTHROUGH_NUDGE,
                            )
                        )
                        continue

                    if is_internal_autonomous:
                        logger.warning(
                            "Internal autonomous follow-up still returned mid-task narration after forced follow-through"
                        )
                        final_response = (
                            "I could not complete the promised action automatically because no executable step was taken. "
                            "Please retry the request or ask me to perform one concrete action."
                        )
                        is_error = True
                        break

                    logger.warning(
                        "Model still returned mid-task narration after forced follow-through; refusing to send partial status"
                    )
                    final_response = (
                        "I did not execute the promised action. Please retry with one concrete action, "
                        "or I can try again with a more specific next step."
                    )
                    is_error = True
                    break

                if (
                    not tool_calls
                    and enable_tools
                    and tool_calls_used > 0
                    and not post_tool_finalization_used
                    and not self._looks_like_blocker_response(response_content)
                ):
                    logger.info(
                        "Suppressing post-tool intermediate narration; forcing one finalization pass"
                    )
                    await self._publish_progress_update("finalizing", "Finalizing the response.")
                    post_tool_finalization_used = True
                    convo.history.append(
                        Message(
                            role="system",
                            content=self.POST_TOOL_FINALIZATION_NUDGE,
                        )
                    )
                    continue

                if (
                    is_internal_autonomous
                    and enable_tools
                    and not tool_calls
                    and self.AUTONOMOUS_COMMITMENT_PATTERN.search(response_content or "")
                ):
                    if not action_nudge_used:
                        logger.info(
                            "Internal autonomous follow-up returned another commitment without tool calls; "
                            "nudging model to execute now or report blocker"
                        )
                        action_nudge_used = True
                        convo.history.append(
                            Message(
                                role="system",
                                content=self.AUTONOMOUS_EXECUTION_NUDGE,
                            )
                        )
                        continue

                    logger.warning(
                        "Internal autonomous follow-up still returned a commitment with no tool calls after nudge"
                    )
                    final_response = (
                        "I could not complete the promised action automatically because no executable step was taken. "
                        "Please retry the request or ask me to perform one concrete action."
                    )
                    is_error = True
                    break

                # No tool calls - this is the final response
                final_text = self._sanitize_final_response(response_content, tool_calls_used)
                convo.history.append(Message(role="assistant", content=final_text or response_content))
                self._queue_persist(convo.session_id, "assistant", final_text or response_content)
                final_response = final_text or response_content
                break
                
            except Exception as e:
                logger.error(f"Error in agent loop iteration {iteration}: {e}")
                self._save_checkpoint(stage="error", iteration=iteration, notes=str(e))
                final_response = self._format_user_facing_error(e)
                is_error = True
                break
        
        if final_response is None:
            if tool_calls_used > 0:
                logger.info("Iteration cap reached after tool use; attempting one finalization-only pass")
                try:
                    await self._publish_progress_update("finalizing", "Summarizing completed work and any blockers.")
                    convo.history.append(
                        Message(
                            role="system",
                            content=(
                                "This is the final response pass for this turn. "
                                "Do not call more tools. Summarize what was completed and any concrete blocker that remains."
                            ),
                        )
                    )
                    messages = self._build_messages(convo.history, query_hint=user_message)
                    response = await self._call_provider_with_retry(messages, enable_tools=False)
                    response_content = self._sanitize_final_response(response.content or "", tool_calls_used).strip()
                    if response_content:
                        convo.history.append(Message(role="assistant", content=response_content))
                        self._queue_persist(convo.session_id, "assistant", response_content)
                        final_response = response_content
                        is_error = self._looks_like_blocker_response(response_content)
                except Exception as e:
                    logger.error(f"Error in finalization-only pass: {e}")

            if final_response is None:
                final_response = "I reached my maximum number of iterations. Please try again."
                is_error = True

        if self._should_schedule_autonomous_followup(
            assistant_response=final_response,
            tool_calls_used=tool_calls_used,
            is_error=is_error,
            is_internal_autonomous=is_internal_autonomous,
            autonomous_depth=autonomous_depth,
        ):
            followup_prompt = (
                "Autonomous follow-up: execute the action you already committed to in the last reply. "
                "Use tools immediately when needed. Do not re-list options. "
                f"Original user request: {user_message}\n"
                f"Your previous reply: {final_response}"
            )
            await self.bus.publish_inbound(
                type(msg)(
                    channel=channel,
                    chat_id=chat_id,
                    content=followup_prompt,
                    user_id=msg.user_id,
                    user_name=msg.user_name,
                    metadata={
                        "internal_autonomous_followup": True,
                        "autonomous_followup_depth": autonomous_depth + 1,
                    },
                )
            )
            logger.info(
                f"Queued autonomous follow-up for {channel}/{chat_id} "
                f"(depth={autonomous_depth + 1})"
            )

        logger.info(f"Final response: {len(final_response)} chars (iterations: {iteration})")
        
        # Update metrics
        if is_error:
            metrics.inc_errors()
        else:
            metrics.inc_messages()
        
        from clawlet.bus.queue import OutboundMessage
        self._emit_runtime_event(
            EVENT_RUN_COMPLETED,
            session_id=convo.session_id,
            payload={
                "iterations": iteration,
                "is_error": is_error,
                "tool_stats": dict(self._tool_stats),
                "response_preview": final_response[:200],
            },
        )
        if scheduled_payload is not None:
            self._emit_runtime_event(
                EVENT_SCHEDULED_RUN_FAILED if is_error else EVENT_SCHEDULED_RUN_COMPLETED,
                session_id=convo.session_id,
                payload={
                    **scheduled_payload,
                    "iterations": iteration,
                    "is_error": is_error,
                    "response_preview": final_response[:200],
                },
            )
        if is_error:
            self._save_checkpoint(stage="interrupted", iteration=iteration, notes=final_response[:400])
        else:
            self._complete_checkpoint()
        return OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=final_response,
            metadata=self._build_outbound_metadata(
                source=source,
                is_heartbeat=is_heartbeat,
                heartbeat_ack_max_chars=heartbeat_ack_max_chars,
                scheduled_payload=scheduled_payload,
                extra=final_metadata_extra,
            ),
        )

    def _scheduled_payload_from_metadata(
        self,
        metadata: dict,
        source: str,
        is_heartbeat: bool,
    ) -> Optional[dict[str, str]]:
        """Build scheduled-run payload from inbound metadata when applicable."""
        if source not in {"heartbeat", "scheduler"} and not is_heartbeat:
            return None

        payload = {
            SCHED_PAYLOAD_JOB_ID: str(metadata.get(SCHED_PAYLOAD_JOB_ID) or ("heartbeat" if is_heartbeat else "scheduler")),
            SCHED_PAYLOAD_RUN_ID: str(metadata.get(SCHED_PAYLOAD_RUN_ID) or f"sched-{uuid4().hex[:12]}"),
            SCHED_PAYLOAD_SOURCE: str(metadata.get(SCHED_PAYLOAD_SOURCE) or source or "scheduler"),
            SCHED_PAYLOAD_SESSION_TARGET: str(metadata.get(SCHED_PAYLOAD_SESSION_TARGET) or "main"),
            SCHED_PAYLOAD_WAKE_MODE: str(metadata.get(SCHED_PAYLOAD_WAKE_MODE) or ("next_heartbeat" if is_heartbeat else "now")),
        }
        return payload

    async def _maybe_handle_direct_skill_install(
        self,
        user_message: str,
        history: list[Message],
    ) -> Optional[str]:
        """Handle explicit skill-install requests without re-entering discovery loops."""
        lowered = user_message.strip().lower()
        if not lowered:
            return None

        if not any(keyword in lowered for keyword in self.INSTALL_KEYWORDS):
            return None
        if "skill" not in lowered and "clawhub" not in lowered:
            return None

        direct_github_url = self._extract_github_url(user_message)
        if direct_github_url and self.tools.get("install_skill"):
            tc = ToolCall(
                id="direct_install_skill_url",
                name="install_skill",
                arguments={"github_url": direct_github_url},
            )
            result = await self._execute_tool(tc)
            if result.success:
                return result.output
            return f"Install failed: {result.error or result.output}"
        # Let the normal reasoning/tool loop handle ambiguous install requests.
        return None

    def _extract_skill_target(self, user_message: str) -> Optional[str]:
        """Extract a likely skill target from natural language install requests."""
        text = user_message.strip()
        if not text:
            return None

        # Examples:
        # "install skilltree", "ok install SkillTree", "please add clawai-town skill"
        # "installe ce skill ...", "installer skilltree", "ajoute ce skill ..."
        m = re.search(r"(?:install|installer|installe|add|ajoute|setup|set up)\s+(.+)", text, re.IGNORECASE)
        if not m:
            return None

        candidate = m.group(1).strip().strip("`'\".,!?")
        candidate = re.sub(
            r"\b(skill|please|now|for me|ce|cette|le|la|les|moi)\b",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip()
        candidate = re.sub(r"https://github\.com/[^\s)]+", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"\s+", " ", candidate).strip(" -")
        return candidate or None

    def _extract_github_url(self, text: str) -> Optional[str]:
        """Extract first GitHub repo URL from a text snippet."""
        if not text:
            return None
        m = re.search(r"https://github\.com/[^\s)]+", text, re.IGNORECASE)
        if not m:
            return None
        return m.group(0).rstrip(".,)")

    def _is_skill_install_intent(self, text: str) -> bool:
        """Detect install intent for skills in both EN/FR phrasing."""
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        has_install = any(word in lowered for word in ("install", "installer", "installe", "add", "ajoute", "setup", "set up"))
        has_skill_context = any(word in lowered for word in ("skill", "github", "clawhub"))
        return has_install and has_skill_context

    def _find_github_url_for_target(self, target: str, history: list[Message]) -> Optional[str]:
        """Find a GitHub URL in recent conversation matching the requested target."""
        target_tokens = set(self._slugify(target).split("-"))
        for msg in reversed(history[-30:]):
            urls = re.findall(r"https://github\.com/[^\s)]+", msg.content or "")
            for url in urls:
                cleaned = url.rstrip(".,)")
                slug = cleaned.rstrip("/").split("/")[-1].replace(".git", "")
                slug_tokens = set(self._slugify(slug).split("-"))
                if target_tokens and (target_tokens <= slug_tokens or slug_tokens <= target_tokens):
                    return cleaned
        return None

    def _find_clawhub_slug_for_target(self, target: str, history: list[Message]) -> Optional[str]:
        """Find a previously suggested `clawhub install <slug>` command for the target."""
        target_slug = self._slugify(target)
        target_tokens = set(target_slug.split("-"))
        for msg in reversed(history[-30:]):
            installs = re.findall(r"clawhub\s+install\s+([a-zA-Z0-9._-]+)", msg.content or "", re.IGNORECASE)
            for candidate in installs:
                slug = self._slugify(candidate)
                slug_tokens = set(slug.split("-"))
                if target_tokens and (target_tokens <= slug_tokens or slug_tokens <= target_tokens):
                    return slug
        return None

    def _slugify(self, value: str) -> str:
        """Normalize potential skill names into a safe slug."""
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return slug

    def _should_enable_tools(self, user_message: str) -> bool:
        """Enable tools for most requests; disable only trivial chat/acks."""
        text = user_message.strip()
        if not text:
            return False

        lowered = text.lower()
        normalized = lowered.rstrip("!?. ").strip()
        if self._is_trivial_chat_message(lowered):
            return False
        if normalized and self._is_trivial_chat_message(normalized):
            return False

        if self._is_ack_message(lowered):
            return False
        if normalized and self._is_ack_message(normalized):
            return False

        return True

    def _is_trivial_chat_message(self, lowered_text: str) -> bool:
        """True for short, non-actionable conversational turns."""
        return lowered_text in {
            "hi",
            "hello",
            "hey",
            "thanks",
            "thank you",
            "ok",
            "okay",
            "yes",
            "no",
            "how are you",
            "how are you?",
        }

    def _is_ack_message(self, lowered_text: str) -> bool:
        """True for acknowledgements that should not trigger tools."""
        return lowered_text in {
            "merci",
            "thanks",
            "thank you",
            "ok merci",
            "ok thanks",
            "super",
            "parfait",
            "top",
        }

    def _is_action_intent(self, text: str) -> bool:
        """Broad detector for requests that likely require taking actions."""
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        if self._is_trivial_chat_message(lowered) or self._is_ack_message(lowered):
            return False
        for pattern in self.TOOL_INTENT_PATTERNS:
            if re.search(pattern, lowered, re.IGNORECASE):
                return True
        return bool(self.URL_PATTERN.search(lowered))

    def _should_promote_tools_for_parsed_calls(
        self,
        user_message: str,
        tool_calls: list[ToolCall],
    ) -> bool:
        """Decide whether to re-run with tools enabled after parser detected tool calls."""
        if not tool_calls:
            return False

        lowered = (user_message or "").strip().lower()
        if not lowered or self._is_trivial_chat_message(lowered):
            return False

        # Only promote when parsed calls are to known tools (or aliases).
        for tc in tool_calls:
            mapped = self._tool_aliases.get(tc.name, tc.name)
            if self.tools.get(mapped) is None:
                return False

        # Require at least one action cue in the user's message.
        action_cues = (
            "list", "liste", "show", "read", "lire", "open", "find", "trouve",
            "search", "recherche", "look up", "run", "execute", "exécuter",
            "workspace", "espace de travail", "file", "folder", "dossier", "directory",
            "web", "contenu", "content",
            "url", "http://", "https://", "install", "create", "edit", "write",
        )
        return any(cue in lowered for cue in action_cues)

    def _dedupe_tool_calls(self, tool_calls: list[ToolCall]) -> list[ToolCall]:
        """Remove duplicate tool calls while preserving original order."""
        out: list[ToolCall] = []
        seen: set[str] = set()
        for tc in tool_calls:
            try:
                key = f"{tc.name}:{json.dumps(tc.arguments or {}, sort_keys=True, default=str)}"
            except Exception:
                key = f"{tc.name}:{str(tc.arguments)}"
            if key in seen:
                continue
            seen.add(key)
            out.append(tc)
        return out

    def _strip_tool_call_markup(self, content: str) -> str:
        """Remove tool-call markup blocks from plain text model responses."""
        text = content or ""
        text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text

    def _sanitize_final_response(self, content: str, tool_calls_used: int) -> str:
        """Sanitize final user-facing text when no further tool execution should happen."""
        cleaned = self._strip_tool_call_markup(content or "")
        if not cleaned:
            return ""

        has_pending_language = bool(self.FINAL_RESPONSE_CONTINUATION_SPLIT.search(cleaned))
        if has_pending_language or self._looks_like_incomplete_followthrough(cleaned, tool_calls_used):
            head = self.FINAL_RESPONSE_CONTINUATION_SPLIT.split(cleaned, maxsplit=1)[0].strip()
            if head:
                return (
                    "Partial progress:\n\n"
                    f"{head}\n\n"
                    "I did not execute the remaining step in this turn."
                )
            return "I made partial progress, but I did not execute the remaining step in this turn."

        return cleaned

    def _extract_explicit_urls(self, user_message: str) -> list[str]:
        """Extract normalized explicit URLs from user message."""
        urls: list[str] = []
        seen: set[str] = set()
        for raw in self.URL_PATTERN.findall(user_message or ""):
            candidate = raw.rstrip(".,);!?'\"")
            if not candidate:
                continue
            lowered = candidate.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            urls.append(candidate)
        return urls

    def _prioritize_explicit_url_fetch(
        self,
        tool_calls: list[ToolCall],
        explicit_urls: list[str],
        tool_calls_used: int,
    ) -> list[ToolCall]:
        """Force URL fetch first for explicit-link requests on the first tool step."""
        if not tool_calls or not explicit_urls or tool_calls_used > 0:
            return tool_calls
        if self.tools.get("fetch_url") is None:
            return tool_calls

        wanted = {u.lower() for u in explicit_urls}
        for tc in tool_calls:
            mapped_name = self._tool_aliases.get(tc.name, tc.name)
            if mapped_name != "fetch_url":
                continue
            arg_url = str((tc.arguments or {}).get("url", "")).strip().lower()
            if arg_url and arg_url in wanted:
                return tool_calls

        forced = ToolCall(
            id="forced_fetch_url_first",
            name="fetch_url",
            arguments={"url": explicit_urls[0]},
        )
        logger.info(
            f"Applying URL-first policy: forcing fetch_url for explicit URL {explicit_urls[0]}"
        )
        return [forced]

    def _should_schedule_autonomous_followup(
        self,
        assistant_response: str,
        tool_calls_used: int,
        is_error: bool,
        is_internal_autonomous: bool,
        autonomous_depth: int,
    ) -> bool:
        """Schedule a self-follow-up turn if the model promised action but did none."""
        if is_error:
            return False
        if is_internal_autonomous:
            return False
        if autonomous_depth >= self.MAX_AUTONOMOUS_FOLLOWUP_DEPTH:
            return False
        if tool_calls_used > 0:
            return False

        text = (assistant_response or "").strip()
        if not text:
            return False

        # If model is asking for input/confirmation, do not force autonomous continuation.
        if "?" in text or self.AUTONOMOUS_BLOCKING_PATTERN.search(text):
            return False

        return bool(self.AUTONOMOUS_COMMITMENT_PATTERN.search(text))

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
        """Render tool output for conversation history."""
        raw = result.output if result.success else f"Error: {result.error}"
        return raw

    def _tool_call_signature(self, tool_call: ToolCall) -> str:
        """Stable signature for duplicate-call suppression within a single turn."""
        try:
            args = json.dumps(tool_call.arguments or {}, sort_keys=True, default=str)
        except Exception:
            args = str(tool_call.arguments)
        return f"{tool_call.name}:{args}"

    def _looks_like_incomplete_followthrough(self, text: str, tool_calls_used: int) -> bool:
        """Detect mid-task narration that should stay inside the current turn."""
        text = (text or "").strip()
        if not text:
            return False
        if "?" in text or self.AUTONOMOUS_BLOCKING_PATTERN.search(text):
            return False
        if self.AUTONOMOUS_COMMITMENT_PATTERN.search(text):
            return True
        if tool_calls_used <= 0:
            return False
        return bool(self.CONTINUATION_PATTERN.search(text))

    def _looks_like_blocker_response(self, text: str) -> bool:
        """Heuristic for responses that are acceptable stop points after tools."""
        text = (text or "").strip()
        if not text:
            return False
        if "?" in text:
            return True
        if self.AUTONOMOUS_BLOCKING_PATTERN.search(text):
            return True
        lowered = text.lower()
        blocker_markers = (
            "could not",
            "can't",
            "cannot",
            "unable",
            "failed",
            "error",
            "blocked",
            "requires",
            "need your",
            "manual step",
            "manual action",
            "claim step",
            "verification",
        )
        return any(marker in lowered for marker in blocker_markers)
    
    def _extract_tool_calls(self, content: str) -> list[ToolCall]:
        """Extract tool calls from LLM response content."""
        # Fast path: raw JSON tool payloads.
        stripped = (content or "").strip()
        if stripped and (stripped.startswith("{") or stripped.startswith("[")):
            try:
                raw = json.loads(stripped)
                if isinstance(raw, dict) and "name" in raw:
                    args = raw.get("arguments", raw.get("parameters", {}))
                    if not isinstance(args, dict):
                        args = {"value": args}
                    return [ToolCall(id="call_raw_json_0", name=raw["name"], arguments=args)]
                if isinstance(raw, list):
                    out: list[ToolCall] = []
                    for i, item in enumerate(raw):
                        if not isinstance(item, dict) or "name" not in item:
                            continue
                        args = item.get("arguments", item.get("parameters", {}))
                        if not isinstance(args, dict):
                            args = {"value": args}
                        out.append(ToolCall(id=f"call_raw_json_{i}", name=item["name"], arguments=args))
                    if out:
                        return out
            except json.JSONDecodeError:
                pass

        from clawlet.agent.tool_parser import ToolCallParser

        parsed = ToolCallParser().parse(content or "")
        if parsed:
            return [ToolCall(id=p.id, name=p.name, arguments=p.arguments) for p in parsed]
        return []
    
    async def _execute_tool(self, tool_call: ToolCall, approved: bool = False) -> ToolResult:
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
                await self._publish_progress_update(
                    "tool_failed",
                    f"Skipped `{tool_name}` because it is temporarily unavailable.",
                    detail="circuit open",
                )
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
        await self._publish_progress_update("tool_started", f"Running `{tool_name}`.", detail=tool_name)

        if self.tools.get(tool_name) is None:
            logger.warning(f"Rejected unknown tool call: {tool_name}")
            self._tool_stats["calls_rejected"] += 1
            await self._publish_progress_update("tool_failed", f"Rejected unknown tool `{tool_name}`.", detail=tool_name)
            return ToolResult(success=False, output="", error=f"Unknown tool: {tool_name}")

        # Validate tool invocation before execution.
        tool = self.tools.get(tool_name)
        schema = tool.parameters_schema if tool else None
        raw_args = dict(tool_call.arguments or {})
        execution_target_raw = str(raw_args.pop("_execution_target", "local")).strip().lower()
        execution_target = "remote" if execution_target_raw == "remote" else "local"
        lane = str(raw_args.pop("_lane", "")).strip().lower()

        valid, error_msg, sanitized = validate_tool_params(
            tool_name=tool_name,
            params=raw_args,
            schema=schema,
        )
        if not valid:
            logger.warning(f"Rejected tool call for '{tool_name}': {error_msg}")
            self._tool_stats["calls_rejected"] += 1
            await self._publish_progress_update(
                "tool_failed",
                f"Rejected invalid call for `{tool_name}`.",
                detail=error_msg,
            )
            return ToolResult(success=False, output="", error=f"Invalid tool call: {error_msg}")
        args = dict(sanitized.get("params", raw_args))
        if execution_target == "remote" and getattr(self._tool_runtime, "remote_executor", None) is None:
            logger.warning("Remote execution requested but remote executor is unavailable; using local target")
            execution_target = "local"

        envelope = ToolCallEnvelope(
            run_id=self._current_run_id or self._next_run_id(self._session_id or "session"),
            session_id=self._session_id or "session",
            tool_call_id=tool_call.id,
            tool_name=tool_name,
            arguments=args,
            execution_mode=self._runtime_policy.infer_mode(tool_name, args),
            workspace_path=str(self.workspace),
            timeout_seconds=self.runtime_config.default_tool_timeout_seconds,
            max_retries=self.runtime_config.default_tool_retries,
            execution_target=execution_target,  # type: ignore[arg-type]
            lane=lane,
        )

        try:
            result, meta = await self._tool_runtime.execute(envelope, approved=approved)
            self._tool_stats["calls_executed"] += 1
            logger.debug(
                f"Tool runtime metadata: {tool_name} -> {asdict(meta)}"
            )
        except Exception as e:
            # Unexpected exception, wrap in ToolResult
            result = ToolResult(success=False, output="", error=str(e))
        
        if result.success:
            # Reset failure count on success
            if tool_name in self._tool_failures:
                self._tool_failures[tool_name] = 0
            logger.info(f"Tool {tool_name} succeeded: {result.output[:100]}...")
            await self._publish_progress_update("tool_completed", f"Completed `{tool_name}`.", detail=tool_name)
        else:
            self._tool_stats["calls_failed"] += 1
            # Increment failure count
            failures = self._tool_failures.get(tool_name, 0) + 1
            self._tool_failures[tool_name] = failures
            # Increment tool error metric
            get_metrics().inc_tool_errors()
            logger.warning(f"Tool {tool_name} failed: {result.error} (failures: {failures})")
            await self._publish_progress_update(
                "tool_failed",
                f"`{tool_name}` failed.",
                detail=result.error or result.output[:200],
            )
            
            if failures >= self._tool_failure_threshold:
                # Trip circuit breaker
                open_until = now + timedelta(seconds=self._tool_circuit_timeout_seconds)
                self._tool_circuit_open_until[tool_name] = open_until
                logger.error(f"Circuit breaker tripped for tool '{tool_name}'! Open until {open_until.isoformat()}")
        
        return result

    def _should_parallelize_tool_calls(self, tool_calls: list[ToolCall]) -> bool:
        """Allow safe parallel execution for batches of read-only local tool calls."""
        if not self._enable_parallel_read_batches:
            return False
        if len(tool_calls) < 2:
            return False
        for tc in tool_calls:
            if not self._is_parallel_tool_call(tc):
                return False
        return True

    def _is_parallel_tool_call(self, tool_call: ToolCall) -> bool:
        """True when this tool call is safe for read-only parallel execution."""
        args = dict(tool_call.arguments or {})
        if str(args.get("_execution_target", "local")).strip().lower() == "remote":
            return False
        lane = str(args.get("_lane", "")).strip().lower()
        if lane.startswith("serial:"):
            return False
        mode = self._runtime_policy.infer_mode(tool_call.name, args)
        return mode == "read_only"

    def _plan_tool_execution_groups(self, tool_calls: list[ToolCall]) -> list[tuple[str, list[ToolCall]]]:
        """Group calls into deterministic execution blocks: parallel-read-only or serial."""
        if not self._enable_parallel_read_batches:
            return [("serial", [tc]) for tc in tool_calls]
        groups: list[tuple[str, list[ToolCall]]] = []
        pending_parallel: list[ToolCall] = []

        def _flush_parallel():
            nonlocal pending_parallel
            if not pending_parallel:
                return
            if len(pending_parallel) == 1:
                groups.append(("serial", [pending_parallel[0]]))
            else:
                groups.append(("parallel", list(pending_parallel)))
            pending_parallel = []

        for tc in tool_calls:
            if self._is_parallel_tool_call(tc):
                pending_parallel.append(tc)
                continue
            _flush_parallel()
            groups.append(("serial", [tc]))

        _flush_parallel()
        return groups

    async def _execute_tool_calls_optimized(self, tool_calls: list[ToolCall]) -> list[tuple[ToolCall, ToolResult]]:
        """Execute mixed batches with parallel read-only groups and serial fallback."""
        if not tool_calls:
            return []

        out: list[tuple[ToolCall, ToolResult]] = []
        for mode, chunk in self._plan_tool_execution_groups(tool_calls):
            if mode == "parallel":
                self._tool_stats["parallel_batches"] = int(self._tool_stats.get("parallel_batches", 0)) + 1
                self._tool_stats["parallel_batch_tools"] = int(self._tool_stats.get("parallel_batch_tools", 0)) + len(
                    chunk
                )
                out.extend(await self._execute_tool_batch_parallel(chunk))
                continue
            self._tool_stats["serial_batches"] = int(self._tool_stats.get("serial_batches", 0)) + 1
            for tc in chunk:
                out.append((tc, await self._execute_tool(tc)))
        return out

    async def _execute_tool_batch_parallel(self, tool_calls: list[ToolCall]) -> list[tuple[ToolCall, ToolResult]]:
        """Execute tool calls concurrently and preserve call order for history determinism."""
        limit = max(1, min(self._max_parallel_read_tools, len(tool_calls)))
        semaphore = asyncio.Semaphore(limit)

        async def _run(tc: ToolCall) -> ToolResult:
            async with semaphore:
                try:
                    return await self._execute_tool(tc)
                except Exception as e:
                    return ToolResult(success=False, output="", error=str(e))

        logger.info(
            f"Executing {len(tool_calls)} read-only tool calls in parallel batch "
            f"(max_parallel={limit})"
        )
        results = await asyncio.gather(*[_run(tc) for tc in tool_calls])
        return list(zip(tool_calls, results))
    
    def _build_messages(self, history: list[Message], query_hint: Optional[str] = None) -> list[dict]:
        """Build messages list for LLM."""
        messages = []
        
        # System prompt from identity (include tools)
        tools_list = self.tools.all_tools() if self.tools else None
        system_prompt = self.identity.build_system_prompt(
            tools=tools_list,
            workspace_path=str(self.workspace)
        )
        messages.append({"role": "system", "content": system_prompt})

        query_text = (query_hint or "").strip()
        if not query_text:
            for msg in reversed(history):
                if msg.role == "user" and msg.content:
                    query_text = msg.content
                    break
        if query_text:
            try:
                repo_context = self._context_engine.render_for_prompt(
                    query=query_text,
                    max_files=5,
                    char_budget=3000,
                )
                if repo_context:
                    messages.append({"role": "system", "content": repo_context})
            except Exception as e:
                logger.debug(f"Context engine unavailable for this turn: {e}")

        try:
            memory_context = self.memory.get_context()
            if memory_context:
                messages.append({"role": "system", "content": memory_context})
        except Exception as e:
            logger.debug(f"Memory context unavailable for this turn: {e}")
        
        if history and history[0].role == "system" and history[0].metadata.get("summary") is True:
            messages.append(history[0].to_dict())

        # Add recent history (limited by CONTEXT_WINDOW only). Do not drop large
        # tool/document messages here; that can discard the exact instructions the
        # model needs to finish the task.
        recent = history[-self.CONTEXT_WINDOW:]
        
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
            overflow = len(history) - self.MAX_HISTORY + 1
            dropped = history[:overflow]
            summary_lines = []
            for msg in dropped:
                if msg.role in {"user", "assistant"}:
                    excerpt = (msg.content or "").strip().replace("\n", " ")
                    if excerpt:
                        summary_lines.append(f"{msg.role}: {excerpt[:180]}")
            if summary_lines:
                summary_text = "Conversation summary (compressed):\n" + "\n".join(summary_lines[-20:])
                summary_msg = Message(role="system", content=summary_text, metadata={"summary": True})
                history[:] = [summary_msg] + history[overflow:]
            else:
                del history[:-self.MAX_HISTORY]
            logger.debug(f"Trimmed history to {len(history)} messages")

    def _format_tool_call_details(self, tool_call: ToolCall) -> str:
        """Render a compact approval summary safe for user-facing channels."""
        try:
            args = json.dumps(tool_call.arguments or {}, indent=2, ensure_ascii=True, sort_keys=True)
        except Exception:
            args = str(tool_call.arguments or {})
        return f"Tool: {tool_call.name}\nArguments:\n{args}"

    def _build_confirmation_outbound_metadata(self, token: str, tool_call: ToolCall, reason: str) -> dict:
        details = self._format_tool_call_details(tool_call)
        return {
            "telegram_buttons": [
                [
                    {"text": "Approve", "callback_data": f"approval:approve:{token}"},
                    {"text": "Reject", "callback_data": f"approval:reject:{token}"},
                ],
                [
                    {"text": "Show details", "callback_data": f"approval:details:{token}"},
                ],
            ],
            "telegram_pending_approval": {
                "token": token,
                "tool_name": tool_call.name,
                "reason": reason,
                "arguments": dict(tool_call.arguments or {}),
                "details": details,
            },
        }

    async def _maybe_handle_confirmation_reply(
        self,
        convo_key: str,
        session_id: str,
        user_message: str,
        history: list[Message],
    ) -> Optional[str]:
        pending = self._pending_confirmations.get(convo_key)
        if not pending:
            return None

        text = user_message.strip().lower()
        if text in {"cancel", "cancel it", "abort"}:
            self._pending_confirmations.pop(convo_key, None)
            return "Cancelled the pending action."

        m = re.match(r"confirm\s+(\d{4,8})$", text)
        if not m:
            return None

        token = m.group(1)
        if token != pending.get("token"):
            return "Confirmation token does not match the pending action."

        tc: ToolCall = pending["tool_call"]
        result = await self._execute_tool(tc, approved=True)
        rendered = self._render_tool_result(result)
        history.append(Message(role="tool", content=rendered, metadata={"tool_name": tc.name, "tool_call_id": tc.id}))
        self._queue_persist(session_id, "tool", rendered)
        self._pending_confirmations.pop(convo_key, None)

        if result.success:
            return f"Confirmed and executed `{tc.name}`.\n\n{result.output}"
        return f"Confirmed but `{tc.name}` failed: {result.error or result.output}"

    def _is_destructive_tool_call(self, tool_call: ToolCall) -> bool:
        """Heuristic risk gate for destructive tool actions."""
        name = (tool_call.name or "").lower()
        args = tool_call.arguments or {}
        if name in {"write_file", "edit_file", "apply_patch"}:
            path = str(args.get("path", "")).lower()
            if any(path.endswith(x) for x in (".env", "config.yaml", "config.yml", "pyproject.toml")):
                return True
            return False

        if name != "shell":
            return False

        cmd = str(args.get("command", "")).strip().lower()
        if not cmd:
            return False
        destructive_patterns = (
            " rm ",
            " rm-",
            " rm\t",
            "rm -",
            "mv ",
            "chmod ",
            "chown ",
            "git reset",
            "git clean",
            "dd ",
            "mkfs",
        )
        return any(pat in f" {cmd}" for pat in destructive_patterns)

    def _requires_confirmation(self, tool_call: ToolCall) -> str:
        """Return a non-empty reason if the tool call should require explicit user confirmation."""
        mode = self._runtime_policy.infer_mode(tool_call.name, tool_call.arguments or {})
        decision = self._runtime_policy.authorize(mode, approved=False)
        if not decision.allowed and "requires explicit approval" in decision.reason.lower():
            return f"Policy requires approval for {mode} action"
        if self._is_destructive_tool_call(tool_call):
            return "Destructive action blocked by default"
        return ""

    async def _publish_outbound_with_retry(self, response: "OutboundMessage") -> bool:
        """Publish outbound messages with bounded retries and structured failure telemetry."""
        if self._should_suppress_outbound(response):
            logger.info(
                f"Suppressed low-value heartbeat outbound for {response.channel}/{response.chat_id}"
            )
            get_metrics().inc_heartbeat_acks_suppressed()
            return True

        retries = max(0, int(self.runtime_config.outbound_publish_retries))
        backoff = max(0.0, float(self.runtime_config.outbound_publish_backoff_seconds))
        attempts = retries + 1
        for attempt in range(1, attempts + 1):
            try:
                await self.bus.publish_outbound(response)
                return True
            except Exception as e:
                failure = classify_error_text(str(e))
                logger.error(
                    f"Failed to publish outbound response (attempt {attempt}/{attempts}, code={failure.code}): {e}"
                )
                self._emit_runtime_event(
                    EVENT_CHANNEL_FAILED,
                    session_id=self._session_id or "session",
                    payload={
                        "channel": getattr(response, "channel", ""),
                        "chat_id": getattr(response, "chat_id", ""),
                        "attempt": attempt,
                        "error": str(e),
                        **failure_payload(failure),
                    },
                )
                if attempt >= attempts:
                    return False
                if backoff > 0:
                    await asyncio.sleep(backoff * attempt)
        return False

    def _should_suppress_outbound(self, response: "OutboundMessage") -> bool:
        """Suppress trivial heartbeat acknowledgements."""
        metadata = getattr(response, "metadata", {}) or {}
        if not bool(metadata.get("heartbeat")):
            return False

        text = (getattr(response, "content", "") or "").strip()
        if not text:
            return True
        if text == "HEARTBEAT_OK":
            return True

        ack_max_chars = int(metadata.get("ack_max_chars", 24) or 24)
        # Short single-line heartbeat acknowledgements are low signal.
        if len(text) <= ack_max_chars and "\n" not in text:
            return True
        return False
    
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
