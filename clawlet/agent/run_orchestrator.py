"""Run orchestration shell around AgentLoop core execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from clawlet.agent.run_context import RunContext, RunModeProfile

if TYPE_CHECKING:
    from clawlet.bus.queue import InboundMessage, OutboundMessage
    from clawlet.agent.loop import AgentLoop


class RunOrchestrator:
    """Prepare per-run context, then delegate to AgentLoop core execution."""

    def __init__(self, agent: "AgentLoop"):
        self.agent = agent

    async def process_message(self, msg: "InboundMessage") -> "OutboundMessage | None":
        metadata = msg.metadata or {}
        source = str(metadata.get("source", "") or "")
        is_heartbeat = bool(metadata.get("heartbeat")) or source == "heartbeat"
        heartbeat_ack_max_chars = int(metadata.get("ack_max_chars", 24) or 24)
        convo = await self.agent._get_conversation_state(msg.channel, msg.chat_id)
        run_ctx = RunContext(
            session_id=convo.session_id,
            run_id=self.agent._next_run_id(convo.session_id),
            channel=msg.channel,
            chat_id=msg.chat_id,
            user_id=str(msg.user_id or ""),
            user_name=str(msg.user_name or ""),
            source=source,
            metadata=metadata,
            scheduled_payload=self.agent._scheduled_payload_from_metadata(metadata, source, is_heartbeat),
            mode=RunModeProfile(
                is_heartbeat=is_heartbeat,
                heartbeat_ack_max_chars=heartbeat_ack_max_chars,
                iteration_limit=self.agent.MAX_HEARTBEAT_ITERATIONS if is_heartbeat else self.agent.max_iterations,
                tool_call_limit=self.agent.MAX_HEARTBEAT_TOOL_CALLS if is_heartbeat else self.agent.max_tool_calls_per_message,
                no_progress_limit=self.agent.HEARTBEAT_NO_PROGRESS_LIMIT if is_heartbeat else self.agent.NO_PROGRESS_LIMIT,
                max_wall_time_seconds=60.0 if is_heartbeat else 180.0,
            ),
            started_at=datetime.now(timezone.utc),
        )
        self.agent._activate_run_context(run_ctx)
        try:
            return await self.agent._process_message_core(msg, convo, run_ctx)
        finally:
            self.agent._clear_run_context()
