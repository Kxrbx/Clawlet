"""Matched coding corpus benchmark and baseline comparison."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from clawlet.benchmarks.async_utils import run_async as _run_async
from clawlet.benchmarks.stats_utils import percentile

@dataclass(slots=True)
class ScenarioResult:
    scenario_id: str
    title: str
    description: str
    samples: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    success_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CorpusBenchmarkReport:
    corpus_id: str
    created_at: str
    workspace: str
    iterations: int
    summary: dict[str, float]
    scenarios: list[ScenarioResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_id": self.corpus_id,
            "created_at": self.created_at,
            "workspace": self.workspace,
            "iterations": self.iterations,
            "summary": dict(self.summary),
            "scenarios": [s.to_dict() for s in self.scenarios],
        }


@dataclass(slots=True)
class ScenarioComparison:
    scenario_id: str
    baseline_p95_ms: float
    current_p95_ms: float
    improvement_pct: float


@dataclass(slots=True)
class CorpusComparisonReport:
    baseline_source: str
    baseline_p95_ms: float
    current_p95_ms: float
    improvement_pct: float
    target_improvement_pct: float
    meets_target: bool
    regressions: list[str] = field(default_factory=list)
    scenario_comparisons: list[ScenarioComparison] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_source": self.baseline_source,
            "baseline_p95_ms": self.baseline_p95_ms,
            "current_p95_ms": self.current_p95_ms,
            "improvement_pct": self.improvement_pct,
            "target_improvement_pct": self.target_improvement_pct,
            "meets_target": self.meets_target,
            "regressions": list(self.regressions),
            "scenario_comparisons": [asdict(s) for s in self.scenario_comparisons],
        }


def load_corpus_benchmark_report(path: Path) -> CorpusBenchmarkReport:
    """Load a corpus benchmark report from either wrapped or raw JSON format."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    report_obj = raw.get("report") if isinstance(raw, dict) and isinstance(raw.get("report"), dict) else raw
    if not isinstance(report_obj, dict):
        raise ValueError("Invalid corpus report JSON structure")

    scenarios: list[ScenarioResult] = []
    for item in report_obj.get("scenarios") or []:
        if not isinstance(item, dict):
            continue
        scenarios.append(
            ScenarioResult(
                scenario_id=str(item.get("scenario_id") or ""),
                title=str(item.get("title") or ""),
                description=str(item.get("description") or ""),
                samples=int(item.get("samples") or 0),
                p50_ms=float(item.get("p50_ms") or 0.0),
                p95_ms=float(item.get("p95_ms") or 0.0),
                p99_ms=float(item.get("p99_ms") or 0.0),
                success_rate=float(item.get("success_rate") or 0.0),
            )
        )

    summary_raw = report_obj.get("summary") or {}
    summary = {
        "samples": float(summary_raw.get("samples") or 0.0),
        "p50_ms": float(summary_raw.get("p50_ms") or 0.0),
        "p95_ms": float(summary_raw.get("p95_ms") or 0.0),
        "p99_ms": float(summary_raw.get("p99_ms") or 0.0),
        "success_rate": float(summary_raw.get("success_rate") or 0.0),
    }
    return CorpusBenchmarkReport(
        corpus_id=str(report_obj.get("corpus_id") or "unknown"),
        created_at=str(report_obj.get("created_at") or ""),
        workspace=str(report_obj.get("workspace") or ""),
        iterations=int(report_obj.get("iterations") or 0),
        summary=summary,
        scenarios=scenarios,
    )


def run_matched_corpus(workspace: Path, iterations: int = 10) -> CorpusBenchmarkReport:
    """Run the standard coding-agent scenario corpus."""
    from clawlet.tools import create_default_tool_registry

    iterations = max(1, int(iterations))
    workspace = workspace.resolve()
    registry = create_default_tool_registry(allowed_dir=str(workspace))

    required_tools = ["list_dir", "read_file", "write_file", "edit_file", "apply_patch", "shell"]
    missing = [name for name in required_tools if registry.get(name) is None]
    if missing:
        raise RuntimeError(f"Missing required tools for corpus benchmark: {', '.join(missing)}")

    cases_root = workspace / ".benchmark-corpus"
    cases_root.mkdir(parents=True, exist_ok=True)

    scenarios: list[tuple[str, str, str, Callable[[int], bool]]] = [
        (
            "repo_understanding",
            "Repo Understanding",
            "List and read target source files to build repository awareness.",
            lambda i: _scenario_repo_understanding(registry, cases_root, i),
        ),
        (
            "safe_edit_verify",
            "Safe Editing",
            "Write/edit/read loop with deterministic verification.",
            lambda i: _scenario_safe_edit_verify(registry, cases_root, i),
        ),
        (
            "patch_apply_validate",
            "Patch Validation",
            "Apply unified diff patch and validate output contents.",
            lambda i: _scenario_patch_apply_validate(registry, cases_root, i),
        ),
        (
            "shell_inspect",
            "Shell Inspection",
            "Run non-destructive shell inspection commands inside workspace.",
            lambda i: _scenario_shell_inspect(registry, cases_root, i),
        ),
        (
            "failure_recover",
            "Failure Recovery",
            "Handle expected read failure then recover with successful write/read.",
            lambda i: _scenario_failure_recover(registry, cases_root, i),
        ),
    ]

    scenario_results: list[ScenarioResult] = []
    all_latencies: list[float] = []
    total_successes = 0
    total_samples = 0

    for scenario_id, title, description, run_case in scenarios:
        latencies: list[float] = []
        successes = 0
        for i in range(iterations):
            started = time.perf_counter()
            ok = False
            try:
                ok = bool(run_case(i))
            except Exception:
                ok = False
            elapsed = (time.perf_counter() - started) * 1000.0
            latencies.append(elapsed)
            if ok:
                successes += 1

        ordered = sorted(latencies)
        scenario_result = ScenarioResult(
            scenario_id=scenario_id,
            title=title,
            description=description,
            samples=len(latencies),
            p50_ms=percentile(ordered, 50),
            p95_ms=percentile(ordered, 95),
            p99_ms=percentile(ordered, 99),
            success_rate=(successes / max(1, len(latencies))) * 100.0,
        )
        scenario_results.append(scenario_result)
        all_latencies.extend(latencies)
        total_successes += successes
        total_samples += len(latencies)

    ordered_all = sorted(all_latencies)
    summary = {
        "samples": float(total_samples),
        "p50_ms": percentile(ordered_all, 50),
        "p95_ms": percentile(ordered_all, 95),
        "p99_ms": percentile(ordered_all, 99),
        "success_rate": (total_successes / max(1, total_samples)) * 100.0,
    }

    return CorpusBenchmarkReport(
        corpus_id="matched-v1",
        created_at=datetime.now(timezone.utc).isoformat(),
        workspace=str(workspace),
        iterations=iterations,
        summary=summary,
        scenarios=scenario_results,
    )


def check_corpus_gates(report: CorpusBenchmarkReport, gates: Any) -> list[str]:
    failures: list[str] = []
    p95_ms = float(report.summary.get("p95_ms", 0.0))
    success_rate = float(report.summary.get("success_rate", 0.0))
    if p95_ms > gates.max_p95_latency_ms:
        failures.append(
            f"corpus p95 latency {p95_ms:.2f}ms exceeded gate {gates.max_p95_latency_ms:.2f}ms"
        )
    if success_rate < gates.min_tool_success_rate_pct:
        failures.append(
            f"corpus success rate {success_rate:.2f}% below gate {gates.min_tool_success_rate_pct:.2f}%"
        )
    for item in report.scenarios:
        if item.success_rate < gates.min_tool_success_rate_pct:
            failures.append(
                "scenario "
                f"{item.scenario_id} success {item.success_rate:.2f}% "
                f"below gate {gates.min_tool_success_rate_pct:.2f}%"
            )
    return failures


def compare_corpus_to_baseline(
    report: CorpusBenchmarkReport,
    baseline_path: Path,
    target_improvement_pct: float = 35.0,
) -> CorpusComparisonReport:
    baseline = load_corpus_benchmark_report(baseline_path)
    baseline_p95 = float(baseline.summary.get("p95_ms", 0.0))
    current_p95 = float(report.summary.get("p95_ms", 0.0))
    improvement_pct = _improvement_pct(baseline_p95, current_p95)

    regressions: list[str] = []
    scenario_comparisons: list[ScenarioComparison] = []
    baseline_scenarios = {s.scenario_id: float(s.p95_ms) for s in baseline.scenarios if s.scenario_id}

    for scenario in report.scenarios:
        if scenario.scenario_id not in baseline_scenarios:
            continue
        base = baseline_scenarios[scenario.scenario_id]
        current = float(scenario.p95_ms)
        delta = _improvement_pct(base, current)
        scenario_comparisons.append(
            ScenarioComparison(
                scenario_id=scenario.scenario_id,
                baseline_p95_ms=base,
                current_p95_ms=current,
                improvement_pct=delta,
            )
        )
        if current > base:
            regressions.append(
                f"scenario {scenario.scenario_id} regressed: baseline={base:.2f}ms current={current:.2f}ms"
            )

    meets_target = improvement_pct >= float(target_improvement_pct) and not regressions

    return CorpusComparisonReport(
        baseline_source=str(baseline_path),
        baseline_p95_ms=baseline_p95,
        current_p95_ms=current_p95,
        improvement_pct=improvement_pct,
        target_improvement_pct=float(target_improvement_pct),
        meets_target=meets_target,
        regressions=regressions,
        scenario_comparisons=scenario_comparisons,
    )


def compare_corpus_reports(
    current_path: Path,
    baseline_path: Path,
    target_improvement_pct: float = 35.0,
) -> CorpusComparisonReport:
    """Compare two saved corpus benchmark reports."""
    current = load_corpus_benchmark_report(current_path)
    return compare_corpus_to_baseline(
        report=current,
        baseline_path=baseline_path,
        target_improvement_pct=target_improvement_pct,
    )


def write_corpus_report(
    path: Path,
    report: CorpusBenchmarkReport,
    gate_failures: list[str],
    comparison: CorpusComparisonReport | None = None,
) -> None:
    payload: dict[str, Any] = {
        "report": report.to_dict(),
        "gate_failures": list(gate_failures),
        "passed": len(gate_failures) == 0,
    }
    if comparison is not None:
        payload["comparison"] = comparison.to_dict()
        payload["comparison_passed"] = bool(comparison.meets_target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def format_publishable_corpus_report(
    current_report: CorpusBenchmarkReport,
    comparison: CorpusComparisonReport,
) -> str:
    """Render a publishable markdown benchmark summary."""
    current_p95 = float(current_report.summary.get("p95_ms", 0.0))
    current_success = float(current_report.summary.get("success_rate", 0.0))
    lines: list[str] = []
    lines.append("# Clawlet Benchmark Report")
    lines.append("")
    lines.append(f"- Corpus: `{current_report.corpus_id}`")
    lines.append(f"- Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Current report created_at: {current_report.created_at}")
    lines.append(f"- Baseline source: `{comparison.baseline_source}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Baseline p95: **{comparison.baseline_p95_ms:.2f} ms**")
    lines.append(f"- Current p95: **{comparison.current_p95_ms:.2f} ms**")
    lines.append(
        f"- Improvement: **{comparison.improvement_pct:.2f}%** "
        f"(target {comparison.target_improvement_pct:.2f}%)"
    )
    lines.append(f"- Meets target: **{'yes' if comparison.meets_target else 'no'}**")
    lines.append(f"- Current success rate: **{current_success:.2f}%**")
    lines.append(f"- Current aggregate p95: **{current_p95:.2f} ms**")
    lines.append("")
    lines.append("## Scenario Deltas")
    lines.append("")
    lines.append("| Scenario | Baseline p95 (ms) | Current p95 (ms) | Delta (%) |")
    lines.append("|---|---:|---:|---:|")
    for row in comparison.scenario_comparisons:
        lines.append(
            f"| `{row.scenario_id}` | {row.baseline_p95_ms:.2f} | "
            f"{row.current_p95_ms:.2f} | {row.improvement_pct:.2f}% |"
        )
    if not comparison.scenario_comparisons:
        lines.append("| _no overlapping scenarios_ | - | - | - |")
    lines.append("")
    lines.append("## Regressions")
    lines.append("")
    if comparison.regressions:
        for item in comparison.regressions:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Current Scenario Results")
    lines.append("")
    lines.append("| Scenario | Samples | p95 (ms) | Success (%) |")
    lines.append("|---|---:|---:|---:|")
    for scenario in current_report.scenarios:
        lines.append(
            f"| `{scenario.scenario_id}` | {scenario.samples} | "
            f"{scenario.p95_ms:.2f} | {scenario.success_rate:.2f}% |"
        )
    return "\n".join(lines) + "\n"


def write_publishable_corpus_report(path: Path, markdown_text: str) -> None:
    """Write publishable benchmark markdown report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_text, encoding="utf-8")


def build_competitive_corpus_bundle(
    report: CorpusBenchmarkReport,
    comparison: CorpusComparisonReport,
    gate_failures: list[str],
) -> dict[str, Any]:
    """Build a machine-readable competitive benchmark artifact payload."""
    gate_passed = len(gate_failures) == 0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": gate_passed and bool(comparison.meets_target),
        "gate_passed": gate_passed,
        "comparison_passed": bool(comparison.meets_target),
        "gate_failures": list(gate_failures),
        "report": report.to_dict(),
        "comparison": comparison.to_dict(),
    }


def write_competitive_corpus_bundle(path: Path, payload: dict[str, Any]) -> None:
    """Write machine-readable competitive benchmark bundle JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_publishable_corpus_report_from_paths(
    current_path: Path,
    baseline_path: Path,
    target_improvement_pct: float = 35.0,
) -> tuple[CorpusComparisonReport, str]:
    """Load reports from disk and build publishable markdown text."""
    current = load_corpus_benchmark_report(current_path)
    comparison = compare_corpus_reports(
        current_path=current_path,
        baseline_path=baseline_path,
        target_improvement_pct=target_improvement_pct,
    )
    markdown = format_publishable_corpus_report(current, comparison)
    return comparison, markdown


def run_matched_corpus_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    report = run_matched_corpus(workdir, iterations=1)
    if report.corpus_id != "matched-v1":
        errors.append("unexpected corpus id")
    if not report.scenarios:
        errors.append("missing scenario results")
    if float(report.summary.get("samples", 0)) <= 0:
        errors.append("summary samples must be > 0")
    if float(report.summary.get("success_rate", 0)) <= 0:
        errors.append("summary success_rate must be > 0")
    return len(errors) == 0, errors


def run_corpus_compare_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    workdir.mkdir(parents=True, exist_ok=True)
    current_path = workdir / "corpus-current.json"
    baseline_path = workdir / "corpus-baseline.json"

    baseline = {
        "report": {
            "corpus_id": "matched-v1",
            "created_at": "2026-02-20T00:00:00+00:00",
            "workspace": str(workdir),
            "iterations": 1,
            "summary": {
                "samples": 5,
                "p50_ms": 10.0,
                "p95_ms": 100.0,
                "p99_ms": 120.0,
                "success_rate": 100.0,
            },
            "scenarios": [
                {
                    "scenario_id": "repo_understanding",
                    "title": "Repo",
                    "description": "",
                    "samples": 1,
                    "p50_ms": 10.0,
                    "p95_ms": 30.0,
                    "p99_ms": 31.0,
                    "success_rate": 100.0,
                }
            ],
        }
    }
    current = {
        "report": {
            "corpus_id": "matched-v1",
            "created_at": "2026-02-27T00:00:00+00:00",
            "workspace": str(workdir),
            "iterations": 1,
            "summary": {
                "samples": 5,
                "p50_ms": 10.0,
                "p95_ms": 60.0,
                "p99_ms": 80.0,
                "success_rate": 100.0,
            },
            "scenarios": [
                {
                    "scenario_id": "repo_understanding",
                    "title": "Repo",
                    "description": "",
                    "samples": 1,
                    "p50_ms": 10.0,
                    "p95_ms": 20.0,
                    "p99_ms": 21.0,
                    "success_rate": 100.0,
                }
            ],
        }
    }
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    current_path.write_text(json.dumps(current), encoding="utf-8")

    comp = compare_corpus_reports(
        current_path=current_path,
        baseline_path=baseline_path,
        target_improvement_pct=35.0,
    )
    if not comp.meets_target:
        errors.append("expected comparison to meet target")
    if comp.improvement_pct < 35.0:
        errors.append("expected improvement >= 35%")
    return len(errors) == 0, errors


def _scenario_repo_understanding(registry, root: Path, i: int) -> bool:
    case = root / f"repo-understanding-{i}"
    case.mkdir(parents=True, exist_ok=True)
    target = case / "module.py"
    target.write_text("def run_case():\n    return 1\n", encoding="utf-8")

    list_result = _run_async(registry.execute("list_dir", path=str(case.relative_to(root.parent))))
    read_result = _run_async(registry.execute("read_file", path=str(target.relative_to(root.parent))))
    return bool(list_result.success and read_result.success and "run_case" in read_result.output)


def _scenario_safe_edit_verify(registry, root: Path, i: int) -> bool:
    path = root / f"safe-edit-{i}.txt"
    rel = str(path.relative_to(root.parent))
    write_ok = _run_async(registry.execute("write_file", path=rel, content=f"line={i}\n"))
    edit_ok = _run_async(
        registry.execute("edit_file", path=rel, old_text=f"line={i}", new_text=f"line={i}-done")
    )
    read_ok = _run_async(registry.execute("read_file", path=rel))
    return bool(write_ok.success and edit_ok.success and read_ok.success and "-done" in read_ok.output)


def _scenario_patch_apply_validate(registry, root: Path, i: int) -> bool:
    path = root / f"patch-{i}.txt"
    rel = str(path.relative_to(root.parent))
    _run_async(registry.execute("write_file", path=rel, content="alpha\nbeta\n"))
    patch = "@@ -1,2 +1,2 @@\n alpha\n-beta\n+beta_done\n"
    patch_ok = _run_async(registry.execute("apply_patch", path=rel, patch=patch))
    read_ok = _run_async(registry.execute("read_file", path=rel))
    return bool(patch_ok.success and read_ok.success and "beta_done" in read_ok.output)


def _scenario_shell_inspect(registry, root: Path, i: int) -> bool:
    _ = i
    pwd = _run_async(registry.execute("shell", command="pwd"))
    ls = _run_async(registry.execute("shell", command="ls"))
    return bool(pwd.success and ls.success)


def _scenario_failure_recover(registry, root: Path, i: int) -> bool:
    missing = root / f"missing-{i}.txt"
    rel_missing = str(missing.relative_to(root.parent))
    failed_read = _run_async(registry.execute("read_file", path=rel_missing))

    good = root / f"recover-{i}.txt"
    rel_good = str(good.relative_to(root.parent))
    write_ok = _run_async(registry.execute("write_file", path=rel_good, content="ok\n"))
    read_ok = _run_async(registry.execute("read_file", path=rel_good))

    return bool((not failed_read.success) and write_ok.success and read_ok.success and "ok" in read_ok.output)


def _improvement_pct(baseline_ms: float, current_ms: float) -> float:
    if baseline_ms <= 0:
        return 0.0
    return ((baseline_ms - current_ms) / baseline_ms) * 100.0
