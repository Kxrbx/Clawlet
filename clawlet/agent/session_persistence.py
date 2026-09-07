"""Session persistence and storage lifecycle for the agent loop.

Behavior-only mixin: all state lives on :class:`~clawlet.agent.loop.AgentLoop`
(storage, memory, conversation states, persistence task bookkeeping).
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from clawlet.agent.models import ConversationState, Message
from clawlet.metrics import get_metrics
from clawlet.runtime import EVENT_STORAGE_FAILED, RuntimeEvent

UTC_TZ = timezone.utc


class SessionPersistenceMixin:
    """Session ids, conversation state, message persistence and teardown."""

    def _queue_persist(self, session_id: str, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """Queue persistence task with lifecycle tracking."""
        frozen_metadata = dict(metadata or {}) if metadata else None
        task = asyncio.create_task(self._persist_message(session_id, role, content, frozen_metadata))
        self._persist_tasks.add(task)
        task.add_done_callback(self._persist_tasks.discard)

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
        seed = f"{self.workspace.resolve()}::{channel}::{chat_id}"
        return hashlib.blake2s(seed.encode(), digest_size=6).hexdigest()

    def get_last_route(self) -> Optional[dict[str, str]]:
        """Return best-effort last active route for heartbeat target='last'."""
        if not self._last_route.get("channel") or not self._last_route.get("chat_id"):
            return None
        if (
            str(self._last_route.get("channel") or "") == "scheduler"
            and str(self._last_route.get("chat_id") or "") == "main"
        ):
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
        if metadata.get("persist") is False:
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
                if self._is_low_value_persisted_message(msg.role, msg.content, getattr(msg, "metadata", {})):
                    continue
                state.history.append(
                    Message(
                        role=msg.role,
                        content=msg.content,
                        metadata=dict(getattr(msg, "metadata", {}) or {}),
                        tool_calls=[],
                    )
                )
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

    def _should_capture_message_as_episode(
        self,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Capture useful continuity into episodic memory without promoting it to curated durable memory."""
        metadata = metadata or {}
        if self._is_low_value_persisted_message(role, content, metadata):
            return False

        lowered = (content or "").strip().lower()
        if len(lowered) < 18:
            return False
        if self.memory._is_low_value_memory(lowered):
            return False

        if role == "user":
            return True

        assistant_outcome_markers = (
            "i've prepared",
            "i have prepared",
            "i've created",
            "i have created",
            "i updated",
            "i've updated",
            "i attempted",
            "i found",
            "i checked",
            "here's",
            "here is",
            "the draft",
            "the post",
            "the latest",
            "status:",
        )
        return len(lowered) >= 40 and any(marker in lowered for marker in assistant_outcome_markers)

    def _memory_capture_plan(
        self,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Optional[dict[str, object]]:
        """Return the memory capture strategy for a persisted conversation message."""
        metadata = dict(metadata or {})
        if not content or self._is_low_value_persisted_message(role, content, metadata):
            return None

        importance = 5
        lowered = content.lower()
        if len(content) > 200:
            importance += 1
        if role == "assistant":
            importance += 1
        keywords = ("important", "remember", "todo", "task", "remind", "note", "save", "key", "critical")
        if any(keyword in lowered for keyword in keywords):
            importance += 2

        durable = self._should_persist_message_to_memory(role, content)
        episodic = self._should_capture_message_as_episode(role, content, metadata)
        if not durable and not episodic:
            return None

        memory_metadata = {
            "source": f"{role}:{metadata.get('session_id') or metadata.get('_session_id') or ''}".rstrip(":"),
            "role": role,
            "session_id": metadata.get("session_id") or metadata.get("_session_id") or "",
            "curated": durable,
        }
        if durable:
            memory_metadata["scope"] = "durable"
        else:
            memory_metadata["scope"] = "daily_note"
            importance = min(importance, 6)

        return {
            "category": "conversation",
            "importance": max(1, min(int(importance), 10)),
            "metadata": memory_metadata,
            "write_daily_note": episodic,
        }

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
