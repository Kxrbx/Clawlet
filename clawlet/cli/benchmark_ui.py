"""Benchmark command helpers for the CLI."""

from __future__ import annotations

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
