"""
Agent loop - the core processing engine.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import asdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING
from urllib.parse import urlparse
from uuid import uuid4
import httpx

from loguru import logger

if TYPE_CHECKING:
    from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage

from clawlet.agent.identity import Identity
from clawlet.agent.memory import MemoryManager
from clawlet.agent.approval_service import ApprovalService
from clawlet.agent.heartbeat_reporter import HeartbeatReporter
from clawlet.agent.heartbeat_turn import HeartbeatTurnHandler
from clawlet.agent.history_trimmer import HistoryTrimmer
from clawlet.agent.message_builder import MessageBuilder
from clawlet.agent.models import ConversationState, Message, ToolCall
from clawlet.agent.outbound_publisher import OutboundPublisher
from clawlet.agent.progress_events import ProgressPublishingMixin
from clawlet.agent.session_persistence import SessionPersistenceMixin
from clawlet.agent.skill_install_intent import SkillInstallIntentMixin
from clawlet.agent.tool_pipeline import ToolPipelineMixin
from clawlet.agent.turn_policy import TurnPolicyMixin
from clawlet.agent.prompts import (
    AUTONOMOUS_EXECUTION_NUDGE,
    COMMITMENT_FOLLOWTHROUGH_NUDGE,
    HEARTBEAT_ACTION_POLICY,
    POST_TOOL_FINALIZATION_NUDGE,
)
from clawlet.agent.recovery_checkpoint import RecoveryCheckpointService
from clawlet.agent.run_context import RunContext
from clawlet.agent.run_lifecycle import RunLifecycle
from clawlet.agent.run_prelude import RunPrelude
from clawlet.agent.run_orchestrator import RunOrchestrator
from clawlet.agent.response_policy import ResponsePolicy
from clawlet.agent.turn_executor import TurnExecutor
from clawlet.exceptions import CircuitBreakerOpen
from clawlet.heartbeat.state import HeartbeatStateStore
from clawlet.providers.base import BaseProvider, LLMResponse
from clawlet.tools.registry import ToolRegistry, ToolResult, validate_tool_params
from clawlet.storage.sqlite import SQLiteStorage
from clawlet.config import RuntimeSettings, StorageConfig
from clawlet.context import ContextEngine
from clawlet.workspace_layout import get_workspace_layout
from clawlet.metrics import get_metrics
from clawlet.retry import CircuitBreaker
from clawlet.utils.security import mask_secrets
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
    ToolCallEnvelope,
)
from clawlet.runtime.failures import classify_error_text, classify_exception, to_payload as failure_payload


UTC_TZ = timezone.utc


class AgentLoop(
    ProgressPublishingMixin,
    SessionPersistenceMixin,
    SkillInstallIntentMixin,
    ToolPipelineMixin,
    TurnPolicyMixin,
):
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
    HEARTBEAT_NO_PROGRESS_LIMIT = 1
    MAX_TOOL_CALLS_PER_MESSAGE = 20
    MAX_HEARTBEAT_TOOL_CALLS = 8
    MAX_HEARTBEAT_ITERATIONS = 12
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
    AUTONOMOUS_EXECUTION_NUDGE = AUTONOMOUS_EXECUTION_NUDGE
    COMMITMENT_FOLLOWTHROUGH_NUDGE = COMMITMENT_FOLLOWTHROUGH_NUDGE
    POST_TOOL_FINALIZATION_NUDGE = POST_TOOL_FINALIZATION_NUDGE
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
    PLACEHOLDER_PATTERNS = (
        r"\bYOUR_[A-Z0-9_]+\b",
        r"\bVOTRE_[A-Z0-9_]+\b",
        r"\bMOLTY_NAME\b",
        r"\bPOST_ID\b",
        r"\bCOMMENT_ID\b",
        r"\bCURSOR_FROM_PREVIOUS_RESPONSE\b",
        r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){0,4}(?:_ID|_KEY|_TOKEN|_NAME|_VALUE|_EMAIL|_URL|_HANDLE)\b",
        r"\[(?:insert|replace|set|use|enter|provide)[^\]]+\]",
        r"<[A-Z][A-Z0-9 _-]{1,48}>",
        r"<[^>]*(?:api[_\s-]*key|clé[_\s-]*api|cle[_\s-]*api|token|bearer|post[_\s-]*id|comment[_\s-]*id|molty|name|nom)[^>]*>",
    )
    HEARTBEAT_ACTION_POLICY = HEARTBEAT_ACTION_POLICY
    
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
        stream_callback: Optional[Callable[[str, int], None]] = None,
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
        # Optional live-token sink (used by the TUI). When set, provider calls
        # stream deltas instead of returning whole responses; CLI/channels leave
        # it unset and keep the exact `complete()` path. Each streaming call is
        # tagged with a monotonic sequence so consumers can drop stale deltas.
        self._stream_callback = stream_callback
        self._stream_call_seq = 0
        # Optional usage sink: receives the conversation's current context size
        # after each provider call. This is the latest call's prompt_tokens —
        # summing across calls would double-count history that prompt_tokens
        # already includes.
        self._usage_callback: Optional[Callable[[int], None]] = None
        self._context_used_tokens = 0
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
        self._approval_service = ApprovalService()
        workspace_layout = get_workspace_layout(self.workspace)
        workspace_layout.ensure_directories()
        self._heartbeat_state = HeartbeatStateStore(workspace_layout.heartbeat_state_path)
        self._current_heartbeat_metadata: dict = {}
        
        # Circuit breaker for provider failures
        self._provider_circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
        )
        
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
        self._run_tool_stats_snapshot = dict(self._tool_stats)
        
        # Persistence failure tracking
        self._persist_failures = 0
        
        # Event to signal that storage initialization is complete
        self._storage_ready = asyncio.Event()
        self._persist_tasks: set[asyncio.Task] = set()
        self._active_message_task: Optional[asyncio.Task] = None
        self._active_run_context: Optional[RunContext] = None
        self._recent_http_context: dict[str, dict] = {}
        self._current_provider_failures: list[str] = []

        # Deterministic runtime + replay infrastructure
        self.runtime_config = runtime_config or RuntimeSettings()
        self._runtime_engine = self.runtime_config.engine
        self._enable_parallel_read_batches = bool(
            getattr(self.runtime_config, "enable_parallel_read_batches", True)
        )
        self._max_parallel_read_tools = max(1, int(getattr(self.runtime_config, "max_parallel_read_tools", 4) or 4))
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
            lane_defaults=dict(self.runtime_config.policy.lanes),
        )
        self._context_engine = ContextEngine(
            workspace=self.workspace,
            cache_dir=replay_dir / "context",
            roots=workspace_layout.context_roots(),
        )
        self._recovery_manager = RecoveryManager(replay_dir / "checkpoints")
        self._run_orchestrator = RunOrchestrator(self)
        self._run_lifecycle = RunLifecycle(
            emit_runtime_event=self._emit_runtime_event,
            save_checkpoint=self._save_checkpoint,
            complete_checkpoint=self._complete_checkpoint,
            metrics_factory=get_metrics,
            event_run_started=EVENT_RUN_STARTED,
            event_run_completed=EVENT_RUN_COMPLETED,
            event_scheduled_run_started=EVENT_SCHEDULED_RUN_STARTED,
            event_scheduled_run_completed=EVENT_SCHEDULED_RUN_COMPLETED,
            event_scheduled_run_failed=EVENT_SCHEDULED_RUN_FAILED,
            sched_payload_job_id=SCHED_PAYLOAD_JOB_ID,
            sched_payload_run_id=SCHED_PAYLOAD_RUN_ID,
            sched_payload_session_target=SCHED_PAYLOAD_SESSION_TARGET,
            sched_payload_wake_mode=SCHED_PAYLOAD_WAKE_MODE,
        )
        self._run_prelude = RunPrelude(
            run_lifecycle=self._run_lifecycle,
            maybe_handle_confirmation_reply=self._maybe_handle_confirmation_reply,
            maybe_handle_direct_skill_install=self._maybe_handle_direct_skill_install,
            queue_persist=self._queue_persist,
            logger=logger,
            message_cls=Message,
        )
        self._response_policy = ResponsePolicy(
            continuation_split=self.FINAL_RESPONSE_CONTINUATION_SPLIT,
            looks_like_incomplete_followthrough=self._looks_like_incomplete_followthrough,
            sanitize_template_placeholders=self._sanitize_template_placeholders,
            looks_like_blocker_response=self._looks_like_blocker_response,
        )
        self._message_builder = MessageBuilder(
            identity=self.identity,
            tools=self.tools,
            workspace=self.workspace,
            context_engine=self._context_engine,
            memory=self.memory,
            heartbeat_state=self._heartbeat_state,
            context_window=self.CONTEXT_WINDOW,
            heartbeat_action_policy=self.HEARTBEAT_ACTION_POLICY,
            logger=logger,
        )
        self._outbound_publisher = OutboundPublisher(
            bus=self.bus,
            runtime_config=self.runtime_config,
            response_policy=self._response_policy,
            heartbeat_state=self._heartbeat_state,
            logger=logger,
            metrics_factory=get_metrics,
            classify_error_text=classify_error_text,
            failure_payload=failure_payload,
            emit_runtime_event=self._emit_runtime_event,
            event_channel_failed=EVENT_CHANNEL_FAILED,
            now_fn=lambda: datetime.now(UTC_TZ),
        )
        self._heartbeat_reporter = HeartbeatReporter(
            heartbeat_state=self._heartbeat_state,
            now_fn=lambda: datetime.now(UTC_TZ),
        )
        self._heartbeat_turn_handler = HeartbeatTurnHandler(self)
        self._history_trimmer = HistoryTrimmer(
            max_history=self.MAX_HISTORY,
            logger=logger,
        )
        self._recovery_checkpoint = RecoveryCheckpointService(
            recovery_manager=self._recovery_manager,
        )
        self._turn_executor = TurnExecutor(
            agent=self,
            heartbeat_handler=self._heartbeat_turn_handler,
        )

        logger.info(
            "AgentLoop initialized with provider=%s, model=%s, tools=%s, max_tool_calls_per_message=%s"
            % (
                provider.name,
                self.model,
                len(self.tools.all_tools()),
                self.max_tool_calls_per_message,            )
        )

    def set_stream_callback(self, callback: Optional[Callable[[str, int], None]]) -> None:
        """Attach (or detach, with None) a sink receiving streamed text deltas.

        The callback receives ``(chunk, seq)`` where ``seq`` is a monotonic
        counter incremented once per streaming provider call - callers can use
        it to ignore deltas from superseded attempts.
        """
        self._stream_callback = callback

    def set_usage_callback(self, callback: Optional[Callable[[int], None]]) -> None:
        """Attach (or detach, with None) a sink receiving context usage.

        Called with the conversation's current token size (the latest call's
        prompt_tokens) after each provider call; receives only provider-reported
        usage (never an estimate).
        """
        self._usage_callback = callback

    def _next_run_id(self, session_id: str) -> str:
        """Generate a deterministic-looking unique run identifier."""
        return f"{session_id}-{uuid4().hex[:12]}"


    def _save_checkpoint(self, stage: str, iteration: int = 0, notes: str = "") -> None:
        """Persist checkpoint for interrupted-run recovery."""
        self._recovery_checkpoint.save(
            run_id=self._current_run_id,
            session_id=self._session_id,
            channel=self._current_channel,
            chat_id=self._current_chat_id,
            stage=stage,
            iteration=iteration,
            history=self._history,
            user_id=self._current_user_id,
            user_name=self._current_user_name,
            tool_stats=self._tool_stats,
            pending_confirmation=self._approval_service.snapshot(
                f"{self._current_channel}:{self._current_chat_id}"
            ),
            notes=notes,
        )

    def _complete_checkpoint(self) -> None:
        """Mark current run as completed."""
        self._recovery_checkpoint.complete(self._current_run_id)

    def _snapshot_tool_stats(self) -> dict[str, int]:
        return {key: int(self._tool_stats.get(key, 0) or 0) for key in self._tool_stats}

    def _current_run_tool_stats(self) -> dict[str, int]:
        delta: dict[str, int] = {}
        for key, value in self._tool_stats.items():
            current = int(value or 0)
            baseline = int(self._run_tool_stats_snapshot.get(key, 0) or 0)
            delta[key] = max(0, current - baseline)
        return delta

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
        await self.memory.initialize()
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
                    self._active_message_task = asyncio.create_task(self._process_message(msg))
                    response = await self._active_message_task
                    if response:
                        logger.info(f"Sending response: {response.content[:50]}...")
                        await self._publish_outbound_with_retry(response)
                except asyncio.CancelledError:
                    logger.info("Active message processing was cancelled")
                    if self._running:
                        raise
                    break
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    from clawlet.bus.queue import OutboundMessage
                    await self._publish_outbound_with_retry(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=self._format_user_facing_error(e)
                    ))
                finally:
                    self._active_message_task = None
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in agent loop: {e}")
                await asyncio.sleep(1)
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        if self._active_message_task is not None and not self._active_message_task.done():
            self._active_message_task.cancel()
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





        finally:
            # Signal that storage initialization attempt has completed
            self._storage_ready.set()

    async def _persist_message(self, session_id: str, role: str, content: str, metadata: dict = None) -> None:
        """Persist a message to storage and long-term memory."""
        if self._is_low_value_persisted_message(role, content, metadata):
            return

        # Wait for storage to be ready (initialization attempt completed)
        if not self._storage_ready.is_set():
            await self._storage_ready.wait()
        
        # Save to storage
        try:
            if self.storage.is_initialized():
                await self.storage.store_message(
                    session_id=session_id,
                    role=role,
                    content=content,
                    metadata=metadata or {},
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
        
        if role in ("assistant", "user"):
            capture = self._memory_capture_plan(role, content, metadata or {})
            if capture is not None:
                try:
                    await self.memory.remember(
                        key=f"{role}_{session_id}_{int(datetime.now(UTC_TZ).timestamp())}",
                        value=content,
                        category=capture["category"],
                        importance=capture["importance"],
                        metadata=capture["metadata"],
                        write_daily_note=bool(capture["write_daily_note"]),
                    )
                except Exception as e:
                    logger.warning(f"Failed to save to memory: {e}")
    
    async def _call_provider_with_retry(self, messages: list[dict], enable_tools: bool = True) -> LLMResponse:
        """Call LLM provider with retry, exponential backoff, and circuit breaker."""
        if not self._provider_circuit_breaker.can_execute():
            raise CircuitBreakerOpen(
                "Provider circuit breaker is open due to repeated failures. Please retry shortly."
            )
        
        max_retries = 3
        base_delay = 2  # seconds
        start_time = time.time()
        
        for attempt in range(1, max_retries + 1):
            try:
                request_kwargs: dict[str, object] = {}
                if enable_tools:
                    request_kwargs["tools"] = self.tools.to_openai_tools()
                    request_kwargs["tool_choice"] = "auto"
                if self._stream_callback is not None:
                    # Live streaming (TUI): forward deltas as they arrive and
                    # accumulate them into the same LLMResponse shape. Tool calls
                    # are still parsed downstream from the assembled content, so
                    # provider-native tool blocks are not required.
                    self._stream_call_seq += 1
                    stream_seq = self._stream_call_seq
                    chunks: list[str] = []
                    async for chunk in self.provider.stream(
                        messages=messages,
                        model=self.model,
                        temperature=0.7,
                        **request_kwargs,
                    ):
                        if chunk:
                            chunks.append(chunk)
                            self._stream_callback(chunk, stream_seq)
                    response = LLMResponse(
                        content="".join(chunks),
                        model=self.model,
                        usage={},
                    )
                else:
                    response = await self.provider.complete(
                        messages=messages,
                        model=self.model,
                        temperature=0.7,
                        **request_kwargs,
                    )
                self._provider_circuit_breaker.record_success()
                usage = response.usage or {}
                prompt_tokens = int(usage.get("prompt_tokens") or 0)
                if prompt_tokens:
                    self._context_used_tokens = prompt_tokens
                    if self._usage_callback is not None:
                        self._usage_callback(prompt_tokens)
                elapsed = time.time() - start_time
                if elapsed > 10.0:
                    logger.warning(f"LLM call took {elapsed:.2f}s (exceeds 10s threshold)")
                else:
                    logger.debug(f"LLM call completed in {elapsed:.2f}s")
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                failure = classify_exception(e)
                self._current_provider_failures.append(failure.code)
                self._provider_circuit_breaker.record_failure()
                logger.warning(
                    f"Provider call failed (attempt {attempt}/{max_retries}, code={failure.code}): {e}"
                )
                payload = {
                    "provider": self.provider.name,
                    "attempt": attempt,
                    "error": str(e),
                    **failure_payload(failure),
                }
                if isinstance(e, httpx.HTTPStatusError):
                    payload["status_code"] = int(getattr(e.response, "status_code", 0) or 0)
                    error_body = mask_secrets(getattr(e.response, "text", "") or "") or ""
                    if error_body:
                        if len(error_body) > 2000:
                            error_body = error_body[:2000] + "... [truncated]"
                        payload["response_body"] = error_body
                self._emit_runtime_event(
                    EVENT_PROVIDER_FAILED,
                    session_id=self._session_id or "session",
                    payload=payload,
                )
                self._save_checkpoint(
                    stage="provider_retry",
                    notes=f"attempt={attempt} code={failure.code} retryable={failure.retryable}",
                )
                if attempt >= max_retries:
                    raise
                if not self._provider_circuit_breaker.can_execute():
                    raise CircuitBreakerOpen(
                        "Provider circuit breaker opened during retries due to repeated failures."
                    )
                # Exponential backoff
                delay = base_delay * (2 ** (attempt - 1))
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)
        raise RuntimeError("Unreachable: retry loop exhausted")

    def _format_user_facing_error(self, exc: Exception) -> str:
        """Map internal exceptions to concise, actionable user-facing messages."""
        if isinstance(exc, CircuitBreakerOpen):
            return (
                "The model provider is temporarily paused after repeated failures. "
                "Please retry shortly."
            )
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

    def _activate_run_context(self, run_ctx: RunContext) -> None:
        self._active_run_context = run_ctx
        self._recent_http_context = {}
        self._current_provider_failures = []
        self._session_id = run_ctx.session_id
        self._current_run_id = run_ctx.run_id
        self._current_channel = run_ctx.channel
        self._current_chat_id = run_ctx.chat_id
        self._current_user_id = run_ctx.user_id
        self._current_user_name = run_ctx.user_name
        self._current_source = run_ctx.source
        self._current_heartbeat_metadata = run_ctx.metadata if run_ctx.is_heartbeat else {}
        is_internal_scheduler_route = run_ctx.channel == "scheduler" and run_ctx.chat_id == "main"
        if not is_internal_scheduler_route:
            self._last_route = {
                "channel": run_ctx.channel,
                "chat_id": run_ctx.chat_id,
                "user_id": run_ctx.user_id,
                "user_name": run_ctx.user_name,
            }

    def _clear_run_context(self) -> None:
        self._active_run_context = None
        self._recent_http_context = {}
        self._current_provider_failures = []
        self._current_run_id = ""
        self._current_channel = ""
        self._current_chat_id = ""
        self._current_user_id = ""
        self._current_user_name = ""
        self._current_source = ""
        self._current_heartbeat_metadata = {}

    async def _process_message(self, msg: "InboundMessage") -> Optional["OutboundMessage"]:
        return await self._run_orchestrator.process_message(msg)

    async def _process_message_core(
        self,
        msg: "InboundMessage",
        convo: ConversationState,
        run_ctx: RunContext,
    ) -> Optional["OutboundMessage"]:
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
        metadata = run_ctx.metadata or {}
        source = run_ctx.source
        is_heartbeat = run_ctx.is_heartbeat
        heartbeat_ack_max_chars = int(run_ctx.mode.heartbeat_ack_max_chars if run_ctx.mode else 24)
        scheduled_payload = run_ctx.scheduled_payload
        is_internal_autonomous = bool(metadata.get("internal_autonomous_followup"))
        autonomous_depth = int(metadata.get("autonomous_followup_depth", 0))
        convo_key = f"{channel}:{chat_id}"
        self._run_tool_stats_snapshot = self._snapshot_tool_stats()
        self._history = convo.history
        prelude = await self._run_prelude.prepare(
            run_id=run_ctx.run_id,
            session_id=convo.session_id,
            channel=channel,
            chat_id=chat_id,
            metadata=metadata,
            source=source,
            is_heartbeat=is_heartbeat,
            scheduled_payload=scheduled_payload,
            heartbeat_ack_max_chars=heartbeat_ack_max_chars,
            history=convo.history,
            convo_key=convo_key,
            is_internal_autonomous=is_internal_autonomous,
            engine=self.runtime_config.engine,
            engine_resolved=self._runtime_engine,
            user_message=user_message,
        )
        user_message = prelude.user_message
        persist_metadata = prelude.persist_metadata
        if prelude.short_response is not None:
            from clawlet.bus.queue import OutboundMessage
            return OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=prelude.short_response,
                metadata=self._build_outbound_metadata(
                    source=source,
                    is_heartbeat=is_heartbeat,
                    heartbeat_ack_max_chars=heartbeat_ack_max_chars,
                    scheduled_payload=scheduled_payload,
                ),
            )
        turn_outcome = await self._turn_executor.execute(
            convo=convo,
            user_message=user_message,
            persist_metadata=persist_metadata,
            run_ctx=run_ctx,
            convo_key=convo_key,
            is_internal_autonomous=is_internal_autonomous,
            autonomous_depth=autonomous_depth,
        )
        final_response = turn_outcome.final_response
        is_error = turn_outcome.is_error
        iteration = turn_outcome.iterations
        tool_calls_used = turn_outcome.tool_calls_used
        action_intent = turn_outcome.action_intent
        final_metadata_extra = turn_outcome.final_metadata_extra

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

        from clawlet.bus.queue import OutboundMessage
        self._run_lifecycle.complete_run(
            run_id=run_ctx.run_id,
            session_id=convo.session_id,
            iterations=iteration,
            is_error=is_error,
            response_text=final_response,
            scheduled_payload=scheduled_payload,
            extra_payload={"tool_stats": self._current_run_tool_stats()},
        )
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


    def _canonicalize_heartbeat_outcome(
        self,
        *,
        response_text: str,
        is_error: bool,
        tool_names: list[str],
        blockers: list[str],
        action_summaries: list[str],
        tool_calls_used: int,
        provider_failures: Optional[list[str]] = None,
    ) -> tuple[str, bool]:
        return self._response_policy.canonicalize_heartbeat_outcome(
            response_text=response_text,
            is_error=is_error,
            tool_names=tool_names,
            blockers=blockers,
            action_summaries=action_summaries,
            provider_failures=provider_failures,
        )





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
    
    async def _build_messages(
        self,
        history: list[Message],
        query_hint: Optional[str] = None,
        is_heartbeat: bool = False,
    ) -> list[dict]:
        """Build messages list for LLM."""
        return await self._message_builder.build_messages(
            history,
            query_hint=query_hint,
            is_heartbeat=is_heartbeat,
            heartbeat_metadata=self._current_heartbeat_metadata,
        )

    def _record_heartbeat_result(self, response_text: str, mapped_tool_names: list[str], blockers: list[str]) -> None:
        self._heartbeat_reporter.record_result(
            response_text=response_text,
            channel=self._current_channel,
            chat_id=self._current_chat_id,
            heartbeat_metadata=self._current_heartbeat_metadata,
            mapped_tool_names=mapped_tool_names,
            blockers=blockers,
        )
    
    def _trim_history(self, history: list[Message]) -> None:
        """Trim history to prevent unbounded growth."""
        self._history_trimmer.trim(history)

    async def _maybe_handle_confirmation_reply(
        self,
        convo_key: str,
        session_id: str,
        user_message: str,
        history: list[Message],
    ) -> Optional[str]:
        async def _execute(tc: ToolCall):
            return await self._execute_tool(tc, approved=True)

        def _append(rendered: str, tc: ToolCall) -> None:
            history.append(Message(role="tool", content=rendered, metadata={"tool_name": tc.name, "tool_call_id": tc.id}))
            self._queue_persist(session_id, "tool", rendered)

        return await self._approval_service.maybe_handle_confirmation_reply(
            convo_key=convo_key,
            user_message=user_message,
            execute_tool=_execute,
            render_tool_result=self._render_tool_result,
            append_tool_message=_append,
        )


    async def _publish_outbound_with_retry(self, response: "OutboundMessage") -> bool:
        """Publish outbound messages with bounded retries and structured failure telemetry."""
        return await self._outbound_publisher.publish(
            response,
            session_id=self._session_id or "session",
            run_id=self._current_run_id or "",
        )

    
    
    
    async def close(self):
        """Clean up resources."""
        if self._persist_tasks:
            logger.info(f"Waiting for {len(self._persist_tasks)} persistence tasks to complete")
            await asyncio.gather(*list(self._persist_tasks), return_exceptions=True)

        # Save long-term memories
        try:
            await self.memory.close()
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
