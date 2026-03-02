"""Lane scheduling benchmark and smokechecks."""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from clawlet.runtime import DeterministicToolRuntime, RuntimeEventStore, RuntimePolicyEngine, ToolCallEnvelope
from clawlet.tools.registry import BaseTool, ToolRegistry, ToolResult


class _SlowTool(BaseTool):
    @property
    def name(self) -> str:
        return "lane_slow_tool"

    @property
    def description(self) -> str:
        return "Sleeps for lane scheduling checks"

    async def execute(self, seconds: float = 0.15, **kwargs) -> ToolResult:
        await asyncio.sleep(max(0.01, float(seconds)))
        return ToolResult(success=True, output="ok")


@dataclass(slots=True)
class LaneContentionReport:
    passed: bool
    serial_elapsed_ms: float
    parallel_elapsed_ms: float
    speedup_ratio: float
    details: list[str]


def run_lane_contention_benchmark(workdir: Path, seconds: float = 0.15) -> LaneContentionReport:
    events = workdir / "lane-contention-events.jsonl"
    registry = ToolRegistry()
    registry.register(_SlowTool())
    runtime = DeterministicToolRuntime(
        registry=registry,
        event_store=RuntimeEventStore(events),
        policy=RuntimePolicyEngine(allowed_modes=("read_only", "workspace_write", "elevated")),
        enable_idempotency=False,
    )

    serial_ms = _run_pair(
        runtime,
        mode="workspace_write",
        lane="serial:workspace_write",
        seconds=seconds,
        run_id="lane-serial",
    )
    parallel_ms = _run_pair(
        runtime,
        mode="read_only",
        lane="parallel:read_only",
        seconds=seconds,
        run_id="lane-parallel",
    )

    ratio = serial_ms / max(1.0, parallel_ms)
    details: list[str] = []
    passed = serial_ms > parallel_ms and ratio >= 1.40
    if not passed:
        details.append(
            "lane scheduling did not show expected serialization/parallelization gap "
            f"(serial={serial_ms:.1f}ms parallel={parallel_ms:.1f}ms ratio={ratio:.2f})"
        )

    return LaneContentionReport(
        passed=passed,
        serial_elapsed_ms=serial_ms,
        parallel_elapsed_ms=parallel_ms,
        speedup_ratio=ratio,
        details=details,
    )


def run_lane_contention_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    report = run_lane_contention_benchmark(workdir)
    return report.passed, list(report.details)


def write_lane_contention_report(path: Path, report: LaneContentionReport) -> None:
    import json

    payload = {"report": asdict(report)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _run_pair(runtime: DeterministicToolRuntime, mode: str, lane: str, seconds: float, run_id: str) -> float:
    env1 = ToolCallEnvelope(
        run_id=run_id,
        session_id="lane",
        tool_call_id=f"{run_id}-1",
        tool_name="lane_slow_tool",
        arguments={"seconds": seconds},
        execution_mode=mode,  # type: ignore[arg-type]
        lane=lane,
    )
    env2 = ToolCallEnvelope(
        run_id=run_id,
        session_id="lane",
        tool_call_id=f"{run_id}-2",
        tool_name="lane_slow_tool",
        arguments={"seconds": seconds},
        execution_mode=mode,  # type: ignore[arg-type]
        lane=lane,
    )

    start = time.perf_counter()
    _run_async(asyncio.gather(runtime.execute(env1), runtime.execute(env2)))
    return (time.perf_counter() - start) * 1000.0


def _run_async(coro):
    import asyncio
    from concurrent.futures import Future
    import threading

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        future: Future = Future()

        def _runner():
            try:
                future.set_result(asyncio.run(coro))
            except Exception as e:
                future.set_exception(e)

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        return future.result()

    return asyncio.run(coro)
