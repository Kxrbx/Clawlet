"""Runtime event payload contract and lightweight validators."""

from __future__ import annotations

from typing import Any

from clawlet.runtime.events import (
    EVENT_CHANNEL_FAILED,
    EVENT_PROVIDER_FAILED,
    EVENT_RUN_COMPLETED,
    EVENT_RUN_STARTED,
    EVENT_STORAGE_FAILED,
    EVENT_TOOL_COMPLETED,
    EVENT_TOOL_FAILED,
    EVENT_TOOL_REQUESTED,
    EVENT_TOOL_STARTED,
    RuntimeEvent,
)

# Required payload fields for each event type.
EVENT_REQUIRED_PAYLOAD_FIELDS: dict[str, tuple[str, ...]] = {
    EVENT_RUN_STARTED: ("channel", "chat_id", "engine", "engine_resolved"),
    EVENT_TOOL_REQUESTED: ("tool_call_id", "tool_name", "arguments", "execution_mode"),
    EVENT_TOOL_STARTED: ("tool_call_id", "tool_name"),
    EVENT_TOOL_COMPLETED: ("tool_call_id", "tool_name", "success"),
    EVENT_TOOL_FAILED: ("tool_call_id", "tool_name", "error", "failure_code", "retryable", "failure_category"),
    EVENT_PROVIDER_FAILED: ("provider", "attempt", "error", "failure_code", "retryable", "failure_category"),
    EVENT_STORAGE_FAILED: ("role", "backend", "error"),
    EVENT_CHANNEL_FAILED: ("channel", "chat_id", "error"),
    EVENT_RUN_COMPLETED: ("iterations", "is_error"),
}


def validate_event_payload(event_type: str, payload: dict[str, Any]) -> list[str]:
    """Return contract violations for one event payload."""
    errors: list[str] = []
    required = EVENT_REQUIRED_PAYLOAD_FIELDS.get(event_type)
    if required is None:
        return [f"unknown event_type: {event_type}"]

    for key in required:
        if key not in payload:
            errors.append(f"missing payload field '{key}'")

    if event_type == EVENT_TOOL_REQUESTED and "arguments" in payload and not isinstance(payload["arguments"], dict):
        errors.append("payload.arguments must be an object")

    if (
        event_type in (EVENT_TOOL_FAILED, EVENT_PROVIDER_FAILED)
        and "retryable" in payload
        and not isinstance(payload["retryable"], bool)
    ):
        errors.append("payload.retryable must be a boolean")

    if event_type in (EVENT_RUN_COMPLETED,) and "is_error" in payload and not isinstance(payload["is_error"], bool):
        errors.append("payload.is_error must be a boolean")

    return errors


def validate_runtime_event(event: RuntimeEvent) -> list[str]:
    """Return contract violations for a runtime event envelope."""
    errors: list[str] = []

    if not event.event_type:
        errors.append("event_type is required")
    if not event.run_id:
        errors.append("run_id is required")
    if not event.session_id:
        errors.append("session_id is required")
    if not isinstance(event.payload, dict):
        errors.append("payload must be an object")
        return errors

    errors.extend(validate_event_payload(event.event_type, event.payload))
    return errors
