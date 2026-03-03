"""Recovery command helpers for the CLI."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from clawlet.cli.common_ui import print_footer, print_section
from clawlet.cli.runtime_paths import resolve_replay_dir

console = Console()


def run_recovery_list(workspace_path: Path, limit: int) -> None:
    """List interrupted runs with available checkpoints."""
    from clawlet.runtime import RecoveryManager

    replay_dir = resolve_replay_dir(workspace_path)
    manager = RecoveryManager(replay_dir / "checkpoints")
    checkpoints = manager.list_active(limit=limit)

    print_section("Recovery", f"{len(checkpoints)} checkpoint(s)")
    if not checkpoints:
        console.print("|  [dim]No interrupted runs found[/dim]")
        print_footer()
        return

    for cp in checkpoints:
        console.print(
            f"|  run={cp.run_id} stage={cp.stage} iter={cp.iteration} "
            f"chat={cp.channel}/{cp.chat_id}"
        )
    print_footer()


def run_recovery_show(workspace_path: Path, run_id: str) -> None:
    """Show checkpoint details for one run id."""
    from clawlet.runtime import RecoveryManager

    replay_dir = resolve_replay_dir(workspace_path)
    manager = RecoveryManager(replay_dir / "checkpoints")
    cp = manager.load(run_id)
    print_section("Recovery", f"run={run_id}")
    if cp is None:
        console.print("|  [red]Checkpoint not found[/red]")
        print_footer()
        raise typer.Exit(1)

    console.print(f"|  session={cp.session_id}")
    console.print(f"|  stage={cp.stage}")
    console.print(f"|  iteration={cp.iteration}")
    console.print(f"|  channel={cp.channel}")
    console.print(f"|  chat_id={cp.chat_id}")
    console.print(f"|  notes={cp.notes}")
    if cp.pending_confirmation:
        console.print(f"|  pending_confirmation={cp.pending_confirmation}")
    print_footer()


def run_recovery_resume_payload(workspace_path: Path, run_id: str) -> None:
    """Render recovery inbound payload for manual resume orchestration."""
    from clawlet.runtime import RecoveryManager

    replay_dir = resolve_replay_dir(workspace_path)
    manager = RecoveryManager(replay_dir / "checkpoints")
    payload = manager.build_resume_message(run_id)
    if payload is None:
        console.print("[red]Checkpoint not found[/red]")
        raise typer.Exit(1)
    console.print(json.dumps(payload, indent=2))


def run_recovery_cleanup(
    workspace_path: Path,
    retention_days: int,
    dry_run: bool,
) -> None:
    """Prune replay events/checkpoints older than retention policy."""
    from clawlet.config import RuntimeSettings
    from clawlet.runtime import cleanup_replay_artifacts

    runtime_cfg = RuntimeSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            runtime_cfg = RuntimeSettings(**(raw.get("runtime") or {}))
        except Exception:
            pass

    replay_dir = resolve_replay_dir(workspace_path)

    effective_retention_days = int(retention_days or runtime_cfg.replay.retention_days)
    report = cleanup_replay_artifacts(
        replay_dir=replay_dir,
        retention_days=effective_retention_days,
        dry_run=dry_run,
    )

    print_section("Recovery Cleanup", f"retention_days={effective_retention_days} dry_run={str(dry_run).lower()}")
    console.print(f"|  replay_dir={report.replay_dir}")
    console.print(
        "|  events: "
        f"total={report.event_lines_total} kept={report.event_lines_kept} "
        f"removed={report.event_lines_removed} malformed={report.event_lines_malformed}"
    )
    console.print(
        "|  checkpoints: "
        f"total={report.checkpoints_total} kept={report.checkpoints_kept} "
        f"removed={report.checkpoints_removed}"
    )
    print_footer()
