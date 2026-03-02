"""Replay retention smokecheck for CI hardening."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from clawlet.runtime import cleanup_replay_artifacts


def run_replay_retention_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    replay_dir = workdir / ".runtime-retention-smoke"
    checkpoints_dir = replay_dir / "checkpoints"
    replay_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    now = datetime(2026, 2, 27, tzinfo=timezone.utc)
    old = now - timedelta(days=45)
    new = now - timedelta(days=2)

    events_path = replay_dir / "events.jsonl"
    events_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "RunStarted",
                        "run_id": "old",
                        "session_id": "s1",
                        "timestamp": old.isoformat(),
                        "payload": {},
                    }
                ),
                json.dumps(
                    {
                        "event_type": "RunStarted",
                        "run_id": "new",
                        "session_id": "s2",
                        "timestamp": new.isoformat(),
                        "payload": {},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (checkpoints_dir / "old.json").write_text(
        json.dumps({"run_id": "old", "updated_at": old.timestamp()}),
        encoding="utf-8",
    )
    (checkpoints_dir / "new.json").write_text(
        json.dumps({"run_id": "new", "updated_at": new.timestamp()}),
        encoding="utf-8",
    )

    report = cleanup_replay_artifacts(replay_dir, retention_days=30, dry_run=False, now=now)

    if report.event_lines_removed != 1:
        errors.append(f"expected 1 old event line removed, got {report.event_lines_removed}")
    if report.checkpoints_removed != 1:
        errors.append(f"expected 1 old checkpoint removed, got {report.checkpoints_removed}")

    kept = events_path.read_text(encoding="utf-8")
    if '"run_id": "old"' in kept:
        errors.append("old run event was not pruned")
    if not (checkpoints_dir / "new.json").exists():
        errors.append("new checkpoint should remain after cleanup")
    if (checkpoints_dir / "old.json").exists():
        errors.append("old checkpoint should be pruned")

    # Also verify dry-run does not mutate artifacts using a separate fixture dir.
    replay_dir_dry = workdir / ".runtime-retention-smoke-dry"
    checkpoints_dir_dry = replay_dir_dry / "checkpoints"
    replay_dir_dry.mkdir(parents=True, exist_ok=True)
    checkpoints_dir_dry.mkdir(parents=True, exist_ok=True)
    events_path_dry = replay_dir_dry / "events.jsonl"
    events_path_dry.write_text(
        json.dumps(
            {
                "event_type": "RunStarted",
                "run_id": "dry-old",
                "session_id": "s1",
                "timestamp": old.isoformat(),
                "payload": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    dry_cp = checkpoints_dir_dry / "dry-old.json"
    dry_cp.write_text(json.dumps({"run_id": "dry-old", "updated_at": old.timestamp()}), encoding="utf-8")
    dry_report = cleanup_replay_artifacts(replay_dir_dry, retention_days=30, dry_run=True, now=now)
    if dry_report.event_lines_removed != 1:
        errors.append("dry-run should report old event removal")
    if '"run_id": "dry-old"' not in events_path_dry.read_text(encoding="utf-8"):
        errors.append("dry-run must not mutate events file")
    if not dry_cp.exists():
        errors.append("dry-run must not remove old checkpoint")

    return len(errors) == 0, errors
