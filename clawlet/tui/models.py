from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


@dataclass(slots=True)
class TranscriptEntry:
    kind: Literal["user", "assistant", "tool", "warning", "system"]
    title: str
    body: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    collapsed: bool = True


@dataclass(slots=True)
class TraceStep:
    """One observable agent step in the thinking trace (sanitized progress).

    Status is presentation, not state: the trace widget derives it from
    event_type so the store keeps only the source-of-truth field.
    """

    event_type: str
    text: str
    detail: str = ""


@dataclass(slots=True)
class AssistantDraft:
    """In-flight streamed answer the model is currently generating.

    Ephemeral: shown as a "drafting…" bubble, never committed to the
    transcript. Cleared when the canonical AssistantMessage lands or the
    response is discarded (tool pass / suppressed narration).
    """

    seq: int = 0
    text: str = ""


@dataclass(slots=True)
class ApprovalState:
    reason: str
    token: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrainState:
    provider: str = ""
    model: str = ""
    status: str = "IDLE"
    context_used_tokens: int = 0
    context_max_tokens: int = 128000
    memory: list[tuple[str, str]] = field(default_factory=list)
    tools: list[tuple[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class HeartbeatState:
    enabled: bool = False
    interval_minutes: int = 0
    quiet_hours: str = "Disabled"
    pulse_label: str = "idle"
    last_task: str = "n/a"
    active_crons: int = 0
    # Task rows: (label, meta, status) — scheduled / paused / idle
    tasks: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass(slots=True)
class TuiState:
    workspace: str
    session_id: str = "local"
    transcript: list[TranscriptEntry] = field(default_factory=list)
    brain: BrainState = field(default_factory=BrainState)
    heartbeat: HeartbeatState = field(default_factory=HeartbeatState)
    pending_approval: ApprovalState | None = None
    # Agent activity layers (Beautiful UI: thinking trace + streaming draft)
    thinking_steps: list[TraceStep] = field(default_factory=list)
    thinking_started_at: datetime | None = None
    thinking_done_at: datetime | None = None
    draft: AssistantDraft | None = None
