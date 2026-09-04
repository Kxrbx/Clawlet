from __future__ import annotations

from typing import Any

from clawlet.tui.events import ApprovalRequest, AssistantMessage, BrainStateUpdate, HeartbeatSnapshot, RuntimeStatus, ToolLifecycle, UserSubmitted
from clawlet.tui.models import ApprovalState, BrainState, HeartbeatState, TranscriptEntry, TuiState


class TuiStore:
    def __init__(self, workspace: str):
        self.state = TuiState(workspace=workspace)

    @staticmethod
    def _is_repeat(transcript: list, kind: str, title: str, body: str) -> bool:
        return (
            bool(transcript)
            and transcript[-1].kind == kind
            and transcript[-1].title == title
            and transcript[-1].body == body
        )

    def reduce(self, event: Any) -> TuiState:
        if isinstance(event, UserSubmitted):
            self.state.session_id = event.session_id or self.state.session_id
            if not self._is_repeat(self.state.transcript, "user", "👤 You", event.content):
                self.state.transcript.append(TranscriptEntry(kind="user", title="👤 You", body=event.content, timestamp=event.timestamp, collapsed=False))
        elif isinstance(event, AssistantMessage):
            self.state.session_id = event.session_id or self.state.session_id
            if not self._is_repeat(self.state.transcript, "assistant", "🐾 Clawlet", event.content):
                self.state.transcript.append(TranscriptEntry(kind="assistant", title="🐾 Clawlet", body=event.content, timestamp=event.timestamp, metadata=event.metadata, collapsed=False))
        elif isinstance(event, ToolLifecycle):
            title = f"🛠 TOOL CALL · {event.tool_name}"
            body = event.summary or event.tool_name
            last = self.state.transcript[-1] if self.state.transcript else None
            if (
                last is not None
                and last.kind == "tool"
                and last.title == title
                and (event.status == last.status or last.status == "RUNNING")
            ):
                # ponytail: replace (not mutate) so the panel re-mounts the new phase
                self.state.transcript[-1] = TranscriptEntry(
                    kind="tool",
                    title=title,
                    body=body,
                    timestamp=event.timestamp,
                    status=event.status,
                    metadata={"arguments": event.arguments, "raw": event.raw},
                    collapsed=True,
                )
            else:
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
        elif isinstance(event, RuntimeStatus):
            self.state.brain.status = event.status
        if len(self.state.transcript) > 400:
            self.state.transcript = self.state.transcript[-400:]
        return self.state
