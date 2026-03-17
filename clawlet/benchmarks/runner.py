"""Local benchmark runner for runtime latency and reliability gates."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from clawlet.config import BenchmarkGatesSettings
from clawlet.benchmarks.async_utils import run_async as _run_async
from clawlet.benchmarks.determinism import run_determinism_trials
from clawlet.benchmarks.stats_utils import percentile
from clawlet.runtime import build_runtime_services


@dataclass(slots=True)
class BenchmarkSummary:
    samples: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    success_rate: float
    deterministic_replay_pass_rate_pct: float

    def to_dict(self) -> dict:
        return {
            "samples": self.samples,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "success_rate": self.success_rate,
            "deterministic_replay_pass_rate_pct": self.deterministic_replay_pass_rate_pct,
        }


def run_local_runtime_benchmark(workspace: Path, iterations: int = 25) -> BenchmarkSummary:
    """Run a deterministic local benchmark over a coding-task micro-suite."""
    registry = build_runtime_services(workspace).tools
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
    determinism_pass_rate = run_determinism_trials(workspace, trials=max(5, min(50, iterations)))
    return BenchmarkSummary(
        samples=len(latencies),
        p50_ms=percentile(ordered, 50),
        p95_ms=percentile(ordered, 95),
        p99_ms=percentile(ordered, 99),
        success_rate=(successes / max(1, len(latencies))) * 100.0,
        deterministic_replay_pass_rate_pct=determinism_pass_rate,
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
    if summary.deterministic_replay_pass_rate_pct < gates.min_deterministic_replay_pass_rate_pct:
        failures.append(
            "deterministic replay pass rate "
            f"{summary.deterministic_replay_pass_rate_pct:.2f}% below gate "
            f"{gates.min_deterministic_replay_pass_rate_pct:.2f}%"
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

