from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    next_runs: list[str] = field(default_factory=list)
    pulse_label: str = "idle"
    last_task: str = "n/a"
    active_crons: int = 0


@dataclass(slots=True)
class LogEvent(TuiEvent):
    level: str = "INFO"
    channel: str = "system"
    message: str = ""


@dataclass(slots=True)
class RuntimeStatus(TuiEvent):
    status: str = "IDLE"
    detail: str = ""
