"""Run-level reliability reporting from runtime events."""

from __future__ import annotations

from dataclasses import dataclass

from clawlet.runtime.events import (
    EVENT_CHANNEL_FAILED,
    EVENT_PROVIDER_FAILED,
    EVENT_RUN_COMPLETED,
    EVENT_STORAGE_FAILED,
    EVENT_TOOL_COMPLETED,
    EVENT_TOOL_FAILED,
    RuntimeEventStore,
)


@dataclass(slots=True)
class ReliabilityReport:
    run_id: str
    tool_completed: int
    tool_failed: int
    provider_failed: int
    storage_failed: int
    channel_failed: int
    run_completed_error: bool
    total_failures: int
    tool_success_rate: float

    @property
    def crash_like(self) -> bool:
        return self.run_completed_error or self.channel_failed > 0


def build_reliability_report(store: RuntimeEventStore, run_id: str) -> ReliabilityReport:
    events = store.iter_events(run_id=run_id)

    tool_completed = sum(1 for e in events if e.event_type == EVENT_TOOL_COMPLETED)
    tool_failed = sum(1 for e in events if e.event_type == EVENT_TOOL_FAILED)
    provider_failed = sum(1 for e in events if e.event_type == EVENT_PROVIDER_FAILED)
    storage_failed = sum(1 for e in events if e.event_type == EVENT_STORAGE_FAILED)
    channel_failed = sum(1 for e in events if e.event_type == EVENT_CHANNEL_FAILED)

    run_completed_error = False
    for e in reversed(events):
        if e.event_type == EVENT_RUN_COMPLETED:
            run_completed_error = bool((e.payload or {}).get("is_error", False))
            break

    attempts = tool_completed + tool_failed
    tool_success_rate = (tool_completed / attempts) if attempts > 0 else 1.0
    total_failures = tool_failed + provider_failed + storage_failed + channel_failed

    return ReliabilityReport(
        run_id=run_id,
        tool_completed=tool_completed,
        tool_failed=tool_failed,
        provider_failed=provider_failed,
        storage_failed=storage_failed,
        channel_failed=channel_failed,
        run_completed_error=run_completed_error,
        total_failures=total_failures,
        tool_success_rate=tool_success_rate,
    )
