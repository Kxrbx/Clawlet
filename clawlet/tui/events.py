from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class TuiEvent:
    timestamp: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class UserSubmitted(TuiEvent):
    session_id: str = ""
    content: str = ""


@dataclass(slots=True)
class AssistantMessage(TuiEvent):
    session_id: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActivityStep(TuiEvent):
    """One observable agent step (thinking, tool, finalizing) for the trace.

    These are the sanitized progress summaries the agent already publishes
    (started / provider_started / tool_started / tool_completed / tool_failed /
    finalizing) — never raw chain-of-thought.
    """

    event_type: str = ""
    text: str = ""
    detail: str = ""


@dataclass(slots=True)
class AssistantDelta(TuiEvent):
    """A chunk of the in-flight assistant answer.

    ``seq`` is the monotonic streaming-call id: deltas from a superseded call
    (e.g. a tool-pass response whose narration was discarded) arrive late and
    are dropped by the store. Discard/commit are inferred from other events
    (tool activity, a new provider pass, the canonical message) — the draft
    bubble never outlives the response it came from.
    """

    text: str = ""
    seq: int = 0


@dataclass(slots=True)
class ToolLifecycle(TuiEvent):
    session_id: str = ""
    tool_name: str = ""
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED", "REQUIRES APPROVAL"] = "PENDING"
    summary: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ApprovalRequest(TuiEvent):
    session_id: str = ""
    reason: str = ""
    token: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UsageUpdate(TuiEvent):
    """Provider-reported context usage after a turn."""

    context_used_tokens: int = 0
    context_max_tokens: int = 128000


@dataclass(slots=True)
class BrainStateUpdate(TuiEvent):
    session_id: str = ""
    provider: str = ""
    model: str = ""
    context_used_tokens: int = 0
    context_max_tokens: int = 0
    memory: list[tuple[str, str]] = field(default_factory=list)
    tools: list[tuple[str, str]] = field(default_factory=list)
    status: str = "IDLE"


@dataclass(slots=True)
class HeartbeatSnapshot(TuiEvent):
    enabled: bool = False
    interval_minutes: int = 0
    quiet_hours: str = "Disabled"
    pulse_label: str = "idle"
    last_task: str = "n/a"
    active_crons: int = 0
    # Task rows: (label, meta, status) — scheduled / paused / idle
    tasks: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass(slots=True)
class LogEvent(TuiEvent):
    level: str = "INFO"
    channel: str = "system"
    message: str = ""


@dataclass(slots=True)
class RuntimeStatus(TuiEvent):
    status: str = "IDLE"
    detail: str = ""
