from __future__ import annotations

from typing import Any

from clawlet.tui.events import ApprovalRequest, AssistantMessage, BrainStateUpdate, HeartbeatSnapshot, LogEvent, RuntimeStatus, ToolLifecycle, UserSubmitted
from clawlet.tui.models import ApprovalState, BrainState, HeartbeatState, LogLine, TranscriptEntry, TuiState


class TuiStore:
    def __init__(self, workspace: str):
        self.state = TuiState(workspace=workspace)

    def reduce(self, event: Any) -> TuiState:
        if isinstance(event, UserSubmitted):
            self.state.session_id = event.session_id or self.state.session_id
            self.state.transcript.append(TranscriptEntry(kind="user", title="👤 You", body=event.content, timestamp=event.timestamp, collapsed=False))
            self.state.logs.append(LogLine(level="CHAT", channel="chat", message=event.content, timestamp=event.timestamp))
        elif isinstance(event, AssistantMessage):
            self.state.session_id = event.session_id or self.state.session_id
            self.state.transcript.append(TranscriptEntry(kind="assistant", title="🐾 Clawlet", body=event.content, timestamp=event.timestamp, metadata=event.metadata, collapsed=False))
            self.state.logs.append(LogLine(level="INFO", channel="chat", message=event.content[:160], timestamp=event.timestamp))
        elif isinstance(event, ToolLifecycle):
            title = f"🛠 TOOL CALL · {event.tool_name}"
            body = event.summary or event.tool_name
            self.state.transcript.append(
                TranscriptEntry(
                    kind="tool",
                    title=title,
                    body=body,
                    timestamp=event.timestamp,
                    status=event.status,
                    metadata={"arguments": event.arguments, "raw": event.raw},
                    collapsed=True,
                )
            )
            level = "TOOL" if event.status != "FAILED" else "ERROR"
            self.state.logs.append(LogLine(level=level, channel="system", message=f"{event.tool_name}: {event.status} - {body}", timestamp=event.timestamp))
        elif isinstance(event, ApprovalRequest):
            self.state.pending_approval = ApprovalState(reason=event.reason, token=event.token, tool_name=event.tool_name, arguments=event.arguments)
            self.state.transcript.append(
                TranscriptEntry(
                    kind="warning",
                    title="⚠ REQUIRES APPROVAL",
                    body=f"For unsafe tool call `{event.tool_name}`. Reply with confirm token `{event.token}` or use the approval popup.",
                    timestamp=event.timestamp,
                    status="REQUIRES APPROVAL",
                    metadata={"reason": event.reason, "arguments": event.arguments},
                    collapsed=False,
                )
            )
            self.state.logs.append(LogLine(level="WARNING", channel="system", message=f"Approval required for {event.tool_name}", timestamp=event.timestamp))
        elif isinstance(event, BrainStateUpdate):
            self.state.brain = BrainState(
                provider=event.provider,
                model=event.model,
                status=event.status,
                context_used_tokens=event.context_used_tokens,
                context_max_tokens=event.context_max_tokens,
                memory=event.memory,
                tools=event.tools,
            )
        elif isinstance(event, HeartbeatSnapshot):
            self.state.heartbeat = HeartbeatState(
                enabled=event.enabled,
                interval_minutes=event.interval_minutes,
                quiet_hours=event.quiet_hours,
                next_runs=event.next_runs,
                pulse_label=event.pulse_label,
                last_task=event.last_task,
                active_crons=event.active_crons,
            )
        elif isinstance(event, LogEvent):
            self.state.logs.append(LogLine(level=event.level, channel=event.channel, message=event.message, timestamp=event.timestamp))
        elif isinstance(event, RuntimeStatus):
            self.state.brain.status = event.status
            if event.detail:
                self.state.logs.append(LogLine(level="DEBUG", channel="system", message=event.detail, timestamp=event.timestamp))
        if len(self.state.logs) > 400:
            self.state.logs = self.state.logs[-400:]
        if len(self.state.transcript) > 400:
            self.state.transcript = self.state.transcript[-400:]
        return self.state
