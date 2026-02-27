"""Runtime types for deterministic tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ToolExecutionMode = Literal["read_only", "workspace_write", "elevated"]


@dataclass(slots=True)
class ToolCallEnvelope:
    """Normalized envelope for tool execution."""

    run_id: str
    session_id: str
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    execution_mode: ToolExecutionMode
    workspace_path: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 0
    idempotency_key: str = ""
    requested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(slots=True)
class ToolExecutionMetadata:
    """Execution metadata emitted for observability."""

    duration_ms: float
    attempts: int
    cached: bool = False
