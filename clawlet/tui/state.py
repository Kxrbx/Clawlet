from __future__ import annotations

from typing import Any

from clawlet.tui.events import (
    ActivityStep,
    ApprovalRequest,
    AssistantDelta,
    AssistantMessage,
    BrainStateUpdate,
    HeartbeatSnapshot,
    RuntimeStatus,
    ToolLifecycle,
    UsageUpdate,
    UserSubmitted,
)
from clawlet.tui.models import (
    ApprovalState,
    AssistantDraft,
    BrainState,
    HeartbeatState,
    TraceStep,
    TranscriptEntry,
    TuiState,
)

# Ephemeral draft cap: protect the UI from a runaway stream without hiding
# that the model is still writing.
MAX_DRAFT_CHARS = 20_000
MAX_TRACE_STEPS = 30


# Progress event types that surface in the thinking trace.
_TRACE_EVENT_TYPES = {
    "started",
    "provider_started",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "finalizing",
}


def _trace_status(event_type: str) -> str:
    """Presentation-only: derive the trace row status glyph from event_type.

    Kept out of models.py because it is purely a rendering concern.
    """
    if event_type == "tool_completed":
        return "DONE"
    if event_type == "tool_failed":
        return "FAILED"
    return "RUNNING"


class TuiStore:
    def __init__(self, workspace: str):
        self.state = TuiState(workspace=workspace)
        # Highest streaming-call sequence seen so far. Deltas from superseded
        # calls (seq <= this) are dropped even when they arrive late, because
        # agent events (emit) and bus messages (poll) are not strictly ordered.
        self._last_stream_seq = 0

    @staticmethod
    def _is_repeat(transcript: list, kind: str, title: str, body: str) -> bool:
        return (
            bool(transcript)
            and transcript[-1].kind == kind
            and transcript[-1].title == title
            and transcript[-1].body == body
        )

    def _reset_turn_activity(self) -> None:
        """New user turn: drop the ephemeral draft and any old trace steps."""
        self.state.draft = None
        self.state.thinking_steps = []
        self.state.thinking_started_at = None
        self.state.thinking_done_at = None

    def _drop_draft(self) -> None:
        self.state.draft = None

    @staticmethod
    def _trace_status(event_type: str) -> str:
        if event_type == "tool_completed":
            return "DONE"
        if event_type == "tool_failed":
            return "FAILED"
        return "RUNNING"

    def _reduce_activity_step(self, event: ActivityStep) -> None:
        steps = self.state.thinking_steps
        if steps and steps[-1].event_type == event.event_type and steps[-1].text == event.text:
            return  # consecutive identical progress echoes, keep one row
        if self.state.thinking_started_at is None:
            self.state.thinking_started_at = event.timestamp
        if len(steps) >= MAX_TRACE_STEPS:
            steps.pop(0)
        steps.append(
            TraceStep(
                event_type=event.event_type,
                text=event.text,
                detail=event.detail,
            )
        )
        # A new provider pass means the previous streamed text did not become
        # the answer; clear the draft so stale text never lingers.
        if event.event_type in {"started", "provider_started"}:
            self._drop_draft()

    def _reduce_assistant_delta(self, event: AssistantDelta) -> None:
        draft = self.state.draft
        if draft is not None and event.seq == draft.seq:
            if event.text:
                draft.text = (draft.text + event.text)[-MAX_DRAFT_CHARS:]
            return
        if event.seq > self._last_stream_seq:
            # A brand-new streaming call: supersedes any previous draft.
            self._last_stream_seq = event.seq
            self.state.draft = AssistantDraft(
                seq=event.seq,
                text=event.text,
            )

    def reduce(self, event: Any) -> TuiState:
        if isinstance(event, UserSubmitted):
            self.state.session_id = event.session_id or self.state.session_id
            self._reset_turn_activity()
            if not self._is_repeat(self.state.transcript, "user", "👤 You", event.content):
                self.state.transcript.append(TranscriptEntry(kind="user", title="👤 You", body=event.content, timestamp=event.timestamp, collapsed=False))
        elif isinstance(event, ActivityStep):
            self._reduce_activity_step(event)
        elif isinstance(event, AssistantDelta):
            self._reduce_assistant_delta(event)
        elif isinstance(event, AssistantMessage):
            self.state.session_id = event.session_id or self.state.session_id
            self._drop_draft()
            self.state.thinking_done_at = event.timestamp
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
            # Any tool execution means the streamed text before it was not the
            # final answer — drop the draft so it can never be misread as one.
            self._drop_draft()
        elif isinstance(event, ApprovalRequest):
            self.state.pending_approval = ApprovalState(reason=event.reason, token=event.token, tool_name=event.tool_name, arguments=event.arguments)
            self._drop_draft()
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
        elif isinstance(event, UsageUpdate):
            # Merge only the usage numbers; never clobber the snapshot fields.
            self.state.brain.context_used_tokens = event.context_used_tokens
            self.state.brain.context_max_tokens = event.context_max_tokens or self.state.brain.context_max_tokens
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
                pulse_label=event.pulse_label,
                last_task=event.last_task,
                active_crons=event.active_crons,
                tasks=event.tasks,
            )
        elif isinstance(event, RuntimeStatus):
            self.state.brain.status = event.status
            if event.status == "IDLE":
                self._drop_draft()
                # A turn ended without a final message (approval blocked,
                # error before publish): the thinking is over regardless.
                if self.state.thinking_steps and self.state.thinking_done_at is None:
                    self.state.thinking_done_at = event.timestamp
        if len(self.state.transcript) > 400:
            self.state.transcript = self.state.transcript[-400:]
        return self.state