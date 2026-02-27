"""Runtime event contract smokecheck for CI gates."""

from __future__ import annotations

from pathlib import Path

from clawlet.runtime import RuntimeEvent
from clawlet.runtime.schema import validate_runtime_event


def run_event_schema_smokecheck(_workdir: Path) -> tuple[bool, list[str]]:
    """Validate representative runtime events against the contract."""
    errors: list[str] = []
    run_id = "schema-smoke-run"
    session_id = "s1"

    samples = [
        RuntimeEvent(
            event_type="RunStarted",
            run_id=run_id,
            session_id=session_id,
            payload={
                "channel": "cli",
                "chat_id": "local",
                "engine": "hybrid_rust",
                "engine_resolved": "python",
            },
        ),
        RuntimeEvent(
            event_type="ToolRequested",
            run_id=run_id,
            session_id=session_id,
            payload={
                "tool_call_id": "tc1",
                "tool_name": "read_file",
                "arguments": {"path": "README.md"},
                "execution_mode": "read_only",
            },
        ),
        RuntimeEvent(
            event_type="ToolStarted",
            run_id=run_id,
            session_id=session_id,
            payload={"tool_call_id": "tc1", "tool_name": "read_file"},
        ),
        RuntimeEvent(
            event_type="ToolCompleted",
            run_id=run_id,
            session_id=session_id,
            payload={"tool_call_id": "tc1", "tool_name": "read_file", "success": True, "output": "ok"},
        ),
        RuntimeEvent(
            event_type="ToolFailed",
            run_id=run_id,
            session_id=session_id,
            payload={
                "tool_call_id": "tc2",
                "tool_name": "run_shell",
                "error": "timeout",
                "failure_code": "timeout",
                "retryable": True,
                "failure_category": "transient",
            },
        ),
        RuntimeEvent(
            event_type="ProviderFailed",
            run_id=run_id,
            session_id=session_id,
            payload={
                "provider": "openrouter",
                "attempt": 1,
                "error": "429",
                "failure_code": "provider_rate_limited",
                "retryable": True,
                "failure_category": "provider",
            },
        ),
        RuntimeEvent(
            event_type="StorageFailed",
            run_id=run_id,
            session_id=session_id,
            payload={"role": "assistant", "backend": "SQLiteStorage", "error": "disk io error"},
        ),
        RuntimeEvent(
            event_type="ChannelFailed",
            run_id=run_id,
            session_id=session_id,
            payload={"channel": "discord", "chat_id": "abc", "error": "send failed"},
        ),
        RuntimeEvent(
            event_type="RunCompleted",
            run_id=run_id,
            session_id=session_id,
            payload={"iterations": 1, "is_error": False, "response_preview": "done"},
        ),
    ]

    for idx, event in enumerate(samples):
        event_errors = validate_runtime_event(event)
        for item in event_errors:
            errors.append(f"sample[{idx}] {event.event_type}: {item}")

    return len(errors) == 0, errors
