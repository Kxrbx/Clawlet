"""Replay retention cleanup for runtime events and checkpoints."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(slots=True)
class RetentionCleanupReport:
    replay_dir: str
    retention_days: int
    event_lines_total: int
    event_lines_kept: int
    event_lines_removed: int
    event_lines_malformed: int
    checkpoints_total: int
    checkpoints_kept: int
    checkpoints_removed: int
    dry_run: bool


def cleanup_replay_artifacts(
    replay_dir: Path,
    retention_days: int,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> RetentionCleanupReport:
    """Prune old runtime replay events and stale checkpoints."""
    retention_days = max(1, int(retention_days))
    now_dt = now or datetime.now(timezone.utc)
    cutoff = now_dt - timedelta(days=retention_days)
    cutoff_epoch = cutoff.timestamp()

    replay_dir = replay_dir.expanduser().resolve()
    events_path = replay_dir / "events.jsonl"
    checkpoints_dir = replay_dir / "checkpoints"

    event_total = 0
    event_kept = 0
    event_removed = 0
    event_malformed = 0
    kept_lines: list[str] = []

    if events_path.exists():
        with events_path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line:
                    continue
                event_total += 1
                keep = True
                try:
                    obj = json.loads(line)
                    ts = _parse_timestamp(str(obj.get("timestamp") or ""))
                    if ts is not None and ts < cutoff:
                        keep = False
                except Exception:
                    # Keep malformed lines for forensic safety, but track them.
                    event_malformed += 1
                    keep = True

                if keep:
                    event_kept += 1
                    kept_lines.append(line)
                else:
                    event_removed += 1

        if not dry_run:
            _atomic_write_lines(events_path, kept_lines)

    checkpoints_total = 0
    checkpoints_kept = 0
    checkpoints_removed = 0

    if checkpoints_dir.exists():
        for path in checkpoints_dir.glob("*.json"):
            checkpoints_total += 1
            updated = _checkpoint_updated_at(path)
            if updated >= cutoff_epoch:
                checkpoints_kept += 1
                continue
            checkpoints_removed += 1
            if not dry_run:
                try:
                    path.unlink()
                except OSError:
                    checkpoints_kept += 1
                    checkpoints_removed -= 1

    return RetentionCleanupReport(
        replay_dir=str(replay_dir),
        retention_days=retention_days,
        event_lines_total=event_total,
        event_lines_kept=event_kept,
        event_lines_removed=event_removed,
        event_lines_malformed=event_malformed,
        checkpoints_total=checkpoints_total,
        checkpoints_kept=checkpoints_kept,
        checkpoints_removed=checkpoints_removed,
        dry_run=dry_run,
    )


def _parse_timestamp(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _checkpoint_updated_at(path: Path) -> float:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "updated_at" in data:
            return float(data["updated_at"])
    except Exception:
        pass
    return float(os.path.getmtime(path))


def _atomic_write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        if lines:
            f.write("\n".join(lines) + "\n")
    temp.replace(path)
