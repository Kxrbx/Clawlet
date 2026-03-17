"""Coding-loop benchmark for inspect -> patch -> verify -> summarize workflow."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from clawlet.benchmarks.async_utils import run_async as _run_async
from clawlet.benchmarks.stats_utils import mean, percentile
from clawlet.runtime import build_runtime_services


@dataclass(slots=True)
class CodingLoopBenchmarkReport:
    passed: bool
    iterations: int
    success_rate: float
    p95_total_ms: float
    avg_inspect_ms: float
    avg_patch_ms: float
    avg_verify_ms: float
    avg_summarize_ms: float
    details: list[str]


def run_coding_loop_benchmark(workspace: Path, iterations: int = 10) -> CodingLoopBenchmarkReport:
    workspace = workspace.resolve()
    iterations = max(1, int(iterations))
    registry = build_runtime_services(workspace).tools
    list_tool = registry.get("list_dir")
    read_tool = registry.get("read_file")
    edit_tool = registry.get("edit_file")
    if list_tool is None or read_tool is None or edit_tool is None:
        raise RuntimeError("list_dir/read_file/edit_file tools are required for coding-loop benchmark")

    totals: list[float] = []
    inspect_ms: list[float] = []
    patch_ms: list[float] = []
    verify_ms: list[float] = []
    summarize_ms: list[float] = []
    successes = 0
    details: list[str] = []

    for i in range(iterations):
        target = workspace / f".benchmark-coding-loop-{i}.py"
        target.write_text(f"def value():\n    return {i}\n", encoding="utf-8")

        started_total = time.perf_counter()

        t0 = time.perf_counter()
        r_list = _run_async(list_tool.execute(path="."))
        r_read_before = _run_async(read_tool.execute(path=target.name))
        inspect_ms.append((time.perf_counter() - t0) * 1000.0)

        t1 = time.perf_counter()
        r_patch = _run_async(
            edit_tool.execute(
                path=target.name,
                old_text=f"return {i}",
                new_text=f"return {i + 1}",
            )
        )
        patch_ms.append((time.perf_counter() - t1) * 1000.0)

        t2 = time.perf_counter()
        r_read_after = _run_async(read_tool.execute(path=target.name))
        verify_ok = r_read_after.success and f"return {i + 1}" in (r_read_after.output or "")
        verify_ms.append((time.perf_counter() - t2) * 1000.0)

        t3 = time.perf_counter()
        summary = (
            f"file={target.name} inspect_ok={r_list.success and r_read_before.success} "
            f"patch_ok={r_patch.success} verify_ok={verify_ok}"
        )
        summarize_ok = bool(summary)
        summarize_ms.append((time.perf_counter() - t3) * 1000.0)

        total_elapsed = (time.perf_counter() - started_total) * 1000.0
        totals.append(total_elapsed)

        ok = r_list.success and r_read_before.success and r_patch.success and verify_ok and summarize_ok
        if ok:
            successes += 1
        else:
            details.append(f"iteration {i} failed")

    success_rate = (successes / max(1, iterations)) * 100.0
    p95_total = percentile(sorted(totals), 95)
    report = CodingLoopBenchmarkReport(
        passed=success_rate >= 99.0,
        iterations=iterations,
        success_rate=success_rate,
        p95_total_ms=p95_total,
        avg_inspect_ms=mean(inspect_ms),
        avg_patch_ms=mean(patch_ms),
        avg_verify_ms=mean(verify_ms),
        avg_summarize_ms=mean(summarize_ms),
        details=details,
    )
    return report


def run_coding_loop_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    report = run_coding_loop_benchmark(workdir, iterations=1)
    if report.iterations != 1:
        errors.append("expected iterations=1")
    if report.success_rate <= 0:
        errors.append("expected success_rate > 0")
    if report.p95_total_ms <= 0:
        errors.append("expected p95_total_ms > 0")
    return len(errors) == 0, errors


def write_coding_loop_report(path: Path, report: CodingLoopBenchmarkReport) -> None:
    payload = {"report": asdict(report)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
