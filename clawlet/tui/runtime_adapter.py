from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from types import MethodType
from typing import Any

from clawlet.bus.queue import InboundMessage, OutboundMessage
from clawlet.cli.runtime_ui import _build_effective_heartbeat_context, _create_provider
from clawlet.tui.events import (
    ActivityStep,
    ApprovalRequest,
    AssistantDelta,
    AssistantMessage,
    BrainStateUpdate,
    HeartbeatSnapshot,
    LogEvent,
    RuntimeStatus,
    ToolLifecycle,
    UsageUpdate,
)
from clawlet.workspace_layout import get_workspace_layout

EventSink = Callable[[object], None]


def _forward_stream_delta(emit: EventSink, chunk: str, seq: int) -> None:
    """Forward a streamed token from the agent loop straight to the store.

    Synchronous same-loop emit: deltas reduce in call order ahead of the
    final assistant message, with no bus round-trip, no per-chunk task and
    no rate-limiter exposure. Superseded calls are still fenced by `seq`
    in the store.
    """
    if chunk:
        emit(AssistantDelta(text=chunk, seq=seq))

# Progress event types that surface in the thinking trace. `tool_failed` and
# `approval_required` additionally produce a ToolLifecycle row (richer than the
# registry path, which never fires for pre-execution rejections).
_TRACE_EVENT_TYPES = {
    "started",
    "provider_started",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "finalizing",
}


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
    get_raw_history: Callable[[], list[dict[str, Any]]] = list  # ponytail: in-memory read, storage query if richer view needed


def _heartbeat_task_rows(workspace: Path, config) -> list[tuple[str, str, str]]:
    """Real scheduled-task rows for the heartbeat panel — no fabricated times.

    Prefers the actual scheduler (next-run datetimes from config/jobs/state);
    falls back to the heartbeat markdown task lines annotated with the real
    interval when no scheduler is configured.
    """
    try:
        # Reuse the CLI's scheduler builder rather than re-wiring settings here.
        from clawlet.cli.cron_ui import _build_scheduler

        rows: list[tuple[str, str, str]] = []
        for task_id, next_run in _build_scheduler(workspace).get_next_runs(5):
            meta = next_run.strftime("%H:%M UTC") if next_run.tzinfo else next_run.strftime("%H:%M")
            rows.append((task_id[:44], meta, "scheduled"))
        if rows:
            return rows
    except Exception:
        # Best-effort panel: missing tz database (Windows without tzdata),
        # unreadable state, etc. all mean "no scheduler rows" for the UI.
        pass

    # Fallback: heartbeat.md task lines with the real interval as metadata.
    hb_cfg = getattr(config, "heartbeat", None)
    interval = int(getattr(hb_cfg, "interval_minutes", 0) or 0)
    enabled = bool(getattr(hb_cfg, "enabled", False))
    meta = f"every {interval}m" if interval > 0 else "manual"
    status = "scheduled" if enabled else "paused"
    rows: list[tuple[str, str, str]] = []
    layout = get_workspace_layout(workspace)
    try:
        heartbeat_raw = layout.heartbeat_path.read_text(encoding="utf-8")
        heartbeat_text = _build_effective_heartbeat_context(
            f"## Periodic Tasks\n\n{heartbeat_raw}", hb_cfg
        ) or "comment-only"
    except FileNotFoundError:
        heartbeat_text = "comment-only"
    for line in heartbeat_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("<!--"):
            rows.append((stripped[:44], meta, status))
        if len(rows) >= 5:
            break
    if not rows:
        rows = [("No scheduled heartbeat tasks", "", "idle")]
    return rows


async def create_local_runtime(workspace: Path, model: str | None, emit: EventSink, session_id: str = "local") -> LocalRuntimeHandle:
    from clawlet.agent.identity import IdentityLoader
    from clawlet.agent.loop import AgentLoop
    from clawlet.bus.queue import MessageBus
    from clawlet.config import load_config
    from clawlet.runtime import build_runtime_services

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
        # ponytail: tool_started/completed already covered (richer) by
        # InstrumentedToolRegistry; tool_failed/approval_required have no
        # registry emit, so they become ToolLifecycle rows.
        if event_type in {"tool_failed", "approval_required"}:
            status = "FAILED" if event_type == "tool_failed" else "REQUIRES APPROVAL"
            emit(
                ToolLifecycle(
                    session_id=session_id,
                    tool_name=detail or "tool",
                    status=status,
                    summary=text.strip(),
                    raw={"detail": detail, "final": final},
                )
            )
        elif event_type in _TRACE_EVENT_TYPES:
            emit(ActivityStep(event_type=event_type, text=text.strip(), detail=detail.strip()))
        else:
            emit(LogEvent(level="DEBUG", channel="system", message=f"{event_type}: {text.strip()}"))

    agent._publish_progress_update = MethodType(_progress_override, agent)

    agent.set_stream_callback(lambda chunk, seq: _forward_stream_delta(emit, chunk, seq))

    def _on_usage(cumulative: int) -> None:
        emit(UsageUpdate(context_used_tokens=cumulative))

    agent.set_usage_callback(_on_usage)

    agent_task = asyncio.create_task(agent.run())
    emit(RuntimeStatus(status="IDLE", detail="Runtime booted."))

    def get_raw_history() -> list[dict[str, Any]]:
        key = f"cli:{session_id}"
        convo = getattr(agent, "_conversations", {}).get(key)
        history = getattr(convo, "history", None) if convo is not None else None
        if not history:
            return []
        entries: list[dict[str, Any]] = []
        for message in history:
            entries.append(
                {
                    "role": getattr(message, "role", "?"),
                    "content": getattr(message, "content", ""),
                    "tool_calls": getattr(message, "tool_calls", None),
                }
            )
        return entries

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
                context_used_tokens=getattr(agent, "_context_used_tokens", 0),
                context_max_tokens=128000,
                memory=memory,
                tools=tools,
                status="IDLE",
            )
        )
        hb_cfg = config.heartbeat
        quiet = "Disabled" if int(getattr(hb_cfg, "quiet_hours_start", 0) or 0) == int(getattr(hb_cfg, "quiet_hours_end", 0) or 0) else f"{hb_cfg.quiet_hours_start}:00-{hb_cfg.quiet_hours_end}:00 UTC"
        tasks = _heartbeat_task_rows(workspace, config)
        emit(
            HeartbeatSnapshot(
                enabled=bool(getattr(hb_cfg, "enabled", False)),
                interval_minutes=int(getattr(hb_cfg, "interval_minutes", 0) or 0),
                quiet_hours=quiet,
                pulse_label=f"{int(getattr(hb_cfg, 'interval_minutes', 0) or 0)}m pulse",
                last_task="Awaiting first run",
                active_crons=len(tasks),
                tasks=tasks,
            )
        )

    async def send_text(text: str) -> None:
        emit(RuntimeStatus(status="RUNNING", detail="Processing user message."))
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
        get_raw_history=get_raw_history,
    )