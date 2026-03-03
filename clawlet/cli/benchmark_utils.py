"""Shared CLI helpers for benchmark and release-report commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from rich.console import Console


def load_benchmarks_settings(workspace_path: Path):
    from clawlet.config import BenchmarksSettings

    gates_cfg = BenchmarksSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            gates_cfg = BenchmarksSettings(**(raw.get("benchmarks") or {}))
        except Exception:
            pass
    return gates_cfg


def print_regressions(console: Console, regressions: list[str], prefix: str = "|  ") -> None:
    if not regressions:
        return
    console.print(f"{prefix}[red]Regressions:[/red]")
    for item in regressions:
        console.print(f"{prefix}  - {item}")


def print_corpus_comparison_summary(
    console: Console,
    comparison: Any,
    prefix: str = "|  ",
    include_p95: bool = True,
) -> None:
    console.print(f"{prefix}Baseline: {comparison.baseline_source}")
    if include_p95:
        console.print(f"{prefix}Baseline p95: {comparison.baseline_p95_ms:.2f} ms")
        console.print(f"{prefix}Current p95: {comparison.current_p95_ms:.2f} ms")
    console.print(
        f"{prefix}Improvement: {comparison.improvement_pct:.2f}% "
        f"(target {comparison.target_improvement_pct:.2f}%)"
    )
    console.print(f"{prefix}Meets target: {'yes' if comparison.meets_target else 'no'}")
    for row in comparison.scenario_comparisons:
        console.print(
            f"{prefix}{row.scenario_id}: "
            f"baseline_p95={row.baseline_p95_ms:.2f}ms "
            f"current_p95={row.current_p95_ms:.2f}ms "
            f"delta={row.improvement_pct:.2f}%"
        )
    print_regressions(console, list(comparison.regressions), prefix=prefix)


def corpus_comparison_payload(
    comparison: Any,
    current_report: Optional[Path] = None,
    baseline_report: Optional[Path] = None,
    publish_report_path: Optional[Path] = None,
) -> dict[str, Any]:
    payload = comparison.to_dict()
    if current_report is not None:
        payload["current_report"] = str(current_report)
    if baseline_report is not None:
        payload["baseline_report"] = str(baseline_report)
    if publish_report_path is not None:
        payload["publish_report_path"] = str(publish_report_path)
    return payload
