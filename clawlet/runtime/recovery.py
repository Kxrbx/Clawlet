"""Checkpoint and resume support for interrupted runs."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass(slots=True)
class RunCheckpoint:
    """Persisted snapshot for recovering interrupted runs."""

    run_id: str
    session_id: str
    channel: str
    chat_id: str
    stage: str
    iteration: int = 0
    user_message: str = ""
    user_id: str = ""
    user_name: str = ""
    tool_stats: dict[str, int] = field(default_factory=dict)
    pending_confirmation: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    updated_at: float = field(default_factory=time.time)


class RecoveryManager:
    """Stores run checkpoints and rebuilds resume payloads."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, checkpoint: RunCheckpoint) -> None:
        checkpoint.updated_at = time.time()
        path = self._path_for(checkpoint.run_id)
        path.write_text(json.dumps(asdict(checkpoint), indent=2), encoding="utf-8")

    def load(self, run_id: str) -> Optional[RunCheckpoint]:
        path = self._path_for(run_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return RunCheckpoint(
            run_id=str(data.get("run_id") or ""),
            session_id=str(data.get("session_id") or ""),
            channel=str(data.get("channel") or ""),
            chat_id=str(data.get("chat_id") or ""),
            stage=str(data.get("stage") or "unknown"),
            iteration=int(data.get("iteration") or 0),
            user_message=str(data.get("user_message") or ""),
            user_id=str(data.get("user_id") or ""),
            user_name=str(data.get("user_name") or ""),
            tool_stats=dict(data.get("tool_stats") or {}),
            pending_confirmation=dict(data.get("pending_confirmation") or {}),
            notes=str(data.get("notes") or ""),
            updated_at=float(data.get("updated_at") or time.time()),
        )

    def mark_completed(self, run_id: str) -> None:
        path = self._path_for(run_id)
        if path.exists():
            path.unlink()

    def list_active(self, limit: int = 100) -> list[RunCheckpoint]:
        checkpoints: list[RunCheckpoint] = []
        for path in sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            cp = self.load(path.stem)
            if cp is None:
                continue
            checkpoints.append(cp)
            if len(checkpoints) >= limit:
                break
        return checkpoints

    def build_resume_message(self, run_id: str) -> Optional[dict[str, Any]]:
        checkpoint = self.load(run_id)
        if checkpoint is None:
            return None

        prompt = (
            "Recovery resume: continue from interrupted run. "
            f"run_id={checkpoint.run_id} stage={checkpoint.stage} iteration={checkpoint.iteration}.\n"
            f"Original user request: {checkpoint.user_message}\n"
            "Continue execution safely from the last known state."
        )

        return {
            "channel": checkpoint.channel,
            "chat_id": checkpoint.chat_id,
            "content": prompt,
            "user_id": checkpoint.user_id or None,
            "user_name": checkpoint.user_name or None,
            "metadata": {
                "recovery_resume": True,
                "recovery_run_id": checkpoint.run_id,
                "recovery_stage": checkpoint.stage,
                "recovery_iteration": checkpoint.iteration,
            },
        }

    def _path_for(self, run_id: str) -> Path:
        return self.directory / f"{run_id}.json"
