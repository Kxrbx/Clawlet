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
