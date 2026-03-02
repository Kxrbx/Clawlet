"""Migration matrix analysis across multiple workspaces."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from clawlet.config_migration import ConfigMigrationReport, analyze_config_migration

_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".runtime",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}


@dataclass(slots=True)
class WorkspaceMigrationResult:
    workspace: str
    config_path: str
    issues: int
    errors: int
    warnings: int
    infos: int
    autofixable: int


@dataclass(slots=True)
class MigrationMatrixReport:
    root: str
    scanned: int
    with_issues: int
    with_errors: int
    total_issues: int
    total_errors: int
    total_warnings: int
    total_infos: int
    total_autofixable: int
    results: list[WorkspaceMigrationResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "scanned": self.scanned,
            "with_issues": self.with_issues,
            "with_errors": self.with_errors,
            "total_issues": self.total_issues,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "total_infos": self.total_infos,
            "total_autofixable": self.total_autofixable,
            "results": [asdict(item) for item in self.results],
        }


def run_migration_matrix(
    root: Path,
    *,
    pattern: str = "config.yaml",
    max_workspaces: int = 200,
) -> MigrationMatrixReport:
    """Scan multiple workspace configs and summarize migration readiness."""
    root = root.resolve()
    max_workspaces = max(1, int(max_workspaces))

    results: list[WorkspaceMigrationResult] = []
    total_issues = 0
    total_errors = 0
    total_warnings = 0
    total_infos = 0
    total_autofixable = 0
    with_issues = 0
    with_errors = 0

    seen: set[Path] = set()
    for config_path in _iter_candidate_configs(root, pattern):
        if len(results) >= max_workspaces:
            break
        config_path = config_path.resolve()
        if config_path in seen:
            continue
        seen.add(config_path)

        report: ConfigMigrationReport = analyze_config_migration(config_path)
        errors = len(report.errors)
        warnings = len(report.warnings)
        infos = len(report.infos)
        issues = len(report.issues)
        autofixable = sum(1 for i in report.issues if i.can_autofix)

        total_issues += issues
        total_errors += errors
        total_warnings += warnings
        total_infos += infos
        total_autofixable += autofixable
        if issues > 0:
            with_issues += 1
        if errors > 0:
            with_errors += 1

        results.append(
            WorkspaceMigrationResult(
                workspace=str(config_path.parent),
                config_path=str(config_path),
                issues=issues,
                errors=errors,
                warnings=warnings,
                infos=infos,
                autofixable=autofixable,
            )
        )

    return MigrationMatrixReport(
        root=str(root),
        scanned=len(results),
        with_issues=with_issues,
        with_errors=with_errors,
        total_issues=total_issues,
        total_errors=total_errors,
        total_warnings=total_warnings,
        total_infos=total_infos,
        total_autofixable=total_autofixable,
        results=results,
    )


def write_migration_matrix_report(path: Path, report: MigrationMatrixReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def run_migration_matrix_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    root = workdir / "migration-matrix-smoke"
    root.mkdir(parents=True, exist_ok=True)

    ws_ok = root / "ws-ok"
    ws_ok.mkdir(exist_ok=True)
    (ws_ok / "config.yaml").write_text(
        "provider:\n  primary: openrouter\n  openrouter:\n    api_key: test\n",
        encoding="utf-8",
    )

    ws_legacy = root / "ws-legacy"
    ws_legacy.mkdir(exist_ok=True)
    (ws_legacy / "config.yaml").write_text(
        "provider:\n  primary: openrouter\ntelegram:\n  enabled: true\nagent:\n  full_exec: true\n",
        encoding="utf-8",
    )

    report = run_migration_matrix(root, pattern="config.yaml", max_workspaces=10)
    if report.scanned < 2:
        errors.append("expected >= 2 scanned workspaces")
    if report.total_issues <= 0:
        errors.append("expected at least one migration issue")
    if report.with_issues <= 0:
        errors.append("expected at least one workspace with issues")

    return len(errors) == 0, errors


def _iter_candidate_configs(root: Path, pattern: str) -> Iterable[Path]:
    # Fast path for standard config name.
    if pattern == "config.yaml":
        for path in root.rglob("config.yaml"):
            if _is_excluded(path):
                continue
            yield path
        return

    for path in root.rglob(pattern):
        if _is_excluded(path):
            continue
        if path.is_file():
            yield path


def _is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    return any(item in parts for item in _EXCLUDED_DIRS)
