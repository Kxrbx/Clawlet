from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


@dataclass(slots=True)
class TranscriptEntry:
    kind: Literal["user", "assistant", "tool", "warning", "system"]
    title: str
    body: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    collapsed: bool = True


@dataclass(slots=True)
class ApprovalState:
    reason: str
    token: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LogLine:
    level: str
    channel: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
    next_runs: list[str] = field(default_factory=list)
    pulse_label: str = "idle"
    last_task: str = "n/a"
    active_crons: int = 0


@dataclass(slots=True)
class TuiState:
    workspace: str
    session_id: str = "local"
    transcript: list[TranscriptEntry] = field(default_factory=list)
    brain: BrainState = field(default_factory=BrainState)
    heartbeat: HeartbeatState = field(default_factory=HeartbeatState)
    logs: list[LogLine] = field(default_factory=list)
    pending_approval: ApprovalState | None = None
    active_log_tab: str = "chat"
    log_filter: str = ""
