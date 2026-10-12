"""Run orchestration shell around AgentLoop core execution.

v2: routes every inbound message through the always-on Orchestrator
(classify -> delegate to a profiled sub-agent -> attribute), with the
classic single-loop turn as the traced fallback path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from loguru import logger

from clawlet.agent.run_context import RunContext, RunModeProfile

if TYPE_CHECKING:
    from clawlet.bus.queue import InboundMessage, OutboundMessage
    from clawlet.agent.loop import AgentLoop


class RunOrchestrator:
    """Prepare per-run context, then orchestrate (delegate-first)."""

    def __init__(self, agent: "AgentLoop"):
        self.agent = agent

    async def process_message(self, msg: "InboundMessage") -> "OutboundMessage | None":
        metadata = msg.metadata or {}
        source = str(metadata.get("source", "") or "")
        # Delegated child turns run the classic pipeline directly to avoid
        # infinite orchestration recursion (depth guard is also enforced).
        if metadata.get("delegated_kind"):
            return await self._run_core(msg, metadata, source)
        try:
            return await self._run_orchestrated(msg, metadata, source)
        except Exception as e:
            logger.error(f"Orchestrator failed ({e}); falling back to classic turn")
            return await self._run_core(msg, metadata, source)

    async def _run_orchestrated(
        self, msg: "InboundMessage", metadata: dict, source: str
    ) -> "OutboundMessage | None":
        from clawlet.agent.orchestrator import Orchestrator

        run_ctx = await self._build_run_context(msg, metadata, source)
        self.agent._activate_run_context(run_ctx)
        try:
            orchestrator = self._make_orchestrator()

            async def _fallback(_msg: "InboundMessage") -> "OutboundMessage | None":
                return await self.agent._process_message_core(_msg, await self._convo(msg), run_ctx)

            return await orchestrator.process_message(msg, fallback_runner=_fallback)
        finally:
            self.agent._clear_run_context()

    async def _run_core(
        self, msg: "InboundMessage", metadata: dict, source: str
    ) -> "OutboundMessage | None":
        run_ctx = await self._build_run_context(msg, metadata, source)
        self.agent._activate_run_context(run_ctx)
        try:
            convo = await self._convo(msg)
            return await self.agent._process_message_core(msg, convo, run_ctx)
        finally:
            self.agent._clear_run_context()

    async def _convo(self, msg: "InboundMessage"):
        return await self.agent._get_conversation_state(msg.channel, msg.chat_id)

    def _make_orchestrator(self):
        from clawlet.agent.orchestrator import Orchestrator

        config = getattr(self.agent, "full_config", None)
        settings = getattr(config, "orchestrator", None) if config is not None else None
        profiles = getattr(config, "task_profiles", None) if config is not None else None
        kwargs: dict = {}
        if settings is not None:
            kwargs["settings"] = settings
        if isinstance(profiles, dict) and profiles:
            kwargs["task_profiles"] = profiles
        return Orchestrator(self.agent, **kwargs)

    async def _build_run_context(
        self, msg: "InboundMessage", metadata: dict, source: str
    ) -> RunContext:
        source = str(metadata.get("source", "") or "")
        is_heartbeat = bool(metadata.get("heartbeat")) or source == "heartbeat"
        heartbeat_ack_max_chars = int(metadata.get("ack_max_chars", 24) or 24)
        convo = await self.agent._get_conversation_state(msg.channel, msg.chat_id)
        return RunContext(
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
                max_wall_time_seconds=120.0 if is_heartbeat else 180.0,
            ),
            started_at=datetime.now(timezone.utc),
        )
