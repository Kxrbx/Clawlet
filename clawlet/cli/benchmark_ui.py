"""Benchmark command helpers for the CLI."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from clawlet.cli.common_ui import print_footer, print_section

console = Console()


def run_benchmark_run(
    workspace: Optional[Path],
    iterations: int,
    report_path: Optional[Path],
    fail_on_gate: bool,
    get_workspace_path_fn,
    load_benchmarks_settings_fn,
) -> None:
    """Run local performance benchmark and evaluate quality gates."""
    from clawlet.benchmarks import check_gates, run_local_runtime_benchmark, write_report

    workspace_path = workspace or get_workspace_path_fn()
    gates_cfg = load_benchmarks_settings_fn(workspace_path)

    print_section("Benchmark", f"Running {iterations} iterations")
    summary = run_local_runtime_benchmark(workspace=workspace_path, iterations=iterations)
    failures = check_gates(summary, gates_cfg.gates)

    console.print(f"|  Samples: {summary.samples}")
    console.print(f"|  p50: {summary.p50_ms:.2f} ms")
    console.print(f"|  p95: {summary.p95_ms:.2f} ms")
    console.print(f"|  p99: {summary.p99_ms:.2f} ms")
    console.print(f"|  Success: {summary.success_rate:.2f}%")
    console.print(
        "|  Determinism: "
        f"{summary.deterministic_replay_pass_rate_pct:.2f}% "
        "(replay signature stability)"
    )

    if failures:
        console.print("|")
        console.print("|  [red]Gate failures:[/red]")
        for failure in failures:
            console.print(f"|    - {failure}")
    else:
        console.print("|  [green]All quality gates passed[/green]")

    output = report_path or (workspace_path / "benchmark-report.json")
    write_report(output, summary, failures)
    console.print(f"|  Report: {output}")
    print_footer()

    if fail_on_gate and failures:
        raise typer.Exit(2)


def run_benchmark_remote_health(workspace: Optional[Path], get_workspace_path_fn) -> None:
    """Check configured remote worker health endpoint."""
    from clawlet.config import RuntimeSettings
    from clawlet.runtime.remote import RemoteToolExecutor

    workspace_path = workspace or get_workspace_path_fn()
    runtime_cfg = RuntimeSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            runtime_cfg = RuntimeSettings(**(raw.get("runtime") or {}))
        except Exception:
            pass

    remote_cfg = runtime_cfg.remote
    if not remote_cfg.enabled:
        console.print("[yellow]Remote execution is disabled (runtime.remote.enabled=false)[/yellow]")
        raise typer.Exit(1)
    if not remote_cfg.endpoint:
        console.print("[red]Remote execution enabled but endpoint is empty[/red]")
        raise typer.Exit(1)

    api_key = os.environ.get(remote_cfg.api_key_env, "")
    client = RemoteToolExecutor(
        endpoint=remote_cfg.endpoint,
        api_key=api_key,
        timeout_seconds=remote_cfg.timeout_seconds,
    )
    ok, detail = asyncio.run(client.health())

    print_section("Remote Health", remote_cfg.endpoint)
    console.print(f"|  enabled={str(remote_cfg.enabled).lower()}")
    console.print(f"|  api_key_env={remote_cfg.api_key_env}")
    console.print(f"|  status={'ok' if ok else 'failed'}")
    console.print(f"|  detail={detail}")
    print_footer()

    if not ok:
        raise typer.Exit(2)


def run_benchmark_remote_parity(workspace: Optional[Path], get_workspace_path_fn) -> None:
    """Run remote/local execution parity smokecheck."""
    from clawlet.benchmarks import run_remote_parity_smokecheck

    workspace_path = workspace or get_workspace_path_fn()
    ok, errors = run_remote_parity_smokecheck(workspace_path)
    print_section("Remote Parity", str(workspace_path))
    console.print(f"|  passed={'yes' if ok else 'no'}")
    if errors:
        for item in errors:
            console.print(f"|  - {item}")
    print_footer()
    if not ok:
        raise typer.Exit(2)


def run_benchmark_lanes(workspace: Optional[Path], report_path: Optional[Path], get_workspace_path_fn) -> None:
    """Run lane scheduling benchmark (serial vs parallel)."""
    from clawlet.benchmarks import run_lane_contention_benchmark, write_lane_contention_report

    workspace_path = workspace or get_workspace_path_fn()
    report = run_lane_contention_benchmark(workspace_path)

    print_section("Lane Scheduling", str(workspace_path))
    console.print(f"|  passed={'yes' if report.passed else 'no'}")
    console.print(f"|  serial_elapsed_ms={report.serial_elapsed_ms:.1f}")
    console.print(f"|  parallel_elapsed_ms={report.parallel_elapsed_ms:.1f}")
    console.print(f"|  speedup_ratio={report.speedup_ratio:.2f}x")
    if report.details:
        for item in report.details:
            console.print(f"|  - {item}")
    output = report_path or (workspace_path / "benchmark-lanes-report.json")
    write_lane_contention_report(output, report)
    console.print(f"|  report={output}")
    print_footer()

    if not report.passed:
        raise typer.Exit(2)


def run_benchmark_context_cache(
    workspace: Optional[Path],
    report_path: Optional[Path],
    get_workspace_path_fn,
) -> None:
    """Run context-engine warm-cache vs cold-cache benchmark."""
    from clawlet.benchmarks import run_context_cache_benchmark, write_context_cache_report

    workspace_path = workspace or get_workspace_path_fn()
    report = run_context_cache_benchmark(workspace_path)

    print_section("Context Cache", str(workspace_path))
    console.print(f"|  passed={'yes' if report.passed else 'no'}")
    console.print(f"|  cold_ms={report.cold_ms:.1f}")
    console.print(f"|  warm_ms={report.warm_ms:.1f}")
    console.print(f"|  speedup_ratio={report.speedup_ratio:.2f}x")
    if report.details:
        for item in report.details:
            console.print(f"|  - {item}")
    output = report_path or (workspace_path / "benchmark-context-cache-report.json")
    write_context_cache_report(output, report)
    console.print(f"|  report={output}")
    print_footer()

    if not report.passed:
        raise typer.Exit(2)


def run_benchmark_coding_loop(
    workspace: Optional[Path],
    iterations: int,
    report_path: Optional[Path],
    get_workspace_path_fn,
) -> None:
    """Run coding-loop benchmark (inspect -> patch -> verify -> summarize)."""
    from clawlet.benchmarks import run_coding_loop_benchmark, write_coding_loop_report

    workspace_path = workspace or get_workspace_path_fn()
    report = run_coding_loop_benchmark(workspace_path, iterations=iterations)

    print_section("Coding Loop", str(workspace_path))
    console.print(f"|  passed={'yes' if report.passed else 'no'}")
    console.print(f"|  iterations={report.iterations}")
    console.print(f"|  success_rate={report.success_rate:.2f}%")
    console.print(f"|  p95_total_ms={report.p95_total_ms:.2f}")
    console.print(
        "|  "
        f"avg_inspect_ms={report.avg_inspect_ms:.2f} "
        f"avg_patch_ms={report.avg_patch_ms:.2f} "
        f"avg_verify_ms={report.avg_verify_ms:.2f} "
        f"avg_summarize_ms={report.avg_summarize_ms:.2f}"
    )
    if report.details:
        for item in report.details:
            console.print(f"|  - {item}")
    output = report_path or (workspace_path / "benchmark-coding-loop-report.json")
    write_coding_loop_report(output, report)
    console.print(f"|  report={output}")
    print_footer()

    if not report.passed:
        raise typer.Exit(2)


def run_benchmark_corpus(
    workspace: Optional[Path],
    iterations: int,
    report_path: Optional[Path],
    baseline_report: Optional[Path],
    target_improvement_pct: float,
    fail_on_gate: bool,
    fail_on_regression: bool,
    publish_report: bool,
    publish_report_path: Optional[Path],
    get_workspace_path_fn,
    load_benchmarks_settings_fn,
    print_corpus_comparison_summary_fn,
) -> None:
    """Run the standard corpus and optional baseline comparison."""
    from clawlet.benchmarks import (
        check_corpus_gates,
        compare_corpus_to_baseline,
        format_publishable_corpus_report,
        run_matched_corpus,
        write_corpus_report,
        write_publishable_corpus_report,
    )

    workspace_path = workspace or get_workspace_path_fn()
    gates_cfg = load_benchmarks_settings_fn(workspace_path)

    print_section("Benchmark Corpus", f"Standard scenarios x {iterations} iteration(s)")
    report = run_matched_corpus(workspace=workspace_path, iterations=iterations)
    gate_failures = check_corpus_gates(report, gates_cfg.gates)

    summary = report.summary
    console.print(f"|  Corpus: {report.corpus_id}")
    console.print(f"|  Samples: {int(summary.get('samples', 0))}")
    console.print(f"|  p50: {float(summary.get('p50_ms', 0.0)):.2f} ms")
    console.print(f"|  p95: {float(summary.get('p95_ms', 0.0)):.2f} ms")
    console.print(f"|  p99: {float(summary.get('p99_ms', 0.0)):.2f} ms")
    console.print(f"|  Success: {float(summary.get('success_rate', 0.0)):.2f}%")
    console.print("|")
    for scenario in report.scenarios:
        console.print(
            "|  "
            f"{scenario.scenario_id}: p95={scenario.p95_ms:.2f}ms "
            f"success={scenario.success_rate:.2f}%"
        )

    comparison = None
    if baseline_report is not None:
        comparison = compare_corpus_to_baseline(
            report=report,
            baseline_path=baseline_report,
            target_improvement_pct=target_improvement_pct,
        )
        console.print("|")
        print_corpus_comparison_summary_fn(console, comparison, prefix="|  ", include_p95=False)

    if gate_failures:
        console.print("|")
        console.print("|  [red]Gate failures:[/red]")
        for failure in gate_failures:
            console.print(f"|    - {failure}")
    else:
        console.print("|")
        console.print("|  [green]All corpus gates passed[/green]")

    output = report_path or (workspace_path / "benchmark-corpus-report.json")
    write_corpus_report(output, report, gate_failures, comparison=comparison)
    console.print(f"|  Report: {output}")
    if publish_report:
        if comparison is None:
            console.print("|  [red]publish-report requires --baseline-report[/red]")
            print_footer()
            raise typer.Exit(2)
        publish_out = publish_report_path or (workspace_path / "benchmark-report.md")
        markdown = format_publishable_corpus_report(report, comparison)
        write_publishable_corpus_report(publish_out, markdown)
        console.print(f"|  Publish report: {publish_out}")
    print_footer()

    if fail_on_gate and gate_failures:
        raise typer.Exit(2)
    if fail_on_regression and comparison is not None and not comparison.meets_target:
        raise typer.Exit(2)


def run_benchmark_compare(
    current_report: Path,
    baseline_report: Path,
    target_improvement_pct: float,
    fail_on_regression: bool,
    publish_report_path: Optional[Path],
    json_output: bool,
    print_corpus_comparison_summary_fn,
    corpus_comparison_payload_fn,
) -> None:
    """Compare two saved corpus reports."""
    from clawlet.benchmarks import (
        build_publishable_corpus_report_from_paths,
        compare_corpus_reports,
        write_publishable_corpus_report,
    )

    markdown: Optional[str] = None
    if publish_report_path is not None:
        comparison, markdown = build_publishable_corpus_report_from_paths(
            current_path=current_report,
            baseline_path=baseline_report,
            target_improvement_pct=target_improvement_pct,
        )
        write_publishable_corpus_report(publish_report_path, markdown)
    else:
        comparison = compare_corpus_reports(
            current_path=current_report,
            baseline_path=baseline_report,
            target_improvement_pct=target_improvement_pct,
        )

    print_section("Benchmark Compare", "Current vs baseline corpus reports")
    print_corpus_comparison_summary_fn(console, comparison, prefix="|  ", include_p95=True)
    if publish_report_path is not None:
        console.print(f"|  Publish report: {publish_report_path}")
    if json_output:
        payload = corpus_comparison_payload_fn(
            comparison,
            current_report=current_report,
            baseline_report=baseline_report,
            publish_report_path=publish_report_path,
        )
        console.print(json.dumps(payload, indent=2, sort_keys=True))
    print_footer()

    if fail_on_regression and not comparison.meets_target:
        raise typer.Exit(2)


def run_benchmark_publish_report(
    current_report: Path,
    baseline_report: Path,
    out: Path,
    target_improvement_pct: float,
    fail_on_regression: bool,
    json_output: bool,
    print_regressions_fn,
    corpus_comparison_payload_fn,
) -> None:
    """Generate publishable markdown report from current/baseline corpus reports."""
    from clawlet.benchmarks import (
        build_publishable_corpus_report_from_paths,
        write_publishable_corpus_report,
    )

    comparison, markdown = build_publishable_corpus_report_from_paths(
        current_path=current_report,
        baseline_path=baseline_report,
        target_improvement_pct=target_improvement_pct,
    )
    write_publishable_corpus_report(out, markdown)

    print_section("Benchmark Publish Report", "Baseline comparison markdown")
    console.print(f"|  current={current_report}")
    console.print(f"|  baseline={baseline_report}")
    console.print(f"|  output={out}")
    console.print(f"|  improvement={comparison.improvement_pct:.2f}%")
    console.print(f"|  meets_target={'yes' if comparison.meets_target else 'no'}")
    print_regressions_fn(console, list(comparison.regressions), prefix="|  ")
    if json_output:
        payload = corpus_comparison_payload_fn(
            comparison,
            current_report=current_report,
            baseline_report=baseline_report,
            publish_report_path=out,
        )
        console.print(json.dumps(payload, indent=2, sort_keys=True))
    print_footer()

    if fail_on_regression and not comparison.meets_target:
        raise typer.Exit(2)


def run_benchmark_competitive_report(
    workspace: Optional[Path],
    iterations: int,
    baseline_report: Path,
    target_improvement_pct: float,
    corpus_report_out: Optional[Path],
    bundle_out: Optional[Path],
    markdown_out: Optional[Path],
    json_output: bool,
    fail_on_gate: bool,
    fail_on_regression: bool,
    get_workspace_path_fn,
    load_benchmarks_settings_fn,
    print_regressions_fn,
) -> None:
    """Run corpus benchmark + baseline comparison and emit publishable artifacts."""
    from clawlet.benchmarks import (
        build_competitive_corpus_bundle,
        check_corpus_gates,
        compare_corpus_to_baseline,
        format_publishable_corpus_report,
        run_matched_corpus,
        write_competitive_corpus_bundle,
        write_corpus_report,
        write_publishable_corpus_report,
    )

    workspace_path = workspace or get_workspace_path_fn()
    gates_cfg = load_benchmarks_settings_fn(workspace_path)

    report = run_matched_corpus(workspace=workspace_path, iterations=iterations)
    gate_failures = check_corpus_gates(report, gates_cfg.gates)
    comparison = compare_corpus_to_baseline(
        report=report,
        baseline_path=baseline_report,
        target_improvement_pct=target_improvement_pct,
    )

    corpus_out = corpus_report_out or (workspace_path / "benchmark-corpus-report.json")
    write_corpus_report(corpus_out, report, gate_failures, comparison=comparison)

    markdown_text = format_publishable_corpus_report(report, comparison)
    markdown_path = markdown_out or (workspace_path / "benchmark-report.md")
    write_publishable_corpus_report(markdown_path, markdown_text)

    bundle = build_competitive_corpus_bundle(
        report,
        comparison,
        gate_failures,
    )
    bundle_path = bundle_out or (workspace_path / "benchmark-competitive.json")
    write_competitive_corpus_bundle(bundle_path, bundle)

    if json_output:
        payload = dict(bundle)
        payload["workspace"] = str(workspace_path)
        payload["corpus_report_path"] = str(corpus_out)
        payload["bundle_report_path"] = str(bundle_path)
        payload["markdown_report_path"] = str(markdown_path)
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        if fail_on_gate and gate_failures:
            raise typer.Exit(2)
        if fail_on_regression and not comparison.meets_target:
            raise typer.Exit(2)
        return

    print_section("Benchmark Competitive Report", f"workspace={workspace_path}")
    console.print(f"|  corpus_report={corpus_out}")
    console.print(f"|  bundle_report={bundle_path}")
    console.print(f"|  markdown_report={markdown_path}")
    console.print(f"|  gate_passed={'yes' if len(gate_failures) == 0 else 'no'}")
    console.print(f"|  comparison_passed={'yes' if comparison.meets_target else 'no'}")
    console.print(f"|  improvement={comparison.improvement_pct:.2f}%")
    if gate_failures:
        console.print("|  [red]Gate failures:[/red]")
        for item in gate_failures:
            console.print(f"|    - {item}")
    print_regressions_fn(console, list(comparison.regressions), prefix="|  ")
    print_footer()

    if fail_on_gate and gate_failures:
        raise typer.Exit(2)
    if fail_on_regression and not comparison.meets_target:
        raise typer.Exit(2)


def run_benchmark_release_gate(
    workspace: Optional[Path],
    local_iterations: int,
    corpus_iterations: int,
    baseline_report: Optional[Path],
    target_improvement_pct: float,
    require_comparison: bool,
    report_path: Optional[Path],
    breach_category: Optional[str],
    max_breaches: int,
    json_output: bool,
    fail_on_gate: bool,
    get_workspace_path_fn,
    load_benchmarks_settings_fn,
    filter_breach_lines_fn,
) -> None:
    """Run consolidated benchmark release gates in one command."""
    from clawlet.benchmarks import run_release_gate, write_release_gate_report

    workspace_path = workspace or get_workspace_path_fn()
    gates_cfg = load_benchmarks_settings_fn(workspace_path)

    report = run_release_gate(
        workspace=workspace_path,
        gates=gates_cfg.gates,
        local_iterations=local_iterations,
        corpus_iterations=corpus_iterations,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        require_comparison=require_comparison,
    )

    output = report_path or (workspace_path / "benchmark-release-gate-report.json")
    write_release_gate_report(output, report)

    breach_lines = list(report.gate_breaches or report.reasons)
    breach_lines, category_error = filter_breach_lines_fn(breach_lines, breach_category)
    if category_error:
        console.print(f"[red]{category_error}[/red]")
        raise typer.Exit(2)

    if json_output:
        payload = report.to_dict()
        payload["display_gate_breaches"] = breach_lines[:max_breaches]
        payload["display_max_breaches"] = max_breaches
        payload["display_breach_category"] = (breach_category or "").strip().lower()
        payload["report_path"] = str(output)
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        if fail_on_gate and not report.passed:
            raise typer.Exit(2)
        return

    print_section("Benchmark Release Gate", f"workspace={workspace_path}")
    console.print("|  Local benchmark:")
    console.print(
        "|    "
        f"p95={report.local_summary.p95_ms:.2f}ms "
        f"success={report.local_summary.success_rate:.2f}% "
        f"determinism={report.local_summary.deterministic_replay_pass_rate_pct:.2f}%"
    )
    console.print("|  Corpus benchmark:")
    console.print(
        "|    "
        f"p95={float(report.corpus_report.summary.get('p95_ms', 0.0)):.2f}ms "
        f"success={float(report.corpus_report.summary.get('success_rate', 0.0)):.2f}%"
    )
    console.print("|  Lane scheduling:")
    console.print(
        "|    "
        f"passed={'yes' if report.lane_scheduling.get('passed') else 'no'} "
        f"serial_ms={float(report.lane_scheduling.get('serial_elapsed_ms', 0.0)):.2f} "
        f"parallel_ms={float(report.lane_scheduling.get('parallel_elapsed_ms', 0.0)):.2f} "
        f"speedup={float(report.lane_scheduling.get('speedup_ratio', 0.0)):.2f}x"
    )
    console.print("|  Context cache:")
    console.print(
        "|    "
        f"passed={'yes' if report.context_cache.get('passed') else 'no'} "
        f"cold_ms={float(report.context_cache.get('cold_ms', 0.0)):.2f} "
        f"warm_ms={float(report.context_cache.get('warm_ms', 0.0)):.2f} "
        f"speedup={float(report.context_cache.get('speedup_ratio', 0.0)):.2f}x"
    )
    console.print("|  Coding loop:")
    console.print(
        "|    "
        f"passed={'yes' if report.coding_loop.get('passed') else 'no'} "
        f"success={float(report.coding_loop.get('success_rate', 0.0)):.2f}% "
        f"p95_total_ms={float(report.coding_loop.get('p95_total_ms', 0.0)):.2f}"
    )
    if report.comparison is not None:
        console.print("|  Baseline comparison:")
        console.print(
            "|    "
            f"improvement={report.comparison.improvement_pct:.2f}% "
            f"target={report.comparison.target_improvement_pct:.2f}% "
            f"meets_target={'yes' if report.comparison.meets_target else 'no'}"
        )
    if report.reasons:
        counts = report.breach_counts or {}
        if counts:
            compact = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            console.print(f"|  [red]Breach counts:[/red] {compact}")
        console.print("|  [red]Gate failures:[/red]")
        for reason in breach_lines[:max_breaches]:
            console.print(f"|    - {reason}")
    else:
        console.print("|  [green]All release gates passed[/green]")
    console.print(f"|  Report: {output}")
    print_footer()

    if fail_on_gate and not report.passed:
        raise typer.Exit(2)
