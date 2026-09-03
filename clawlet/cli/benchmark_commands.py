"""Benchmark command registration for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import typer

from clawlet.cli.benchmark_ui import (
    run_benchmark_corpus,
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
            publish_report=False,
            publish_report_path=None,
            get_workspace_path_fn=get_workspace_path_fn,
            load_benchmarks_settings_fn=load_benchmarks_settings_fn,
            print_corpus_comparison_summary_fn=print_corpus_comparison_summary_fn,
        )
