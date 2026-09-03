"""One-shot v1 -> v2 migration helper (dry-run by default).

What it does:
- Loads a v1 ``config.yaml`` and reports breaking-change issues:
  - ``runtime.engine: hybrid_rust`` (removed in v2, must be ``python``)
  - missing ``orchestrator`` / ``task_profiles`` sections (new in v2,
    optional — built-ins apply when absent)
  - validates the file against the v2 :class:`Config` schema
- With ``--write``: fixes ``hybrid_rust`` -> ``python`` in place
  (backup ``config.yaml.bak`` first) and re-validates.

Usage:
    python scripts/migrate_v1_to_v2.py [--workspace PATH] [--write]

Session/message databases need no migration: SessionDB tables are created
alongside the existing ``messages`` table in the same ``clawlet.db``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml


def _iter_config_paths(workspace: Path) -> list[Path]:
    paths = [workspace / "config.yaml"]
    workspaces_dir = workspace / "workspaces"
    if workspaces_dir.is_dir():
        paths.extend(sorted(workspaces_dir.glob("*/config.yaml")))
    return [p for p in paths if p.exists()]


def analyze(path: Path) -> list[str]:
    """Return human-readable migration issues for one config file."""
    issues: list[str] = []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return [f"{path}: unreadable YAML ({e})"]
    runtime = raw.get("runtime") or {}
    if str(runtime.get("engine", "")).strip().lower() == "hybrid_rust":
        issues.append(
            f"{path}: runtime.engine 'hybrid_rust' was removed in v2 "
            "(use --write to normalize to 'python')"
        )
    if "orchestrator" not in raw:
        issues.append(f"{path}: no 'orchestrator' section (built-in defaults apply)")
    if "task_profiles" not in raw:
        issues.append(
            f"{path}: no 'task_profiles' section (built-in per-task defaults apply)"
        )
    try:
        from clawlet.config import Config

        Config(**Config._substitute_env_vars(raw))
    except Exception as e:
        issues.append(f"{path}: fails v2 schema validation ({e})")
    return issues


def fix_file(path: Path) -> bool:
    """Normalize legacy keys in place. Returns True when the file changed."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    changed = False
    runtime = raw.get("runtime")
    if (
        isinstance(runtime, dict)
        and str(runtime.get("engine", "")).strip().lower() == "hybrid_rust"
    ):
        runtime["engine"] = "python"
        changed = True
    if changed:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        path.write_text(yaml.dump(raw, default_flow_style=False), encoding="utf-8")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate Clawlet v1 configs to v2")
    parser.add_argument("--workspace", default="~/.clawlet", help="Workspace directory")
    parser.add_argument(
        "--write", action="store_true", help="Apply fixes in place (backup first)"
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).expanduser()
    paths = _iter_config_paths(workspace)
    if not paths:
        print(f"No config.yaml found under {workspace}")
        return 1

    exit_code = 0
    for path in paths:
        issues = analyze(path)
        if not issues:
            print(f"OK   {path}")
            continue
        exit_code = 2
        for issue in issues:
            print(f"WARN {issue}")
        if args.write and any("hybrid_rust" in i for i in issues):
            if fix_file(path):
                print(f"FIX  {path}: engine normalized to 'python' (backup kept)")
                remaining = [
                    i for i in analyze(path) if "hybrid_rust" in i or "fails v2" in i
                ]
                if remaining:
                    for issue in remaining:
                        print(f"WARN {issue}")
                else:
                    print(f"OK   {path}: now validates against the v2 schema")
    if exit_code == 0:
        print("All configs are v2-ready.")
    elif not args.write:
        print("Re-run with --write to auto-fix what's fixable.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
