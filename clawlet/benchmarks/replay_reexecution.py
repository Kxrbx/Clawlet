"""Replay reexecution smokecheck for deterministic parity gates."""

from __future__ import annotations

from pathlib import Path

from clawlet.runtime import RuntimeEvent, RuntimeEventStore, reexecute_run
from clawlet.tools.registry import BaseTool, ToolRegistry, ToolResult


class _EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo_tool"

    @property
    def description(self) -> str:
        return "Synthetic deterministic echo tool"

    async def execute(self, value: str = "", **kwargs) -> ToolResult:
        return ToolResult(success=True, output=value)


def run_replay_reexecution_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    path = workdir / "replay-reexecution-events.jsonl"
    if path.exists():
        path.unlink()

    run_id = "reexec-smoke-run"
    store = RuntimeEventStore(path)
    store.append(RuntimeEvent(event_type="RunStarted", run_id=run_id, session_id="s1", payload={}))
    store.append(
        RuntimeEvent(
            event_type="ToolRequested",
            run_id=run_id,
            session_id="s1",
            payload={
                "tool_call_id": "tc1",
                "tool_name": "echo_tool",
                "arguments": {"value": "hello"},
                "execution_mode": "read_only",
            },
        )
    )
    store.append(
        RuntimeEvent(
            event_type="ToolCompleted",
            run_id=run_id,
            session_id="s1",
            payload={"tool_call_id": "tc1", "tool_name": "echo_tool", "output": "hello"},
        )
    )
    store.append(RuntimeEvent(event_type="RunCompleted", run_id=run_id, session_id="s1", payload={"is_error": False}))

    registry = ToolRegistry()
    registry.register(_EchoTool())

    report = reexecute_run(store, run_id, registry, allow_write=False)
    if report.mismatched > 0:
        errors.append(f"Replay reexecution mismatches={report.mismatched}")
    if report.matched != 1:
        errors.append(f"Expected exactly 1 matched replay tool call, got {report.matched}")

    return len(errors) == 0, errors
