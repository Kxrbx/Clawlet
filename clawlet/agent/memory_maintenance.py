"""Automatic memory consolidation (slow loop, deterministic, no LLM).

Runs at most once per interval (default 24h) and promotes durable items
from recent daily notes into curated long-term memory via the existing
``MemoryManager.curate_from_recent_daily_notes`` primitive. Progress is
tracked in a tiny state file so restarts don't reset the cadence. Never
raises — maintenance must not break the heartbeat tick.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger


def _read_last_run(state_path: Path) -> datetime | None:
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        return datetime.fromisoformat(str(raw.get("last_run", "")))
    except Exception:
        return None


def _write_last_run(state_path: Path, now: datetime) -> None:
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"last_run": now.isoformat()}), encoding="utf-8"
        )
    except Exception as e:
        logger.debug(f"Could not persist memory maintenance state: {e}")


async def maybe_run_memory_maintenance(
    memory_manager: Any,
    memory_dir: Path | str,
    *,
    now: datetime | None = None,
    interval_hours: float = 24,
) -> list[str]:
    """Curate daily notes into durable memory if the interval elapsed.

    Returns the promoted entries (empty when skipped or nothing found).
    """
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    state_path = Path(memory_dir) / "maintenance-state.json"
    last_run = _read_last_run(state_path)
    if last_run is not None:
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=UTC)
        if now - last_run < timedelta(hours=interval_hours):
            return []
    try:
        promoted = await memory_manager.curate_from_recent_daily_notes()
    except Exception as e:
        logger.warning(f"Memory maintenance failed: {e}")
        return []
    _write_last_run(state_path, now)
    if promoted:
        logger.info(f"Memory maintenance promoted {len(promoted)} entries")
    return list(promoted or [])
