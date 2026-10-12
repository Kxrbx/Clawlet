"""Progress publishing + runtime event emission for the agent loop.

Behavior-only mixin: all state lives on :class:`~clawlet.agent.loop.AgentLoop`.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from clawlet.bus.queue import OutboundMessage

from clawlet.runtime import RuntimeEvent


class ProgressPublishingMixin:
    """Publishing of progress updates, outbound metadata and runtime events."""

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

    async def _publish_outbound_with_retry(self, response: "OutboundMessage") -> bool:
        """Publish outbound messages with bounded retries and structured failure telemetry."""
        return await self._outbound_publisher.publish(
            response,
            session_id=self._session_id or "session",
            run_id=self._current_run_id or "",
        )

    def _should_suppress_outbound(self, response: "OutboundMessage") -> bool:
        """Suppress only empty heartbeat outputs and scheduler-only noise."""
        return self._response_policy.should_suppress_outbound(response)
