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
from clawlet.agent.recovery_checkpoint import RecoveryCheckpointService
from clawlet.agent.run_context import RunContext
from clawlet.agent.run_lifecycle import RunLifecycle
from clawlet.agent.run_prelude import RunPrelude
from clawlet.agent.run_orchestrator import RunOrchestrator
from clawlet.agent.response_policy import ResponsePolicy
from clawlet.agent.turn_executor import TurnExecutor
from clawlet.heartbeat.state import HeartbeatStateStore
from clawlet.providers.base import BaseProvider, LLMResponse
from clawlet.tools.registry import ToolRegistry, ToolResult, validate_tool_params
from clawlet.agent.memory import MemoryManager
from clawlet.storage.sqlite import SQLiteStorage
from clawlet.config import RuntimeSettings, StorageConfig
from clawlet.context import ContextEngine
from clawlet.workspace_layout import get_workspace_layout
from clawlet.metrics import get_metrics
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
    HEARTBEAT_ACTION_POLICY = (
        "Heartbeat poll policy:\n"
        "- Follow the heartbeat prompt strictly.\n"
        "- Do not infer or repeat old tasks from prior chats.\n"
        "- Read HEARTBEAT.md first when the prompt requires it.\n"
        "- Prefer `http_request` over shell/curl for API calls and JSON posts.\n"
        "- Use `review_daily_notes` before curating long-term memory, and use `curate_memory` when recent notes contain durable updates.\n"
        "- If nothing needs attention, reply exactly with HEARTBEAT_OK.\n"
        "- Avoid unrelated exploration unless the heartbeat task is blocked."
    )
    
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
        self._approval_service = ApprovalService()
        workspace_layout = get_workspace_layout(self.workspace)
        workspace_layout.ensure_directories()
        self._heartbeat_state = HeartbeatStateStore(workspace_layout.heartbeat_state_path)
        self._current_heartbeat_metadata: dict = {}
        
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
        self._run_tool_stats_snapshot = dict(self._tool_stats)
        
        # Persistence failure tracking
        self._persist_failures = 0
        
        # Event to signal that storage initialization is complete
        self._storage_ready = asyncio.Event()
        self._persist_tasks: set[asyncio.Task] = set()
        self._active_message_task: Optional[asyncio.Task] = None
        self._active_run_context: Optional[RunContext] = None

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
            remote_executor=self._build_remote_executor(),
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
        pending = self._approval_service.snapshot(key)
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
        return self._approval_service.peek(channel, chat_id)

    def _build_outbound_metadata(
        self,
        *,
        source: str,
        is_heartbeat: bool,
        heartbeat_ack_max_chars: int,
        scheduled_payload: Optional[dict],
        extra: Optional[dict] = None,
    ) -> dict:
        return self._run_lifecycle.build_outbound_metadata(
            source=source,
            is_heartbeat=is_heartbeat,
            heartbeat_ack_max_chars=heartbeat_ack_max_chars,
            scheduled_payload=scheduled_payload,
            extra=extra,
        )

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
        if self._current_source == "heartbeat":
            return
        if event_type in {"started", "provider_started", "finalizing"}:
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

    def _is_low_value_persisted_message(self, role: str, content: str, metadata: Optional[dict] = None) -> bool:
        """Skip persistence and history reload for low-signal runtime noise."""
        text = (content or "").strip()
        lowered = text.lower()
        metadata = metadata or {}
        is_heartbeat = bool(metadata.get("heartbeat")) or metadata.get("source") in {"heartbeat", "scheduler"}

        if role == "tool":
            return True
        if not text:
            return True
        if is_heartbeat:
            return True
        if (
            lowered.startswith("read heartbeat.md if it exists")
            or "i'll read the heartbeat.md" in lowered
            or "i will read the heartbeat.md" in lowered
            or "vérifier le fichier heartbeat.md" in lowered
            or lowered == "heartbeat_ok"
            or lowered.startswith("heartbeat_ok ")
            or lowered == "heartbeat_complete"
            or lowered.startswith("heartbeat_complete ")
            or lowered.startswith("heartbeat_needs_attention")
        ):
            return True
        noisy_fragments = (
            "read heartbeat.md if it exists",
            "reply heartbeat_ok",
            "follow it strictly",
            "do not infer or repeat old tasks from prior chats",
            "authorization: bearer <votre_cle_api>",
            "authorization: bearer your_api_key",
        )
        return any(fragment in lowered for fragment in noisy_fragments)

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
                if self._is_low_value_persisted_message(msg.role, msg.content):
                    continue
                state.history.append(Message(role=msg.role, content=msg.content, metadata={}, tool_calls=[]))
            if stored_messages:
                logger.info(f"Loaded {len(state.history)} sanitized messages for conversation {key}")

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
        
        # Save to long-term memory (MEMORY.md) only for memory-worthy messages.
        if role in ("assistant", "user") and self._should_persist_message_to_memory(role, content):
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
                    importance=importance,
                    metadata={
                        "source": f"{role}:{session_id}",
                        "role": role,
                        "session_id": session_id,
                    },
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

    def _activate_run_context(self, run_ctx: RunContext) -> None:
        self._active_run_context = run_ctx
        self._session_id = run_ctx.session_id
        self._current_run_id = run_ctx.run_id
        self._current_channel = run_ctx.channel
        self._current_chat_id = run_ctx.chat_id
        self._current_user_id = run_ctx.user_id
        self._current_user_name = run_ctx.user_name
        self._current_source = run_ctx.source
        self._current_heartbeat_metadata = run_ctx.metadata if run_ctx.is_heartbeat else {}
        self._last_route = {
            "channel": run_ctx.channel,
            "chat_id": run_ctx.chat_id,
            "user_id": run_ctx.user_id,
            "user_name": run_ctx.user_name,
        }

    def _clear_run_context(self) -> None:
        self._active_run_context = None
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

    def _has_recent_incomplete_action_context(self, history: list[Message]) -> bool:
        """True when recent assistant replies indicate an unfinished action flow."""
        for msg in reversed(history[-6:]):
            if msg.role == "user" and self._is_action_intent(msg.content or ""):
                return True
            if msg.role != "assistant":
                continue
            content = (msg.content or "").strip()
            if not content:
                return True
            if self._looks_like_incomplete_followthrough(content, tool_calls_used=0):
                return True
            lowered = content.lower()
            if (
                "i'd love to" in lowered
                or "let me check" in lowered
                or "need to check" in lowered
                or "don't see a direct tool" in lowered
                or "i can do that" in lowered
            ):
                return True
        return False

    def _fallback_empty_response(self, *, action_intent: bool, is_heartbeat: bool) -> str:
        """Never surface an empty assistant reply to channels."""
        if is_heartbeat:
            return "HEARTBEAT_OK"
        if action_intent:
            return (
                "I got stuck before completing the action. "
                "Please retry, or start a new conversation so I can run it cleanly."
            )
        return "I got stuck and produced an empty reply. Please try again."

    def _sanitize_conversation_history(self, history: list[Message]) -> None:
        """Drop malformed tool artifacts that poison later prompts."""
        if not history:
            return
        sanitized: list[Message] = []
        removed = 0
        for msg in history:
            if msg.role == "tool" and not (msg.metadata or {}).get("tool_call_id"):
                removed += 1
                continue
            sanitized.append(msg)
        if removed:
            history[:] = sanitized
            logger.info(f"Removed {removed} malformed tool message(s) from conversation history")

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
        history: Optional[list[Message]] = None,
    ) -> bool:
        """Decide whether to re-run with tools enabled after parser detected tool calls."""
        if not tool_calls:
            return False

        lowered = (user_message or "").strip().lower()
        if not lowered:
            return False
        if self._is_trivial_chat_message(lowered) and not self._has_recent_incomplete_action_context(history or []):
            return False

        # Only promote when parsed calls are to known tools (or aliases).
        for tc in tool_calls:
            mapped = self._tool_aliases.get(tc.name, tc.name)
            if self.tools.get(mapped) is None:
                return False

        if self._has_recent_incomplete_action_context(history or []):
            return True

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

    def _sanitize_final_response(self, content: str, tool_calls_used: int) -> str:
        """Sanitize final user-facing text when no further tool execution should happen."""
        return self._response_policy.sanitize_final_response(content, tool_calls_used)

    def _rewrite_specialized_tool_call(self, tool_call: ToolCall) -> ToolCall:
        """Convert brittle shell-based HTTP calls into structured tool calls when possible."""
        normalized = self._normalize_special_file_path(tool_call)
        if normalized is not tool_call:
            tool_call = normalized
        if tool_call.name != "shell":
            return tool_call
        if self.tools.get("http_request") is None:
            return tool_call

        command = str((tool_call.arguments or {}).get("command", "") or "").strip()
        rewritten_args = self._parse_curl_shell_command(command)
        if not rewritten_args:
            return tool_call

        logger.info("Rewriting shell curl into structured http_request call")
        return ToolCall(id=tool_call.id, name="http_request", arguments=rewritten_args)

    def _normalize_special_file_path(self, tool_call: ToolCall) -> ToolCall:
        """Collapse known workspace-relative identity paths onto the real workspace root."""
        if tool_call.name not in {"read_file", "write_file", "edit_file"}:
            return tool_call
        arguments = dict(tool_call.arguments or {})
        raw_path = str(arguments.get("path", "") or "").strip()
        if not raw_path:
            return tool_call

        normalized = raw_path.replace("\\", "/").lower()
        if not normalized.endswith("/heartbeat.md") and normalized != "heartbeat.md":
            return tool_call

        candidate = get_workspace_layout(self.workspace).heartbeat_path
        if not candidate.exists():
            return tool_call

        if raw_path == str(candidate) or raw_path == "HEARTBEAT.md":
            return tool_call

        arguments["path"] = str(candidate)
        logger.info(f"Normalizing HEARTBEAT.md path: {raw_path} -> {candidate}")
        return ToolCall(id=tool_call.id, name=tool_call.name, arguments=arguments)

    def _parse_curl_shell_command(self, command: str) -> Optional[dict]:
        """Best-effort parser for common curl invocations emitted by the model."""
        text = (command or "").strip()
        if "curl" not in text.lower():
            return None

        url_match = re.search(r"(https?://[^\s\"']+)", text, re.IGNORECASE)
        if not url_match:
            return None

        method_match = re.search(r"(?:^|\s)-X\s+([A-Za-z]+)\b", text)
        data_payload = self._extract_json_payload_from_curl(text)
        header_pairs = self._extract_headers_from_curl(text)
        method = (method_match.group(1).upper() if method_match else ("POST" if data_payload is not None else "GET"))

        args: dict[str, object] = {
            "method": method,
            "url": url_match.group(1),
        }
        if header_pairs:
            args["headers"] = header_pairs
        if data_payload is not None:
            args["json_body"] = data_payload
        return args

    def _extract_headers_from_curl(self, command: str) -> dict[str, str]:
        """Extract simple header pairs from a curl command string."""
        headers: dict[str, str] = {}
        for match in re.finditer(r"(?:^|\s)-H\s+", command):
            start = match.end()
            quote = command[start] if start < len(command) and command[start] in {"'", '"'} else ""
            if quote:
                start += 1
                end = command.find(quote, start)
                if end == -1:
                    continue
                raw = command[start:end]
            else:
                next_space = command.find(" ", start)
                end = len(command) if next_space == -1 else next_space
                raw = command[start:end]
            if ":" not in raw:
                continue
            key, value = raw.split(":", 1)
            headers[key.strip()] = value.strip()
        return headers

    def _extract_json_payload_from_curl(self, command: str) -> Optional[dict]:
        """Extract a JSON object from curl -d/--data payloads without relying on shell parsing."""
        data_flag = re.search(r"(?:^|\s)(?:-d|--data(?:-raw)?)\s+", command)
        if not data_flag:
            return None

        start = command.find("{", data_flag.end())
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        end = -1
        for index in range(start, len(command)):
            char = command[index]
            if in_string:
                if escape:
                    escape = False
                    continue
                if char == "\\":
                    escape = True
                    continue
                if char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
                continue
            if char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break

        if end == -1:
            return None

        raw_json = command[start:end]
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _sanitize_template_placeholders(self, content: str) -> str:
        """Remove obvious template/example placeholders from user-facing replies."""
        raw_placeholder_hits = sum(
            len(re.findall(pattern, content or "", flags=re.IGNORECASE))
            for pattern in self.PLACEHOLDER_PATTERNS
        )
        cleaned = self._sanitize_context_placeholders(content)
        cleaned = re.sub(r"Bearer\s+the configured value\b", "a configured API key", cleaned)
        cleaned = re.sub(r"Bearer\s+your current API key\b", "your current API key", cleaned)
        cleaned = re.sub(r"moltbook_sk_[A-Za-z0-9_\-]+", "[redacted]", cleaned)
        cleaned = re.sub(r"sk-or-v1-[A-Za-z0-9]+", "[redacted]", cleaned)
        cleaned = re.sub(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b", "[redacted]", cleaned)
        word_count = len(re.findall(r"\b\w+\b", content or ""))
        if raw_placeholder_hits >= 3 and word_count <= raw_placeholder_hits + 2:
            return self._rewrite_placeholder_heavy_response("")
        elif self._contains_placeholder_artifacts(cleaned):
            cleaned = self._rewrite_placeholder_heavy_response(cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _sanitize_context_placeholders(self, content: str) -> str:
        """Remove obvious template/example placeholders from model-facing context."""
        cleaned = content or ""
        replacements = [
            (r"Bearer\s+YOUR_API_KEY\b", "Bearer the configured value"),
            (r"Bearer\s+VOTRE_CLE_API\b", "Bearer the configured value"),
            (r"Bearer\s+<[^>]*(?:api[_\s-]*key|clé[_\s-]*api|cle[_\s-]*api|token|bearer)[^>]*>", "Bearer the configured value"),
            (r"\bYOUR_[A-Z0-9_]+\b", "the configured value"),
            (r"\bVOTRE_[A-Z0-9_]+\b", "the configured value"),
            (r"\bMOLTY_NAME\b", "the target molty"),
            (r"\bPOST_ID\b", "the target post ID"),
            (r"\bCOMMENT_ID\b", "the target comment ID"),
            (r"\bCURSOR_FROM_PREVIOUS_RESPONSE\b", "the next page cursor"),
            (r"\bYourAgentName\b", "the configured agent name"),
            (r"\bYourName\b", "the current name"),
            (r"\byour-human@example\.com\b", "the owner's email address"),
            (r"\bmoltbook_xxx\b", "a Moltbook API key"),
            (r"\bmoltbook_claim_xxx\b", "a Moltbook claim URL token"),
            (r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){0,4}(?:_ID|_KEY|_TOKEN|_NAME|_VALUE|_EMAIL|_URL|_HANDLE)\b", "the live value"),
            (r"uuid\.\.\.", "the target resource"),
            (r"\[Your [^\]]+\]", "your actual details"),
            (r"\[Preferred [^\]]+\]", "your preferred name"),
            (r"\[(?:insert|replace|set|use|enter|provide)[^\]]+\]", "the real value"),
            (r"\[Optional\]", ""),
            (r"<[^>]*(?:api[_\s-]*key|clé[_\s-]*api|cle[_\s-]*api|token|bearer)[^>]*>", "a configured API key"),
            (r"<[^>]*(?:post[_\s-]*id|comment[_\s-]*id|molty|name|nom)[^>]*>", "the real target details"),
            (r"<[A-Z][A-Z0-9 _-]{1,48}>", "the real value"),
        ]
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _contains_placeholder_artifacts(self, content: str) -> bool:
        text = content or ""
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.PLACEHOLDER_PATTERNS)

    def _tool_args_contain_template_placeholders(self, tool_name: str, args: dict) -> bool:
        """Detect templated values that should never be executed as live tool inputs."""
        def _walk(value) -> bool:
            if isinstance(value, dict):
                return any(_walk(v) or _walk(k) for k, v in value.items())
            if isinstance(value, list):
                return any(_walk(item) for item in value)
            if not isinstance(value, str):
                return False
            text = value.strip()
            if not text:
                return False
            if self._contains_placeholder_artifacts(text):
                return True
            patterns = (
                r"\bYOUR_API_KEY_HERE\b",
                r"\bYOUR_[A-Z0-9_]+\b",
                r"\bVOTRE_[A-Z0-9_]+\b",
                r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){0,4}(?:_ID|_KEY|_TOKEN|_NAME|_VALUE|_EMAIL|_URL|_HANDLE)\b",
                r"\bMOLTY_NAME\b",
                r"\bPOST_ID\b",
                r"\bCOMMENT_ID\b",
                r"\bCURSOR_FROM_PREVIOUS_RESPONSE\b",
                r"\bYourAgentName\b",
                r"\bYourName\b",
                r"\[Your [^\]]+\]",
                r"\[Preferred [^\]]+\]",
                r"\[(?:insert|replace|set|use|enter|provide)[^\]]+\]",
                r"\[Optional\]",
                r"<[A-Z][A-Z0-9 _-]{1,48}>",
                r"<[^>]*(?:api[_\s-]*key|clé[_\s-]*api|cle[_\s-]*api|token|bearer|post[_\s-]*id|comment[_\s-]*id|molty|name|nom)[^>]*>",
            )
            return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

        if tool_name not in {"http_request", "shell", "fetch_url", "write_file", "edit_file"}:
            return False
        return _walk(args)

    def _rewrite_placeholder_heavy_response(self, content: str) -> str:
        """Fallback rewrite when a response still reads like a template."""
        text = content or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        kept: list[str] = []
        for line in lines:
            if self._contains_placeholder_artifacts(line):
                continue
            kept.append(line)
        if kept:
            return "\n\n".join(kept)
        return (
            "I need the real target details from the live context before I can complete that action. "
            "I will use the actual values on the next attempt."
        )

    def _should_persist_message_to_memory(self, role: str, content: str) -> bool:
        """Persist only messages likely to remain useful across future sessions."""
        lowered = (content or "").strip().lower()
        if not lowered:
            return False
        if len(lowered) < 25:
            return False
        if self.memory._is_low_value_memory(lowered):
            return False
        low_value_runtime_fragments = (
            "read heartbeat.md",
            "heartbeat.md first",
            "heartbeat_ok",
            "heartbeat_complete",
            "authorization: bearer",
            "http_request",
            "curl ",
            "api key",
        )
        if any(fragment in lowered for fragment in low_value_runtime_fragments):
            return False

        durable_keywords = (
            "preference",
            "prefer",
            "call me",
            "timezone",
            "project",
            "working on",
            "my name is",
            "you can call me",
            "remember",
            "task",
            "todo",
            "deadline",
            "allergic",
            "likes ",
            "dislikes ",
            "important",
        )
        return role == "user" and any(keyword in lowered for keyword in durable_keywords)

    def _extract_explicit_urls(self, user_message: str) -> list[str]:
        """Extract normalized explicit URLs from user message."""
        urls: list[str] = []
        seen: set[str] = set()
        for raw in self.URL_PATTERN.findall(user_message or ""):
            candidate = raw.rstrip("`.,);!?'\"")
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
        if self._is_authenticated_api_url(explicit_urls[0]):
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

    @staticmethod
    def _is_authenticated_api_url(url: str) -> bool:
        lowered = (url or "").strip().lower()
        return "/api/" in lowered

    def _is_action_oriented_request(self, user_message: str, is_heartbeat: bool) -> bool:
        if is_heartbeat:
            return True
        lowered = (user_message or "").strip().lower()
        action_markers = (
            "introduce yourself",
            "post ",
            "comment ",
            "reply ",
            "perform",
            "do it",
            "check moltbook",
            "heartbeat check",
            "update your credentials",
            "update the api key",
            "introduce yourself on",
        )
        return any(marker in lowered for marker in action_markers)

    def _is_low_value_exploration_tool(
        self,
        tool_call: ToolCall,
        user_message: str,
        is_heartbeat: bool,
        tool_calls_used: int,
    ) -> bool:
        if not self._is_action_oriented_request(user_message, is_heartbeat):
            return False

        mapped_name = self._tool_aliases.get(tool_call.name, tool_call.name)
        arguments = dict(tool_call.arguments or {})
        path = str(arguments.get("path", "") or "")
        normalized_path = path.lower()
        normalized_name = Path(path).name.lower()
        url = str(arguments.get("url", "") or "").strip().lower()

        if mapped_name == "list_skills":
            return True
        if mapped_name == "get_context":
            return True
        if mapped_name == "read_file" and normalized_name == "skill.md":
            return True
        if mapped_name == "read_file" and normalized_name == "heartbeat.md":
            return is_heartbeat and tool_calls_used > 0
        if mapped_name == "read_file" and normalized_name == "credentials.json":
            if "/.config/" in normalized_path or normalized_path.startswith(".config/"):
                return True
        if mapped_name == "read_file" and normalized_path.endswith("/config.yaml"):
            return True
        if mapped_name == "read_file" and normalized_path.endswith("/config.yml"):
            return True
        if mapped_name == "list_dir" and normalized_path in {
            "/root/.clawlet",
            "/root/.clawlet/workspace",
            "workspace",
        }:
            return True
        if mapped_name == "fetch_url" and is_heartbeat and self._is_low_value_heartbeat_url(url):
            return True
        if is_heartbeat and tool_calls_used > 0 and mapped_name in {"read_file", "list_dir"}:
            return True
        return False

    @staticmethod
    def _is_low_value_heartbeat_url(url: str) -> bool:
        lowered = (url or "").strip().lower()
        if not lowered:
            return False
        return any(
            lowered.endswith(suffix)
            for suffix in ("/skill.md", "/heartbeat.md", "/rules.md", "/messaging.md")
        )

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
        cleaned = self._sanitize_context_placeholders(raw)
        cleaned = re.sub(r"moltbook_sk_[A-Za-z0-9_\-]+", "[redacted]", cleaned)
        cleaned = re.sub(r"sk-or-v1-[A-Za-z0-9]+", "[redacted]", cleaned)
        cleaned = re.sub(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b", "[redacted]", cleaned)
        return cleaned

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
        raw_args = dict(tool_call.arguments or {})
        failure_key = self._tool_failure_key(tool_name, raw_args)
        
        # Check if circuit is open for this tool
        if failure_key in self._tool_circuit_open_until:
            if now < self._tool_circuit_open_until[failure_key]:
                # Circuit is open, skip execution
                logger.warning(f"Circuit open for tool bucket '{failure_key}'. Skipping execution.")
                await self._publish_progress_update(
                    "tool_failed",
                    f"Skipped `{tool_name}` because it is temporarily unavailable.",
                    detail="circuit open",
                )
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Tool '{tool_name}' is temporarily unavailable due to repeated failures.",
                    data={"transient": True, "failure_key": failure_key},
                )
            else:
                # Circuit timeout expired, reset
                logger.info(f"Circuit breaker timeout for tool bucket '{failure_key}' expired, allowing test call")
                self._tool_circuit_open_until.pop(failure_key, None)
                self._tool_failures[failure_key] = 0  # reset failures
        
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
        execution_target_raw = str(raw_args.pop("_execution_target", "local")).strip().lower()
        execution_target = "remote" if execution_target_raw == "remote" else "local"
        lane = str(raw_args.pop("_lane", "")).strip().lower()
        cacheable_override_raw = raw_args.pop("_cacheable", None)
        cacheable_override: Optional[bool] = None
        if isinstance(cacheable_override_raw, bool):
            cacheable_override = cacheable_override_raw

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
        repaired_args = self._repair_templated_tool_args(tool_name, args)
        if repaired_args is not None:
            logger.info(f"Applied deterministic repair to templated args for '{tool_name}'")
            args = repaired_args
        if self._tool_args_contain_template_placeholders(tool_name, args):
            error_msg = "Tool call contains template placeholders instead of live values"
            logger.warning(f"Rejected templated tool call for '{tool_name}': {args}")
            self._tool_stats["calls_rejected"] += 1
            await self._publish_progress_update(
                "tool_failed",
                f"Rejected templated call for `{tool_name}`.",
                detail=error_msg,
            )
            return ToolResult(success=False, output="", error=error_msg)
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
            cacheable=cacheable_override,
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
            if failure_key in self._tool_failures:
                self._tool_failures[failure_key] = 0
            logger.info(f"Tool {tool_name} succeeded: {result.output[:100]}...")
            await self._publish_progress_update("tool_completed", f"Completed `{tool_name}`.", detail=tool_name)
        else:
            self._tool_stats["calls_failed"] += 1
            result_data = result.data if isinstance(result.data, dict) else {}
            is_transient_failure = bool(result_data.get("transient")) or "temporarily unavailable" in (
                (result.error or "").lower()
            )
            failures = self._tool_failures.get(failure_key, 0)
            if is_transient_failure:
                failures += 1
                self._tool_failures[failure_key] = failures
            # Increment tool error metric
            get_metrics().inc_tool_errors()
            logger.warning(
                f"Tool {tool_name} failed: {result.error} "
                f"(bucket={failure_key}, transient={is_transient_failure}, failures: {failures})"
            )
            await self._publish_progress_update(
                "tool_failed",
                f"`{tool_name}` failed.",
                detail=result.error or result.output[:200],
            )
            
            if is_transient_failure and failures >= self._tool_failure_threshold:
                # Trip circuit breaker
                open_until = now + timedelta(seconds=self._tool_circuit_timeout_seconds)
                self._tool_circuit_open_until[failure_key] = open_until
                logger.error(
                    f"Circuit breaker tripped for tool bucket '{failure_key}'! "
                    f"Open until {open_until.isoformat()}"
                )
        
        return result

    def _tool_failure_key(self, tool_name: str, args: dict) -> str:
        if tool_name != "http_request":
            return tool_name
        method = str(args.get("method", "GET") or "GET").strip().upper()
        url = str(args.get("url", "") or "").strip()
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path or "/"
        return f"{tool_name}:{method}:{host}{path}"

    def _repair_templated_tool_args(self, tool_name: str, args: dict) -> Optional[dict]:
        if not self._tool_args_contain_template_placeholders(tool_name, args):
            return None
        if tool_name != "http_request":
            return None

        repaired = json.loads(json.dumps(args))
        changed = False
        headers = repaired.get("headers")
        if isinstance(headers, dict):
            auth_value = str(headers.get("Authorization", "") or "")
            if auth_value and self._contains_placeholder_artifacts(auth_value):
                headers.pop("Authorization", None)
                changed = True

        body = repaired.get("json_body")
        if isinstance(body, dict):
            placeholder_keys = [
                key for key, value in body.items()
                if isinstance(value, str) and self._contains_placeholder_artifacts(value)
            ]
            for key in placeholder_keys:
                body.pop(key, None)
                changed = True

        return repaired if changed else None

    def _canonicalize_heartbeat_outcome(
        self,
        *,
        response_text: str,
        is_error: bool,
        tool_names: list[str],
        blockers: list[str],
        action_summaries: list[str],
        tool_calls_used: int,
    ) -> tuple[str, bool]:
        return self._response_policy.canonicalize_heartbeat_outcome(
            response_text=response_text,
            is_error=is_error,
            tool_names=tool_names,
            blockers=blockers,
            action_summaries=action_summaries,
        )

    def _summarize_heartbeat_tool_result(self, tool_name: str, result: ToolResult) -> str:
        return self._response_policy.summarize_heartbeat_tool_result(tool_name, result)

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
    
    def _build_messages(
        self,
        history: list[Message],
        query_hint: Optional[str] = None,
        is_heartbeat: bool = False,
    ) -> list[dict]:
        """Build messages list for LLM."""
        return self._message_builder.build_messages(
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

    def _requires_confirmation(self, tool_call: ToolCall) -> str:
        """Return a non-empty reason if the tool call should require explicit user confirmation."""
        return self._runtime_policy.confirmation_reason(tool_call.name, tool_call.arguments or {}, approved=False)

    async def _publish_outbound_with_retry(self, response: "OutboundMessage") -> bool:
        """Publish outbound messages with bounded retries and structured failure telemetry."""
        return await self._outbound_publisher.publish(
            response,
            session_id=self._session_id or "session",
        )

    def _should_suppress_outbound(self, response: "OutboundMessage") -> bool:
        """Suppress only empty heartbeat outputs and scheduler-only noise."""
        return self._response_policy.should_suppress_outbound(response)
    
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
            self.memory.close()
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
