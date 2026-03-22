"""Run lifecycle helpers for start/completion events and outbound metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class RunLifecycle:
    emit_runtime_event: Callable[[str, str, dict], None]
    save_checkpoint: Callable[..., None]
    complete_checkpoint: Callable[[], None]
    metrics_factory: Callable[[], Any]
    event_run_started: str
    event_run_completed: str
    event_scheduled_run_started: str
    event_scheduled_run_completed: str
    event_scheduled_run_failed: str
    sched_payload_job_id: str
    sched_payload_run_id: str
    sched_payload_session_target: str
    sched_payload_wake_mode: str
    _active_runs: set[str] = field(default_factory=set)

    def build_outbound_metadata(
        self,
        *,
        source: str,
        is_heartbeat: bool,
        heartbeat_ack_max_chars: int,
        scheduled_payload: dict | None,
        extra: dict | None = None,
    ) -> dict:
        metadata = {
            "source": source,
            "heartbeat": is_heartbeat,
            "ack_max_chars": heartbeat_ack_max_chars,
            self.sched_payload_job_id: scheduled_payload.get(self.sched_payload_job_id) if scheduled_payload else "",
            self.sched_payload_run_id: scheduled_payload.get(self.sched_payload_run_id) if scheduled_payload else "",
            self.sched_payload_session_target: scheduled_payload.get(self.sched_payload_session_target) if scheduled_payload else "",
            self.sched_payload_wake_mode: scheduled_payload.get(self.sched_payload_wake_mode) if scheduled_payload else "",
        }
        if extra:
            metadata.update(extra)
        return metadata

    def start_run(
        self,
        *,
        run_id: str,
        session_id: str,
        channel: str,
        chat_id: str,
        engine: str,
        engine_resolved: str,
        source: str,
        is_heartbeat: bool,
        message_preview: str,
        metadata: dict,
        scheduled_payload: dict | None,
    ) -> None:
        self._active_runs.add(run_id)
        self.save_checkpoint(stage="run_started", iteration=0, notes="Inbound message accepted")
        self.emit_runtime_event(
            self.event_run_started,
            session_id=session_id,
            payload={
                "channel": channel,
                "chat_id": chat_id,
                "engine": engine,
                "engine_resolved": engine_resolved,
                "recovery_resume_from": metadata.get("recovery_run_id", ""),
                "recovery_resume": bool(metadata.get("recovery_resume")),
                "source": source,
                "heartbeat": is_heartbeat,
                "message_preview": message_preview[:200],
            },
        )
        if scheduled_payload is not None:
            self.emit_runtime_event(
                self.event_scheduled_run_started,
                session_id=session_id,
                payload=scheduled_payload,
            )

    def complete_run(
        self,
        *,
        run_id: str,
        session_id: str,
        iterations: int,
        is_error: bool,
        response_text: str,
        scheduled_payload: dict | None,
        extra_payload: dict | None = None,
    ) -> None:
        if run_id not in self._active_runs:
            return
        if is_error:
            self.metrics_factory().inc_errors()
            self.save_checkpoint(stage="interrupted", iteration=iterations, notes=response_text[:400])
        else:
            self.metrics_factory().inc_messages()
            self.complete_checkpoint()
        self.emit_runtime_event(
            self.event_run_completed,
            session_id=session_id,
            payload={
                "iterations": iterations,
                "is_error": is_error,
                "response_preview": response_text[:200],
                **(extra_payload or {}),
            },
        )
        if scheduled_payload is not None:
            self.emit_runtime_event(
                self.event_scheduled_run_failed if is_error else self.event_scheduled_run_completed,
                session_id=session_id,
                payload={
                    **scheduled_payload,
                    "iterations": iterations,
                    "is_error": is_error,
                    "response_preview": response_text[:200],
                },
            )
        self._active_runs.discard(run_id)

    def complete_short_run(
        self,
        *,
        run_id: str,
        session_id: str,
        response_text: str,
        scheduled_payload: dict | None,
    ) -> None:
        if run_id not in self._active_runs:
            return
        self.emit_runtime_event(
            self.event_run_completed,
            session_id=session_id,
            payload={"iterations": 0, "is_error": False, "response_preview": response_text[:200]},
        )
        if scheduled_payload is not None:
            self.emit_runtime_event(
                self.event_scheduled_run_completed,
                session_id=session_id,
                payload={**scheduled_payload, "is_error": False, "response_preview": response_text[:200]},
            )
        self.complete_checkpoint()
        self._active_runs.discard(run_id)
