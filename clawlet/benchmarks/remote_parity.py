"""Remote/local parity smokechecks for remote-optional runtime contract."""

from __future__ import annotations

from pathlib import Path

from clawlet.benchmarks.async_utils import run_async as _run_async
from clawlet.runtime import DeterministicToolRuntime, RuntimeEventStore, RuntimePolicyEngine, ToolCallEnvelope
from clawlet.tools.registry import BaseTool, ToolRegistry, ToolResult


class _EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo_parity"

    @property
    def description(self) -> str:
        return "Echo deterministic value"

    async def execute(self, value: str = "", **kwargs) -> ToolResult:
        return ToolResult(success=True, output=value)


class _FakeRemoteExecutor:
    async def execute(self, envelope: ToolCallEnvelope) -> ToolResult:
        return ToolResult(success=True, output=str(envelope.arguments.get("value") or ""))


def run_remote_parity_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    events_local = workdir / "remote-parity-local.jsonl"
    events_remote = workdir / "remote-parity-remote.jsonl"

    registry = ToolRegistry()
    registry.register(_EchoTool())
    policy = RuntimePolicyEngine(allowed_modes=("read_only", "workspace_write", "elevated"))

    runtime_local = DeterministicToolRuntime(
        registry=registry,
        event_store=RuntimeEventStore(events_local),
        policy=policy,
    )
    runtime_remote = DeterministicToolRuntime(
        registry=registry,
        event_store=RuntimeEventStore(events_remote),
        policy=policy,
        remote_executor=_FakeRemoteExecutor(),
    )

    env_local = ToolCallEnvelope(
        run_id="remote-parity",
        session_id="s1",
        tool_call_id="tc-local",
        tool_name="echo_parity",
        arguments={"value": "hello"},
        execution_mode="read_only",
        execution_target="local",
    )
    env_remote = ToolCallEnvelope(
        run_id="remote-parity",
        session_id="s1",
        tool_call_id="tc-remote",
        tool_name="echo_parity",
        arguments={"value": "hello"},
        execution_mode="read_only",
        execution_target="remote",
    )

    local_result, _ = _run_async(runtime_local.execute(env_local))
    remote_result, _ = _run_async(runtime_remote.execute(env_remote))

    if not local_result.success:
        errors.append("local execution failed")
    if not remote_result.success:
        errors.append("remote execution failed")
    if local_result.output != remote_result.output:
        errors.append("remote/local outputs differ")

    return len(errors) == 0, errors

