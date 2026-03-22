"""Per-run execution context and mode profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class RunModeProfile:
    is_heartbeat: bool
    heartbeat_ack_max_chars: int
    iteration_limit: int
    tool_call_limit: int
    no_progress_limit: int
    max_wall_time_seconds: float


@dataclass(slots=True)
class RunContext:
    session_id: str
    run_id: str
    channel: str
    chat_id: str
    user_id: str = ""
    user_name: str = ""
    source: str = ""
    metadata: dict = field(default_factory=dict)
    scheduled_payload: dict | None = None
    mode: RunModeProfile | None = None
    started_at: datetime | None = None

    @property
    def is_heartbeat(self) -> bool:
        return bool(self.mode and self.mode.is_heartbeat)
