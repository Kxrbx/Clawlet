"""Benchmark command registration for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import typer

from clawlet.cli.benchmark_ui import (
    run_benchmark_compare,
    run_benchmark_competitive_report,
    run_benchmark_coding_loop,
    run_benchmark_corpus,
    run_benchmark_context_cache,
    run_benchmark_lanes,
    run_benchmark_publish_report,
    run_benchmark_release_gate,
    run_benchmark_remote_health,
    run_benchmark_remote_parity,
    run_benchmark_run,
)


def register_benchmark_commands(
    benchmark_app: typer.Typer,
    *,
    get_workspace_path_fn: Callable[[], Path],
    load_benchmarks_settings_fn,
    print_corpus_comparison_summary_fn,
    corpus_comparison_payload_fn,
    print_regressions_fn,
    filter_breach_lines_fn,
) -> None:
    @benchmark_app.command("run")
    def benchmark_run(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        iterations: int = typer.Option(25, "--iterations", min=5, max=500, help="Benchmark iterations"),
        report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
        fail_on_gate: bool = typer.Option(False, "--fail-on-gate", help="Exit non-zero when quality gates fail"),
    ):
        """Run local performance benchmark and evaluate quality gates."""
        run_benchmark_run(
            workspace=workspace,
            iterations=iterations,
            report_path=report_path,
            fail_on_gate=fail_on_gate,
            get_workspace_path_fn=get_workspace_path_fn,
            load_benchmarks_settings_fn=load_benchmarks_settings_fn,
        )

    @benchmark_app.command("remote-health")
    def benchmark_remote_health(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Check configured remote worker health endpoint."""
        run_benchmark_remote_health(workspace=workspace, get_workspace_path_fn=get_workspace_path_fn)

    @benchmark_app.command("remote-parity")
    def benchmark_remote_parity(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    ):
        """Run remote/local execution parity smokecheck."""
        run_benchmark_remote_parity(workspace=workspace, get_workspace_path_fn=get_workspace_path_fn)

    @benchmark_app.command("lanes")
    def benchmark_lanes(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    ):
        """Run lane scheduling benchmark (serial vs parallel)."""
        run_benchmark_lanes(workspace=workspace, report_path=report_path, get_workspace_path_fn=get_workspace_path_fn)

    @benchmark_app.command("context-cache")
    def benchmark_context_cache(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    ):
        """Run context-engine warm-cache vs cold-cache benchmark."""
        run_benchmark_context_cache(
            workspace=workspace,
            report_path=report_path,
            get_workspace_path_fn=get_workspace_path_fn,
        )

    @benchmark_app.command("coding-loop")
    def benchmark_coding_loop(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        iterations: int = typer.Option(10, "--iterations", min=1, max=200, help="Benchmark iterations"),
        report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
    ):
        """Run coding-loop benchmark (inspect -> patch -> verify -> summarize)."""
        run_benchmark_coding_loop(
            workspace=workspace,
            iterations=iterations,
            report_path=report_path,
            get_workspace_path_fn=get_workspace_path_fn,
        )

    @benchmark_app.command("corpus")
    def benchmark_corpus(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        iterations: int = typer.Option(10, "--iterations", min=1, max=200, help="Iterations per scenario"),
        report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path"),
        baseline_report: Optional[Path] = typer.Option(
            None,
            "--baseline-report",
            help="Optional baseline report JSON (previous Clawlet run or another saved baseline)",
        ),
        target_improvement_pct: float = typer.Option(
            35.0,
            "--target-improvement-pct",
            min=0.0,
            max=100.0,
            help="Required p95 improvement percent vs baseline",
        ),
        fail_on_gate: bool = typer.Option(False, "--fail-on-gate", help="Exit non-zero when quality gates fail"),
        fail_on_regression: bool = typer.Option(
            False,
            "--fail-on-regression",
            help="Exit non-zero on baseline regressions or target miss",
        ),
        publish_report: bool = typer.Option(
            False,
            "--publish-report",
            help="Generate a publishable markdown report (requires --baseline-report)",
        ),
        publish_report_path: Optional[Path] = typer.Option(
            None,
            "--publish-report-path",
            help="Output markdown report path (default: benchmark-report.md in workspace)",
        ),
    ):
        """Run the standard corpus and optional baseline comparison."""
        run_benchmark_corpus(
            workspace=workspace,
            iterations=iterations,
            report_path=report_path,
            baseline_report=baseline_report,
            target_improvement_pct=target_improvement_pct,
            fail_on_gate=fail_on_gate,
            fail_on_regression=fail_on_regression,
            publish_report=publish_report,
            publish_report_path=publish_report_path,
            get_workspace_path_fn=get_workspace_path_fn,
            load_benchmarks_settings_fn=load_benchmarks_settings_fn,
            print_corpus_comparison_summary_fn=print_corpus_comparison_summary_fn,
        )

    @benchmark_app.command("compare")
    def benchmark_compare(
        current_report: Path = typer.Option(..., "--current-report", help="Current corpus report JSON"),
        baseline_report: Path = typer.Option(..., "--baseline-report", help="Baseline corpus report JSON"),
        target_improvement_pct: float = typer.Option(
            35.0,
            "--target-improvement-pct",
            min=0.0,
            max=100.0,
            help="Required p95 improvement percent vs baseline",
        ),
        fail_on_regression: bool = typer.Option(
            True,
            "--fail-on-regression",
            help="Exit non-zero on regressions or target miss",
        ),
        publish_report_path: Optional[Path] = typer.Option(
            None,
            "--publish-report-path",
            help="Optional markdown report output path",
        ),
        json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
    ):
        """Compare two saved corpus reports."""
        run_benchmark_compare(
            current_report=current_report,
            baseline_report=baseline_report,
            target_improvement_pct=target_improvement_pct,
            fail_on_regression=fail_on_regression,
            publish_report_path=publish_report_path,
            json_output=json_output,
            print_corpus_comparison_summary_fn=print_corpus_comparison_summary_fn,
            corpus_comparison_payload_fn=corpus_comparison_payload_fn,
        )

    @benchmark_app.command("publish-report")
    def benchmark_publish_report(
        current_report: Path = typer.Option(..., "--current-report", help="Current corpus report JSON"),
        baseline_report: Path = typer.Option(..., "--baseline-report", help="Baseline corpus report JSON"),
        out: Path = typer.Option(Path("benchmark-report.md"), "--out", help="Output markdown report path"),
        target_improvement_pct: float = typer.Option(
            35.0,
            "--target-improvement-pct",
            min=0.0,
            max=100.0,
            help="Required p95 improvement percent vs baseline",
        ),
        fail_on_regression: bool = typer.Option(
            True,
            "--fail-on-regression",
            help="Exit non-zero on regressions or target miss",
        ),
        json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
    ):
        """Generate publishable markdown report from current/baseline corpus reports."""
        run_benchmark_publish_report(
            current_report=current_report,
            baseline_report=baseline_report,
            out=out,
            target_improvement_pct=target_improvement_pct,
            fail_on_regression=fail_on_regression,
            json_output=json_output,
            print_regressions_fn=print_regressions_fn,
            corpus_comparison_payload_fn=corpus_comparison_payload_fn,
        )

    @benchmark_app.command("competitive-report")
    def benchmark_competitive_report(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        iterations: int = typer.Option(10, "--iterations", min=1, max=200, help="Iterations per scenario"),
        baseline_report: Path = typer.Option(..., "--baseline-report", help="Baseline corpus report JSON"),
        target_improvement_pct: float = typer.Option(
            35.0,
            "--target-improvement-pct",
            min=0.0,
            max=100.0,
            help="Required p95 improvement percent vs baseline",
        ),
        corpus_report_out: Optional[Path] = typer.Option(
            None,
            "--corpus-report-out",
            help="Optional current corpus report JSON output path",
        ),
        bundle_out: Optional[Path] = typer.Option(
            None,
            "--bundle-out",
            help="Optional machine-readable competitive bundle JSON output path",
        ),
        markdown_out: Optional[Path] = typer.Option(
            None,
            "--markdown-out",
            help="Optional publishable markdown output path",
        ),
        json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
        fail_on_gate: bool = typer.Option(True, "--fail-on-gate"),
        fail_on_regression: bool = typer.Option(True, "--fail-on-regression"),
    ):
        """Run corpus benchmark + baseline comparison and emit publishable artifacts."""
        run_benchmark_competitive_report(
            workspace=workspace,
            iterations=iterations,
            baseline_report=baseline_report,
            target_improvement_pct=target_improvement_pct,
            corpus_report_out=corpus_report_out,
            bundle_out=bundle_out,
            markdown_out=markdown_out,
            json_output=json_output,
            fail_on_gate=fail_on_gate,
            fail_on_regression=fail_on_regression,
            get_workspace_path_fn=get_workspace_path_fn,
            load_benchmarks_settings_fn=load_benchmarks_settings_fn,
            print_regressions_fn=print_regressions_fn,
        )

    @benchmark_app.command("release-gate")
    def benchmark_release_gate(
        workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
        local_iterations: int = typer.Option(
            25,
            "--local-iterations",
            min=1,
            max=500,
            help="Iterations for local runtime benchmark",
        ),
        corpus_iterations: int = typer.Option(
            10,
            "--corpus-iterations",
            min=1,
            max=200,
            help="Iterations per corpus scenario",
        ),
        baseline_report: Optional[Path] = typer.Option(
            None,
            "--baseline-report",
            help="Optional baseline corpus report for superiority comparison",
        ),
        target_improvement_pct: float = typer.Option(
            35.0,
            "--target-improvement-pct",
            min=0.0,
            max=100.0,
            help="Required p95 improvement vs baseline",
        ),
        require_comparison: bool = typer.Option(
            False,
            "--require-comparison",
            help="Fail gate when --baseline-report is not provided",
        ),
        report_path: Optional[Path] = typer.Option(
            None,
            "--report",
            help="Optional JSON report output path",
        ),
        breach_category: Optional[str] = typer.Option(
            None,
            "--breach-category",
            help="Filter displayed gate breaches by category: local|corpus|lane|context|coding|rust|comparison|other",
        ),
        max_breaches: int = typer.Option(
            8,
            "--max-breaches",
            min=1,
            max=100,
            help="Maximum number of breach lines to display",
        ),
        json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON summary to stdout"),
        fail_on_gate: bool = typer.Option(
            True,
            "--fail-on-gate",
            help="Exit non-zero when any release gate fails",
        ),
    ):
        """Run consolidated benchmark release gates in one command."""
        run_benchmark_release_gate(
            workspace=workspace,
            local_iterations=local_iterations,
            corpus_iterations=corpus_iterations,
            baseline_report=baseline_report,
            target_improvement_pct=target_improvement_pct,
            require_comparison=require_comparison,
            report_path=report_path,
            breach_category=breach_category,
            max_breaches=max_breaches,
            json_output=json_output,
            fail_on_gate=fail_on_gate,
            get_workspace_path_fn=get_workspace_path_fn,
            load_benchmarks_settings_fn=load_benchmarks_settings_fn,
            filter_breach_lines_fn=filter_breach_lines_fn,
        )
