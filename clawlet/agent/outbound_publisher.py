"""Outbound response publication with retry, suppression, and telemetry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


@dataclass(slots=True)
class OutboundPublisher:
    bus: Any
    runtime_config: Any
    response_policy: Any
    heartbeat_state: Any
    logger: Any
    metrics_factory: Callable[[], Any]
    classify_error_text: Callable[[str], Any]
    failure_payload: Callable[[Any], dict]
    emit_runtime_event: Callable[[str, str, dict], None]
    event_channel_failed: str
    now_fn: Callable[[], Any]

    async def publish(self, response: Any, *, session_id: str, run_id: str = "") -> bool:
        if self.response_policy.should_suppress_outbound(response):
            self.logger.info(
                f"Suppressed low-value heartbeat outbound for {response.channel}/{response.chat_id}"
            )
            self.metrics_factory().inc_heartbeat_acks_suppressed()
            return True

        response.metadata = dict(response.metadata or {})
        response.metadata.setdefault("_session_id", session_id)
        if run_id:
            response.metadata.setdefault("_run_id", run_id)

        retries = max(0, int(self.runtime_config.outbound_publish_retries))
        backoff = max(0.0, float(self.runtime_config.outbound_publish_backoff_seconds))
        attempts = retries + 1
        for attempt in range(1, attempts + 1):
            try:
                await self.bus.publish_outbound(response)
                if bool((response.metadata or {}).get("heartbeat")) and response.channel != "scheduler":
                    self.heartbeat_state.record_outreach(
                        now=self.now_fn(),
                        response_text=response.content,
                    )
                return True
            except Exception as e:
                failure = self.classify_error_text(str(e))
                self.logger.error(
                    f"Failed to publish outbound response (attempt {attempt}/{attempts}, code={failure.code}): {e}"
                )
                self.emit_runtime_event(
                    self.event_channel_failed,
                    session_id,
                    {
                        "channel": getattr(response, "channel", ""),
                        "chat_id": getattr(response, "chat_id", ""),
                        "attempt": attempt,
                        "error": str(e),
                        **self.failure_payload(failure),
                    },
                )
                if attempt >= attempts:
                    return False
                if backoff > 0:
                    await asyncio.sleep(backoff * attempt)
        return False
