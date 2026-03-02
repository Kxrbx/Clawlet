"""Release gate orchestration for benchmark + corpus + baseline comparison."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from clawlet.benchmarks.corpus import CorpusBenchmarkReport, CorpusComparisonReport


def run_local_runtime_benchmark(workspace: Path, iterations: int = 25):
    from clawlet.benchmarks.runner import run_local_runtime_benchmark as _impl

    return _impl(workspace=workspace, iterations=iterations)


def check_gates(summary: Any, gates: Any) -> list[str]:
    from clawlet.benchmarks.runner import check_gates as _impl

    return _impl(summary, gates)


def run_openclaw_matched_corpus(workspace: Path, iterations: int = 10):
    from clawlet.benchmarks.corpus import run_openclaw_matched_corpus as _impl

    return _impl(workspace=workspace, iterations=iterations)


def check_corpus_gates(report: Any, gates: Any) -> list[str]:
    from clawlet.benchmarks.corpus import check_corpus_gates as _impl

    return _impl(report, gates)


def compare_corpus_to_baseline(report: Any, baseline_path: Path, target_improvement_pct: float):
    from clawlet.benchmarks.corpus import compare_corpus_to_baseline as _impl

    return _impl(report=report, baseline_path=baseline_path, target_improvement_pct=target_improvement_pct)


def run_lane_contention_benchmark(workspace: Path):
    from clawlet.benchmarks.lanes import run_lane_contention_benchmark as _impl

    return _impl(workspace)


def run_context_cache_benchmark(workspace: Path):
    from clawlet.benchmarks.context_cache import run_context_cache_benchmark as _impl

    return _impl(workspace)


def run_coding_loop_benchmark(workspace: Path):
    from clawlet.benchmarks.coding_loop import run_coding_loop_benchmark as _impl

    return _impl(workspace, iterations=5)


@dataclass(slots=True)
class ReleaseGateReport:
    local_summary: Any
    local_failures: list[str]
    corpus_report: CorpusBenchmarkReport
    corpus_failures: list[str]
    lane_scheduling: dict[str, Any]
    context_cache: dict[str, Any]
    coding_loop: dict[str, Any]
    comparison: Optional[CorpusComparisonReport]
    target_improvement_pct: float
    require_comparison: bool
    passed: bool
    reasons: list[str] = field(default_factory=list)
    gate_breaches: list[str] = field(default_factory=list)
    breach_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "local_summary": self.local_summary.to_dict()
            if hasattr(self.local_summary, "to_dict")
            else dict(self.local_summary),
            "local_failures": list(self.local_failures),
            "corpus_report": self.corpus_report.to_dict(),
            "corpus_failures": list(self.corpus_failures),
            "lane_scheduling": dict(self.lane_scheduling),
            "context_cache": dict(self.context_cache),
            "coding_loop": dict(self.coding_loop),
            "target_improvement_pct": float(self.target_improvement_pct),
            "require_comparison": bool(self.require_comparison),
            "passed": bool(self.passed),
            "reasons": list(self.reasons),
            "gate_breaches": list(self.gate_breaches),
            "breach_counts": dict(self.breach_counts),
        }
        if self.comparison is not None:
            payload["comparison"] = self.comparison.to_dict()
        return payload


def run_release_gate(
    workspace: Path,
    gates: Any,
    *,
    local_iterations: int = 25,
    corpus_iterations: int = 10,
    baseline_report: Path | None = None,
    target_improvement_pct: float = 35.0,
    require_comparison: bool = False,
) -> ReleaseGateReport:
    """Run all benchmark release gates and return a consolidated verdict."""
    local_summary = run_local_runtime_benchmark(workspace=workspace, iterations=local_iterations)
    local_failures = check_gates(local_summary, gates)

    corpus_report = run_openclaw_matched_corpus(workspace=workspace, iterations=corpus_iterations)
    corpus_failures = check_corpus_gates(corpus_report, gates)
    lane_report = run_lane_contention_benchmark(workspace)
    context_report = run_context_cache_benchmark(workspace)
    coding_report = run_coding_loop_benchmark(workspace)

    comparison: CorpusComparisonReport | None = None
    reasons: list[str] = []
    reasons.extend([f"local: {item}" for item in local_failures])
    reasons.extend([f"corpus: {item}" for item in corpus_failures])
    if not lane_report.passed:
        details = "; ".join(lane_report.details) or "lane scheduling benchmark failed"
        reasons.append(f"lane_scheduling: {details}")
    min_lane_speedup_ratio = float(getattr(gates, "min_lane_speedup_ratio", 1.0) or 1.0)
    if float(lane_report.speedup_ratio) < min_lane_speedup_ratio:
        reasons.append(
            "lane_scheduling: "
            f"speedup ratio {lane_report.speedup_ratio:.2f}x is below gate {min_lane_speedup_ratio:.2f}x"
        )
    max_lane_parallel_elapsed_ms = float(getattr(gates, "max_lane_parallel_elapsed_ms", 1000.0) or 1000.0)
    if float(lane_report.parallel_elapsed_ms) > max_lane_parallel_elapsed_ms:
        reasons.append(
            "lane_scheduling: "
            f"parallel elapsed {lane_report.parallel_elapsed_ms:.2f}ms exceeds gate "
            f"{max_lane_parallel_elapsed_ms:.2f}ms"
        )
    if not context_report.passed:
        details = "; ".join(context_report.details) or "context cache benchmark failed"
        reasons.append(f"context_cache: {details}")
    min_context_cache_speedup_ratio = float(getattr(gates, "min_context_cache_speedup_ratio", 1.0) or 1.0)
    if float(context_report.speedup_ratio) < min_context_cache_speedup_ratio:
        reasons.append(
            "context_cache: "
            f"speedup ratio {context_report.speedup_ratio:.2f}x is below gate "
            f"{min_context_cache_speedup_ratio:.2f}x"
        )
    max_context_cache_warm_ms = float(getattr(gates, "max_context_cache_warm_ms", 1200.0) or 1200.0)
    if float(context_report.warm_ms) > max_context_cache_warm_ms:
        reasons.append(
            "context_cache: "
            f"warm latency {context_report.warm_ms:.2f}ms exceeds gate {max_context_cache_warm_ms:.2f}ms"
        )
    min_coding_loop_success_rate = float(getattr(gates, "min_coding_loop_success_rate_pct", 99.0) or 99.0)
    if float(coding_report.success_rate) < min_coding_loop_success_rate:
        reasons.append(
            "coding_loop: "
            f"success rate {coding_report.success_rate:.2f}% is below gate "
            f"{min_coding_loop_success_rate:.2f}%"
        )
    max_coding_loop_p95_total_ms = float(getattr(gates, "max_coding_loop_p95_total_ms", 2500.0) or 2500.0)
    if float(coding_report.p95_total_ms) > max_coding_loop_p95_total_ms:
        reasons.append(
            "coding_loop: "
            f"p95 total latency {coding_report.p95_total_ms:.2f}ms exceeds gate "
            f"{max_coding_loop_p95_total_ms:.2f}ms"
        )

    if baseline_report is not None:
        comparison = compare_corpus_to_baseline(
            report=corpus_report,
            baseline_path=baseline_report,
            target_improvement_pct=target_improvement_pct,
        )
        if not comparison.meets_target:
            reasons.append(
                "comparison: "
                f"improvement {comparison.improvement_pct:.2f}% is below target "
                f"{comparison.target_improvement_pct:.2f}% or regressions exist"
            )
    elif require_comparison:
        reasons.append("comparison: baseline report is required but was not provided")

    passed = len(reasons) == 0
    gate_breaches, breach_counts = _summarize_gate_breaches(reasons, max_items=30)
    return ReleaseGateReport(
        local_summary=local_summary,
        local_failures=local_failures,
        corpus_report=corpus_report,
        corpus_failures=corpus_failures,
        lane_scheduling={
            "passed": lane_report.passed,
            "serial_elapsed_ms": lane_report.serial_elapsed_ms,
            "parallel_elapsed_ms": lane_report.parallel_elapsed_ms,
            "speedup_ratio": lane_report.speedup_ratio,
            "min_speedup_ratio_gate": min_lane_speedup_ratio,
            "max_parallel_elapsed_ms_gate": max_lane_parallel_elapsed_ms,
            "details": list(lane_report.details),
        },
        context_cache={
            "passed": context_report.passed,
            "cold_ms": context_report.cold_ms,
            "warm_ms": context_report.warm_ms,
            "speedup_ratio": context_report.speedup_ratio,
            "min_speedup_ratio_gate": min_context_cache_speedup_ratio,
            "max_warm_ms_gate": max_context_cache_warm_ms,
            "details": list(context_report.details),
        },
        coding_loop={
            "passed": coding_report.passed,
            "iterations": coding_report.iterations,
            "success_rate": coding_report.success_rate,
            "max_p95_total_ms_gate": max_coding_loop_p95_total_ms,
            "p95_total_ms": coding_report.p95_total_ms,
            "avg_inspect_ms": coding_report.avg_inspect_ms,
            "avg_patch_ms": coding_report.avg_patch_ms,
            "avg_verify_ms": coding_report.avg_verify_ms,
            "avg_summarize_ms": coding_report.avg_summarize_ms,
            "min_success_rate_gate": min_coding_loop_success_rate,
            "details": list(coding_report.details),
        },
        comparison=comparison,
        target_improvement_pct=float(target_improvement_pct),
        require_comparison=bool(require_comparison),
        passed=passed,
        reasons=reasons,
        gate_breaches=gate_breaches,
        breach_counts=breach_counts,
    )


def run_release_gate_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    """Smokecheck release gate orchestration on minimal settings."""
    errors: list[str] = []
    class _Gates:
        max_p95_latency_ms = 120000.0
        min_tool_success_rate_pct = 1.0
        min_deterministic_replay_pass_rate_pct = 1.0
        min_lane_speedup_ratio = 1.0
        max_lane_parallel_elapsed_ms = 999999.0
        min_context_cache_speedup_ratio = 1.0
        max_context_cache_warm_ms = 999999.0
        min_coding_loop_success_rate_pct = 1.0
        max_coding_loop_p95_total_ms = 999999.0

    gates = _Gates()
    report = run_release_gate(
        workspace=workdir,
        gates=gates,
        local_iterations=1,
        corpus_iterations=1,
        baseline_report=None,
        target_improvement_pct=35.0,
        require_comparison=False,
    )
    if not isinstance(report.passed, bool):
        errors.append("release gate report.passed must be a bool")
    if report.local_summary.samples <= 0:
        errors.append("local summary missing samples")
    if float(report.corpus_report.summary.get("samples", 0.0)) <= 0:
        errors.append("corpus summary missing samples")
    if "passed" not in report.lane_scheduling:
        errors.append("lane_scheduling summary missing passed field")
    if "passed" not in report.context_cache:
        errors.append("context_cache summary missing passed field")
    if "passed" not in report.coding_loop:
        errors.append("coding_loop summary missing passed field")
    if not isinstance(report.gate_breaches, list):
        errors.append("gate_breaches must be a list")
    if not isinstance(report.breach_counts, dict):
        errors.append("breach_counts must be a dict")
    return len(errors) == 0, errors


def write_release_gate_report(path: Path, report: ReleaseGateReport) -> None:
    """Write consolidated release gate report JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def _summarize_gate_breaches(reasons: list[str], max_items: int = 30) -> tuple[list[str], dict[str, int]]:
    categories = ["local", "corpus", "lane", "context", "coding", "comparison", "other"]
    buckets: dict[str, list[str]] = {k: [] for k in categories}
    for reason in reasons:
        text = str(reason)
        lowered = text.lower()
        if lowered.startswith("local:"):
            buckets["local"].append(text)
        elif lowered.startswith("corpus:"):
            buckets["corpus"].append(text)
        elif lowered.startswith("lane_scheduling:"):
            buckets["lane"].append(text)
        elif lowered.startswith("context_cache:"):
            buckets["context"].append(text)
        elif lowered.startswith("coding_loop:"):
            buckets["coding"].append(text)
        elif lowered.startswith("comparison:"):
            buckets["comparison"].append(text)
        else:
            buckets["other"].append(text)

    out: list[str] = []
    for key in categories:
        for item in buckets[key]:
            out.append(f"{key}: {item}")
            if len(out) >= max_items:
                break
        if len(out) >= max_items:
            break

    counts = {k: len(v) for k, v in buckets.items() if v}
    return out, counts
