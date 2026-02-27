"""Failure taxonomy gate checks for CI release hardening."""

from __future__ import annotations

import asyncio
from pathlib import Path

from clawlet.runtime import (
    DeterministicToolRuntime,
    RuntimeEventStore,
    RuntimePolicyEngine,
    ToolCallEnvelope,
)
from clawlet.runtime.failures import is_known_failure_code
from clawlet.tools.registry import BaseTool, ToolRegistry, ToolResult


class _FailingTool(BaseTool):
    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "Synthetic failing tool for taxonomy gate"

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=False, output="", error="network connection reset")


def run_failure_taxonomy_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    path = workdir / "failure-taxonomy-events.jsonl"
    if path.exists():
        path.unlink()

    registry = ToolRegistry()
    registry.register(_FailingTool())
    store = RuntimeEventStore(path)
    policy = RuntimePolicyEngine(allowed_modes=("read_only", "workspace_write", "elevated"))
    runtime = DeterministicToolRuntime(registry=registry, event_store=store, policy=policy)

    envelope = ToolCallEnvelope(
        run_id="taxonomy-gate-run",
        session_id="s1",
        tool_call_id="tc1",
        tool_name="failing_tool",
        arguments={},
        execution_mode="workspace_write",
    )
    asyncio.run(runtime.execute(envelope))

    events = store.iter_events(run_id="taxonomy-gate-run")
    failed_events = [e for e in events if e.event_type == "ToolFailed"]
    if not failed_events:
        errors.append("No ToolFailed event generated")
        return False, errors

    payload = failed_events[-1].payload or {}
    code = payload.get("failure_code")
    retryable = payload.get("retryable")
    category = payload.get("failure_category")

    if not is_known_failure_code(str(code)):
        errors.append(f"Unknown failure_code: {code}")
    if not isinstance(retryable, bool):
        errors.append("retryable is missing or not boolean")
    if not category:
        errors.append("failure_category missing")

    return len(errors) == 0, errors
