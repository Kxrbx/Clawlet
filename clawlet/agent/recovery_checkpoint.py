"""Checkpoint persistence helper for interrupted-run recovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from clawlet.runtime.recovery import RunCheckpoint


@dataclass(slots=True)
class RecoveryCheckpointService:
    recovery_manager: Any

    def save(
        self,
        *,
        run_id: str,
        session_id: str,
        channel: str,
        chat_id: str,
        stage: str,
        iteration: int,
        history: list[Any],
        user_id: str,
        user_name: str,
        tool_stats: dict[str, int],
        pending_confirmation: dict,
        notes: str,
    ) -> None:
        if not run_id or not session_id:
            return
        checkpoint = RunCheckpoint(
            run_id=run_id,
            session_id=session_id,
            channel=channel,
            chat_id=chat_id,
            stage=stage,
            iteration=iteration,
            user_message=history[-1].content if history and history[-1].role == "user" else "",
            user_id=user_id,
            user_name=user_name,
            tool_stats=dict(tool_stats),
            pending_confirmation=pending_confirmation,
            notes=notes,
        )
        self.recovery_manager.save(checkpoint)

    def complete(self, run_id: str) -> None:
        if not run_id:
            return
        self.recovery_manager.mark_completed(run_id)
