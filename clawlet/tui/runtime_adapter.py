from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from types import MethodType
from typing import Any, Awaitable, Callable, Optional

from clawlet.bus.queue import InboundMessage, OutboundMessage
from clawlet.cli.runtime_ui import _build_effective_heartbeat_context, _create_provider
from clawlet.tui.events import ApprovalRequest, AssistantMessage, BrainStateUpdate, HeartbeatSnapshot, LogEvent, RuntimeStatus, ToolLifecycle
from clawlet.workspace_layout import get_workspace_layout

EventSink = Callable[[object], None]


class InstrumentedToolRegistry:
    def __init__(self, base, emit: EventSink, session_id: str):
        self._base = base
        self._emit = emit
        self._session_id = session_id

    def __getattr__(self, name: str):
        return getattr(self._base, name)

    async def execute(self, name: str, **kwargs):
        self._emit(ToolLifecycle(session_id=self._session_id, tool_name=name, status="RUNNING", summary="Executing tool.", arguments=kwargs, raw={"Input": kwargs}))
        result = await self._base.execute(name, **kwargs)
        status = "SUCCESS" if getattr(result, "success", False) else "FAILED"
        self._emit(
            ToolLifecycle(
                session_id=self._session_id,
                tool_name=name,
                status=status,
                summary=(getattr(result, "output", "") or getattr(result, "error", "") or "Tool completed.")[:240],
                arguments=kwargs,
                raw={"Input": kwargs, "Output": getattr(result, "output", ""), "Error": getattr(result, "error", None)},
            )
        )
        return result


@dataclass
class LocalRuntimeHandle:
    session_id: str
    provider_name: str
    model_name: str | None
    send_text: Callable[[str], Awaitable[None]]
    poll_outbound: Callable[[], Awaitable[OutboundMessage]]
    stop: Callable[[], Awaitable[None]]
    emit_snapshot: Callable[[], None]


async def create_local_runtime(workspace: Path, model: Optional[str], emit: EventSink, session_id: str = "local") -> LocalRuntimeHandle:
    from clawlet.agent.identity import IdentityLoader
    from clawlet.agent.loop import AgentLoop
    from clawlet.config import load_config
    from clawlet.runtime import build_runtime_services
    from clawlet.bus.queue import MessageBus

    identity = IdentityLoader(workspace).load_all()
    bus = MessageBus()
    config = load_config(workspace)
    provider, effective_model = _create_provider(config, model)
    provider_name = config.provider.primary
    services = build_runtime_services(workspace, config)
    services.tools = InstrumentedToolRegistry(services.tools, emit=emit, session_id=session_id)

    agent = AgentLoop(
        bus=bus,
        workspace=workspace,
        identity=identity,
        provider=provider,
        model=effective_model,
        tools=services.tools,
        memory_manager=services.memory_manager,
        max_iterations=config.agent.max_iterations,
        max_tool_calls_per_message=config.agent.max_tool_calls_per_message,
        storage_config=config.storage,
        runtime_config=config.runtime,
    )

    async def _progress_override(self, event_type: str, text: str, *, detail: str = "", final: bool = False) -> None:
        if not text.strip():
            return
        event_map = {
            "tool_started": "RUNNING",
            "tool_completed": "SUCCESS",
            "tool_failed": "FAILED",
            "approval_required": "REQUIRES APPROVAL",
        }
        status = event_map.get(event_type)
        if status:
            emit(ToolLifecycle(session_id=session_id, tool_name=detail or "tool", status=status, summary=text.strip(), raw={"detail": detail, "final": final}))
        else:
            emit(LogEvent(level="DEBUG", channel="system", message=f"{event_type}: {text.strip()}"))

    agent._publish_progress_update = MethodType(_progress_override, agent)

    agent_task = asyncio.create_task(agent.run())
    emit(RuntimeStatus(status="IDLE", detail="Runtime booted."))

    def emit_snapshot() -> None:
        memory = [
            ("project_root", str(workspace)),
            ("session", session_id),
            ("max_iterations", str(config.agent.max_iterations)),
            ("max_tool_calls", str(config.agent.max_tool_calls_per_message)),
        ]
        tools = [(tool.name, "ACTIVE") for tool in services.tools.all_tools()]
        emit(
            BrainStateUpdate(
                session_id=session_id,
                provider=provider_name,
                model=effective_model or "default",
                context_used_tokens=0,
                context_max_tokens=128000,
                memory=memory,
                tools=tools,
                status="IDLE",
            )
        )
        hb_cfg = config.heartbeat
        quiet = "Disabled" if int(getattr(hb_cfg, "quiet_hours_start", 0) or 0) == int(getattr(hb_cfg, "quiet_hours_end", 0) or 0) else f"{hb_cfg.quiet_hours_start}:00-{hb_cfg.quiet_hours_end}:00 UTC"
        layout = get_workspace_layout(workspace)
        heartbeat_text = "comment-only"
        try:
            heartbeat_raw = layout.heartbeat_path.read_text(encoding="utf-8")
            heartbeat_text = _build_effective_heartbeat_context(f"## Periodic Tasks\n\n{heartbeat_raw}", hb_cfg) or "comment-only"
        except FileNotFoundError:
            pass
        next_runs = []
        for line in heartbeat_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("<!--"):
                next_runs.append(f"00:30:00 [task] {stripped[:48]}")
            if len(next_runs) >= 3:
                break
        emit(
            HeartbeatSnapshot(
                enabled=bool(getattr(hb_cfg, "enabled", False)),
                interval_minutes=int(getattr(hb_cfg, "interval_minutes", 0) or 0),
                quiet_hours=quiet,
                next_runs=next_runs or ["No scheduled heartbeat tasks"],
                pulse_label=f"{int(getattr(hb_cfg, 'interval_minutes', 0) or 0)}m pulse",
                last_task="Awaiting first run",
                active_crons=len(next_runs),
            )
        )

    async def send_text(text: str) -> None:
        emit(RuntimeStatus(status="RUNNING", detail="Processing user message."))
        emit(LogEvent(level="CHAT", channel="chat", message=text))
        await bus.publish_inbound(InboundMessage(channel="cli", chat_id=session_id, content=text))

    async def poll_outbound() -> OutboundMessage:
        message = await bus.consume_outbound_for("cli")
        if message.chat_id != session_id:
            return message
        metadata = message.metadata or {}
        if metadata.get("telegram_pending_approval") or metadata.get("pending_confirmation"):
            pending = metadata.get("telegram_pending_approval") or metadata.get("pending_confirmation") or {}
            emit(
                ApprovalRequest(
                    session_id=session_id,
                    reason=str(pending.get("reason", "Approval required")),
                    token=str(pending.get("token", "")),
                    tool_name=str((pending.get("tool_call") or {}).get("name", "tool")),
                    arguments=dict((pending.get("tool_call") or {}).get("arguments", {}) or {}),
                )
            )
        if metadata.get("progress"):
            emit(LogEvent(level="DEBUG", channel="system", message=message.content))
        else:
            emit(AssistantMessage(session_id=session_id, content=message.content, metadata=metadata))
            emit(RuntimeStatus(status="IDLE", detail="Assistant response completed."))
        return message

    async def stop() -> None:
        agent.stop()
        await agent.close()
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        emit(RuntimeStatus(status="IDLE", detail="Runtime stopped."))

    return LocalRuntimeHandle(
        session_id=session_id,
        provider_name=provider_name,
        model_name=effective_model,
        send_text=send_text,
        poll_outbound=poll_outbound,
        stop=stop,
        emit_snapshot=emit_snapshot,
    )
