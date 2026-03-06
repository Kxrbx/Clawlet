"""Migration CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from clawlet.cli.common_ui import print_footer, print_section

console = Console()


def run_migrate_config(workspace_path: Path, write: bool, backup: bool) -> None:
    """Analyze and optionally autofix legacy config keys."""
    from clawlet.config_migration import analyze_config_migration, apply_config_migration_autofix

    config_path = workspace_path / "config.yaml"
    print_section("Config Migration", str(config_path))

    analysis = analyze_config_migration(config_path)
    if analysis.issues:
        console.print(f"|  Detected {len(analysis.issues)} issue(s):")
        for issue in analysis.issues:
            mark = "x" if issue.severity == "error" else ("!" if issue.severity == "warning" else "i")
            auto = " (autofixable)" if issue.can_autofix else ""
            console.print(f"|   {mark} {issue.severity.upper()} {issue.path}: {issue.message}{auto}")
            console.print(f"|      hint: {issue.hint}")
    else:
        console.print("|  No migration issues detected")

    result = apply_config_migration_autofix(config_path, write=write, create_backup=backup)
    console.print("|")
    mode = "write" if write else "dry-run"
    console.print(f"|  Autofix mode: {mode}")
    console.print(f"|  Changes available: {'yes' if result.changed else 'no'}")
    if result.actions:
        for action in result.actions:
            console.print(f"|   - {action}")
    if write and result.changed and result.backup_path:
        console.print(f"|  Backup: {result.backup_path}")

    print_footer()

    if analysis.has_blockers:
        raise typer.Exit(2)


def run_migration_matrix(
    root: Path,
    pattern: str,
    max_workspaces: int,
    report_path: Optional[Path],
    fail_on_errors: bool,
) -> None:
    """Scan many workspaces and report migration compatibility readiness."""
    from clawlet.config_migration_matrix import run_migration_matrix, write_migration_matrix_report

    report = run_migration_matrix(root=root, pattern=pattern, max_workspaces=max_workspaces)
    print_section("Migration Matrix", f"root={root.resolve()}")
    console.print(
        "|  "
        f"scanned={report.scanned} with_issues={report.with_issues} with_errors={report.with_errors}"
    )
    console.print(
        "|  "
        f"issues={report.total_issues} errors={report.total_errors} "
        f"warnings={report.total_warnings} infos={report.total_infos} "
        f"autofixable={report.total_autofixable}"
    )
    if report.results:
        console.print("|")
        top = sorted(report.results, key=lambda r: (r.errors, r.issues), reverse=True)[:20]
        for item in top:
            console.print(
                "|  "
                f"{item.workspace}: issues={item.issues} errors={item.errors} "
                f"warnings={item.warnings} autofixable={item.autofixable}"
            )

    output = report_path or (Path(root).resolve() / "migration-matrix-report.json")
    write_migration_matrix_report(output, report)
    console.print(f"|  Report: {output}")
    print_footer()

    if fail_on_errors and report.with_errors > 0:
        raise typer.Exit(2)


def run_migrate_heartbeat(workspace_path: Path, write: bool) -> None:
    """Normalize legacy heartbeat keys into canonical heartbeat schema."""
    import yaml

    config_path = workspace_path / "config.yaml"
    print_section("Heartbeat Migration", str(config_path))
    if not config_path.exists():
        console.print("|  [red]x[/red] Config file not found")
        print_footer()
        raise typer.Exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    hb = dict(raw.get("heartbeat") or {})
    changes: list[str] = []

    # Legacy: heartbeat.every ("2h", "30m") -> interval_minutes
    every = hb.get("every")
    if every and "interval_minutes" not in hb:
        from clawlet.heartbeat.cron_scheduler import parse_interval

        try:
            td = parse_interval(str(every))
            minutes = max(1, int(td.total_seconds() // 60))
            hb["interval_minutes"] = minutes
            changes.append(f"heartbeat.every -> heartbeat.interval_minutes ({minutes})")
        except Exception as e:
            console.print(f"|  [yellow]![/yellow] Could not parse heartbeat.every='{every}': {e}")

    # Legacy: heartbeat.active_hours {start,end} OR "9-18" -> quiet hours inverse.
    active = hb.get("active_hours")
    start = None
    end = None
    if isinstance(active, dict):
        start = active.get("start")
        end = active.get("end")
    elif isinstance(active, str) and "-" in active:
        left, right = active.split("-", 1)
        try:
            start = int(left.strip())
            end = int(right.strip())
        except ValueError:
            start = None
            end = None
    if isinstance(start, int) and isinstance(end, int):
        hb["quiet_hours_start"] = int(end) % 24
        hb["quiet_hours_end"] = int(start) % 24
        changes.append(
            "heartbeat.active_hours -> heartbeat.quiet_hours_start/quiet_hours_end "
            f"({hb['quiet_hours_start']}/{hb['quiet_hours_end']})"
        )

    if "every" in hb:
        hb.pop("every", None)
        changes.append("removed legacy heartbeat.every")
    if "active_hours" in hb:
        hb.pop("active_hours", None)
        changes.append("removed legacy heartbeat.active_hours")

    if not changes:
        console.print("|  No heartbeat migration changes needed")
        print_footer()
        return

    console.print("|  Proposed changes:")
    for c in changes:
        console.print(f"|   - {c}")

    if write:
        raw["heartbeat"] = hb
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw, f, sort_keys=False)
        console.print("|  [green]OK[/green] Applied changes to config.yaml")
    else:
        console.print("|  [dim]Dry-run only. Use --write to apply.[/dim]")

    print_footer()
