"""Release-readiness CLI helper."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from clawlet.cli.benchmark_utils import load_benchmarks_settings
from clawlet.cli.common_ui import _filter_breach_lines, print_footer, print_section

console = Console()


def run_release_readiness_command(
    workspace: Optional[Path],
    local_iterations: int,
    corpus_iterations: int,
    baseline_report: Optional[Path],
    target_improvement_pct: float,
    require_comparison: bool,
    migration_root: Optional[Path],
    migration_pattern: str,
    migration_max_workspaces: int,
    check_remote_health: bool,
    breach_category: Optional[str],
    max_breaches: int,
    json_output: bool,
    report_path: Optional[Path],
    fail_on_not_ready: bool,
    get_workspace_path_fn,
) -> None:
    """Run consolidated release-readiness checks and render results."""
    from clawlet.config import load_config
    from clawlet.release_readiness import (
        run_release_readiness,
        summarize_gate_breaches,
        write_release_readiness_report,
    )

    workspace_path = workspace or get_workspace_path_fn()
    gates_cfg = load_benchmarks_settings(workspace_path)

    plugin_dirs = [workspace_path / "plugins"]
    remote_endpoint = ""
    remote_api_key = ""
    remote_timeout_seconds = 60.0
    try:
        cfg = load_config(workspace_path)
        plugin_dirs = []
        for raw_dir in cfg.plugins.directories:
            p = Path(raw_dir).expanduser()
            if not p.is_absolute():
                p = workspace_path / p
            plugin_dirs.append(p)
        remote_endpoint = str(getattr(cfg.runtime.remote, "endpoint", "") or "")
        remote_timeout_seconds = float(getattr(cfg.runtime.remote, "timeout_seconds", 60.0) or 60.0)
        api_env = str(getattr(cfg.runtime.remote, "api_key_env", "CLAWLET_REMOTE_API_KEY") or "CLAWLET_REMOTE_API_KEY")
        remote_api_key = os.environ.get(api_env, "")
    except Exception:
        pass

    report = run_release_readiness(
        workspace=workspace_path,
        benchmark_gates=gates_cfg.gates,
        local_iterations=local_iterations,
        corpus_iterations=corpus_iterations,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        require_comparison=require_comparison,
        migration_root=migration_root,
        migration_pattern=migration_pattern,
        migration_max_workspaces=migration_max_workspaces,
        plugin_dirs=plugin_dirs,
        check_remote_health=check_remote_health,
        remote_endpoint=remote_endpoint,
        remote_api_key=remote_api_key,
        remote_timeout_seconds=remote_timeout_seconds,
    )

    rg = report.release_gate or {}
    local = rg.get("local_summary") or {}
    lane = report.lane_scheduling or {}
    context = report.context_cache or {}
    coding = report.coding_loop or {}
    gate_breaches = list(report.gate_breaches or [])[:max_breaches]
    if not gate_breaches:
        gate_breaches = summarize_gate_breaches(report, max_items=max_breaches)
    gate_breaches, category_error = _filter_breach_lines(gate_breaches, breach_category)
    if category_error:
        console.print(f"[red]{category_error}[/red]")
        raise typer.Exit(2)
    breach_counts = dict(report.breach_counts or {})

    output = report_path or (workspace_path / "release-readiness-report.json")
    write_release_readiness_report(output, report)

    if json_output:
        payload = report.to_dict()
        payload["display_gate_breaches"] = gate_breaches
        payload["display_max_breaches"] = max_breaches
        payload["display_breach_category"] = (breach_category or "").strip().lower()
        payload["report_path"] = str(output)
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        if fail_on_not_ready and not report.passed:
            raise typer.Exit(2)
        return

    print_section("Release Readiness", str(workspace_path))
    console.print(f"|  passed={'yes' if report.passed else 'no'}")
    console.print(f"|  release_gate={'yes' if report.release_gate_passed else 'no'}")
    console.print(f"|  migration_matrix={'yes' if report.migration_matrix_passed else 'no'}")
    console.print(f"|  plugin_matrix={'yes' if report.plugin_matrix_passed else 'no'}")
    console.print(f"|  lane_scheduling={'yes' if report.lane_scheduling_passed else 'no'}")
    console.print(f"|  context_cache={'yes' if report.context_cache_passed else 'no'}")
    console.print(f"|  coding_loop={'yes' if report.coding_loop_passed else 'no'}")
    console.print(f"|  remote_health={'yes' if report.remote_health_passed else 'no'}")
    if local or lane or context or coding or rust:
        console.print("|  Metrics:")
        if local:
            console.print(
                "|    "
                f"local_p95_ms={float(local.get('p95_ms', 0.0)):.2f} "
                f"local_success={float(local.get('success_rate', 0.0)):.2f}% "
                f"local_determinism={float(local.get('deterministic_replay_pass_rate_pct', 0.0)):.2f}%"
            )
        if lane:
            console.print(
                "|    "
                f"lane_parallel_ms={float(lane.get('parallel_elapsed_ms', 0.0)):.2f} "
                f"lane_speedup={float(lane.get('speedup_ratio', 0.0)):.2f}x"
            )
        if context:
            console.print(
                "|    "
                f"context_warm_ms={float(context.get('warm_ms', 0.0)):.2f} "
                f"context_speedup={float(context.get('speedup_ratio', 0.0)):.2f}x"
            )
        if coding:
            console.print(
                "|    "
                f"coding_success={float(coding.get('success_rate', 0.0)):.2f}% "
                f"coding_p95_total_ms={float(coding.get('p95_total_ms', 0.0)):.2f}"
            )
    if breach_counts:
        compact = ", ".join(f"{k}={v}" for k, v in sorted(breach_counts.items()))
        console.print(f"|  [red]Breach counts:[/red] {compact}")
    if gate_breaches:
        console.print("|  [red]Gate Breaches:[/red]")
        for item in gate_breaches:
            console.print(f"|    - {item}")
    if report.reasons:
        console.print("|  [red]Reasons:[/red]")
        for reason in report.reasons:
            console.print(f"|    - {reason}")

    console.print(f"|  Report: {output}")
    print_footer()

    if fail_on_not_ready and not report.passed:
        raise typer.Exit(2)
