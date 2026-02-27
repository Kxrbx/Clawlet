"""Structured runtime events and append-only event store."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

EVENT_RUN_STARTED = "RunStarted"
EVENT_TOOL_REQUESTED = "ToolRequested"
EVENT_TOOL_STARTED = "ToolStarted"
EVENT_TOOL_COMPLETED = "ToolCompleted"
EVENT_TOOL_FAILED = "ToolFailed"
EVENT_PROVIDER_FAILED = "ProviderFailed"
EVENT_STORAGE_FAILED = "StorageFailed"
EVENT_CHANNEL_FAILED = "ChannelFailed"
EVENT_RUN_COMPLETED = "RunCompleted"


@dataclass(slots=True)
class RuntimeEvent:
    """Runtime event envelope persisted to replay log."""

    event_type: str
    run_id: str
    session_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeEvent":
        return cls(
            event_type=data.get("event_type", ""),
            run_id=data.get("run_id", ""),
            session_id=data.get("session_id", ""),
            timestamp=data.get("timestamp", ""),
            payload=data.get("payload") or {},
        )


class RuntimeEventStore:
    """Append-only jsonl event log for replay and diagnostics."""

    def __init__(self, log_path: Path, redact_tool_output: bool = False):
        self.log_path = log_path
        self.redact_tool_output = redact_tool_output
        self._lock = threading.Lock()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: RuntimeEvent) -> None:
        """Append an event record."""
        line = json.dumps(self._normalize_event(event), ensure_ascii=True, sort_keys=True)
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def iter_events(self, run_id: Optional[str] = None, limit: Optional[int] = None) -> list[RuntimeEvent]:
        """Read and filter persisted events."""
        if not self.log_path.exists():
            return []

        items: list[RuntimeEvent] = []
        with self.log_path.open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                ev = RuntimeEvent.from_dict(data)
                if run_id and ev.run_id != run_id:
                    continue
                items.append(ev)

        if limit is not None:
            return items[-limit:]
        return items

    def get_run_signature(self, run_id: str) -> str:
        """Return deterministic hash for a run event stream."""
        events = [e.to_dict() for e in self.iter_events(run_id=run_id)]
        canon = json.dumps(events, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def _normalize_event(self, event: RuntimeEvent) -> dict[str, Any]:
        data = event.to_dict()
        payload = dict(data.get("payload") or {})
        if self.redact_tool_output:
            for key in ("output", "stdout", "stderr"):
                if key in payload:
                    payload[key] = "[redacted]"
        data["payload"] = _to_jsonable(payload)
        return data


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    return str(value)
