"""Local benchmark runner for runtime latency and reliability gates."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from clawlet.config import BenchmarkGatesSettings
from clawlet.tools import create_default_tool_registry


@dataclass(slots=True)
class BenchmarkSummary:
    samples: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    success_rate: float

    def to_dict(self) -> dict:
        return {
            "samples": self.samples,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "success_rate": self.success_rate,
        }


def run_local_runtime_benchmark(workspace: Path, iterations: int = 25) -> BenchmarkSummary:
    """Run a deterministic local benchmark over a coding-task micro-suite."""
    registry = create_default_tool_registry(allowed_dir=str(workspace))
    list_tool = registry.get("list_dir")
    read_tool = registry.get("read_file")
    edit_tool = registry.get("edit_file")
    if list_tool is None or read_tool is None or edit_tool is None:
        raise RuntimeError("list_dir/read_file/edit_file tools are required for local benchmark")

    latencies = []
    successes = 0
    target = workspace / ".runtime-benchmark-target.txt"

    for i in range(iterations):
        target.write_text(f"benchmark iteration {i}\n", encoding="utf-8")
        started = time.perf_counter()
        # Minimal coding loop: inspect -> read -> patch/edit -> verify.
        result_list = _run_async(list_tool.execute(path="."))
        result_read_before = _run_async(read_tool.execute(path=target.name))
        result_edit = _run_async(
            edit_tool.execute(
                path=target.name,
                old_text=f"benchmark iteration {i}",
                new_text=f"benchmark iteration {i} done",
            )
        )
        result_read_after = _run_async(read_tool.execute(path=target.name))
        elapsed = (time.perf_counter() - started) * 1000.0
        latencies.append(elapsed)
        if (
            result_list.success
            and result_read_before.success
            and result_edit.success
            and result_read_after.success
            and "done" in result_read_after.output
        ):
            successes += 1

    ordered = sorted(latencies)
    return BenchmarkSummary(
        samples=len(latencies),
        p50_ms=_percentile(ordered, 50),
        p95_ms=_percentile(ordered, 95),
        p99_ms=_percentile(ordered, 99),
        success_rate=(successes / max(1, len(latencies))) * 100.0,
    )


def check_gates(summary: BenchmarkSummary, gates: BenchmarkGatesSettings) -> list[str]:
    """Return a list of gate failures."""
    failures = []
    if summary.p95_ms > gates.max_p95_latency_ms:
        failures.append(
            f"p95 latency {summary.p95_ms:.2f}ms exceeded gate {gates.max_p95_latency_ms:.2f}ms"
        )
    if summary.success_rate < gates.min_tool_success_rate_pct:
        failures.append(
            f"success rate {summary.success_rate:.2f}% below gate {gates.min_tool_success_rate_pct:.2f}%"
        )
    return failures


def write_report(path: Path, summary: BenchmarkSummary, failures: list[str]) -> None:
    report = {
        "summary": summary.to_dict(),
        "gate_failures": failures,
        "passed": len(failures) == 0,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    rank = (pct / 100.0) * (len(values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    weight = rank - lower
    return (values[lower] * (1 - weight)) + (values[upper] * weight)


def _run_async(coro):
    import asyncio
    from concurrent.futures import Future
    import threading

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Rare path: execute in a dedicated thread to avoid nested-loop errors.
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
