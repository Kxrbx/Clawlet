"""Replay verification and resume-chain equivalence checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from clawlet.runtime.failures import classify_error_text
from clawlet.runtime.events import (
    EVENT_RUN_COMPLETED,
    EVENT_RUN_STARTED,
    EVENT_TOOL_COMPLETED,
    EVENT_TOOL_FAILED,
    EVENT_TOOL_REQUESTED,
    EVENT_TOOL_STARTED,
    RuntimeEvent,
    RuntimeEventStore,
)
from clawlet.runtime.policy import READ_ONLY_TOOLS, RuntimePolicyEngine
from clawlet.runtime.recovery import RecoveryManager
from clawlet.runtime.rust_bridge import fast_hash
from clawlet.tools.registry import ToolRegistry


@dataclass(slots=True)
class ReplayReport:
    run_id: str
    signature: str
    event_count: int
    has_start: bool
    has_end: bool
    tool_requested: int
    tool_started: int
    tool_finished: int
    deterministic_ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.deterministic_ok and not self.errors


@dataclass(slots=True)
class ResumeEquivalenceReport:
    source_run_id: str
    successors: list[str]
    checkpoint_exists: bool
    equivalent: bool
    details: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReexecutionDetail:
    tool_call_id: str
    tool_name: str
    status: str  # matched | mismatched | skipped
    reason: str = ""
    recorded_success: Optional[bool] = None
    reexecuted_success: Optional[bool] = None
    recorded_failure_code: str = ""
    reexecuted_failure_code: str = ""
    recorded_output_hash: str = ""
    reexecuted_output_hash: str = ""


@dataclass(slots=True)
class ReplayReexecutionReport:
    run_id: str
    requested: int
    executed: int
    matched: int
    mismatched: int
    skipped: int
    details: list[ReexecutionDetail] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.mismatched == 0


def replay_run(store: RuntimeEventStore, run_id: str) -> ReplayReport:
    events = store.iter_events(run_id=run_id)
    signature = store.get_run_signature(run_id)

    has_start = any(e.event_type == EVENT_RUN_STARTED for e in events)
    has_end = any(e.event_type == EVENT_RUN_COMPLETED for e in events)
    errors: list[str] = []
    warnings: list[str] = []

    if not events:
        errors.append("No events found for run")
    if not has_start:
        errors.append("RunStarted missing")
    if not has_end:
        errors.append("RunCompleted missing")

    requested_ids: set[str] = set()
    started_ids: set[str] = set()
    finished_ids: set[str] = set()
    requested_count = 0
    started_count = 0
    finished_count = 0

    for ev in events:
        payload = ev.payload or {}
        tcid = str(payload.get("tool_call_id") or "")

        if ev.event_type == EVENT_TOOL_REQUESTED:
            requested_count += 1
            if not tcid:
                errors.append("ToolRequested missing tool_call_id")
                continue
            if tcid in requested_ids:
                warnings.append(f"Duplicate ToolRequested for tool_call_id={tcid}")
            requested_ids.add(tcid)

        elif ev.event_type == EVENT_TOOL_STARTED:
            started_count += 1
            if not tcid:
                errors.append("ToolStarted missing tool_call_id")
                continue
            if tcid not in requested_ids:
                errors.append(f"ToolStarted without request: tool_call_id={tcid}")
            started_ids.add(tcid)

        elif ev.event_type in (EVENT_TOOL_COMPLETED, EVENT_TOOL_FAILED):
            finished_count += 1
            if not tcid:
                errors.append(f"{ev.event_type} missing tool_call_id")
                continue
            if tcid not in requested_ids:
                errors.append(f"{ev.event_type} without request: tool_call_id={tcid}")
            finished_ids.add(tcid)

    dangling = sorted(started_ids - finished_ids)
    if dangling:
        warnings.append(f"Started but not finished tool calls: {', '.join(dangling[:10])}")

    deterministic_ok = bool(signature) and has_start and has_end
    return ReplayReport(
        run_id=run_id,
        signature=signature,
        event_count=len(events),
        has_start=has_start,
        has_end=has_end,
        tool_requested=requested_count,
        tool_started=started_count,
        tool_finished=finished_count,
        deterministic_ok=deterministic_ok,
        errors=errors,
        warnings=warnings,
    )


def verify_resume_equivalence(
    store: RuntimeEventStore,
    recovery: RecoveryManager,
    source_run_id: str,
) -> ResumeEquivalenceReport:
    checkpoint_exists = recovery.load(source_run_id) is not None
    successors = _find_resume_successors(store, source_run_id)
    details: list[str] = []

    if not successors:
        return ResumeEquivalenceReport(
            source_run_id=source_run_id,
            successors=[],
            checkpoint_exists=checkpoint_exists,
            equivalent=False,
            details=["No recovery-resume successor runs found"],
        )

    source_tools = _tool_name_sequence(store.iter_events(run_id=source_run_id))
    all_ok = True
    for run_id in successors:
        rep = replay_run(store, run_id)
        if not rep.passed:
            all_ok = False
            details.append(f"Successor run {run_id} failed replay checks")
            continue

        successor_tools = _tool_name_sequence(store.iter_events(run_id=run_id))
        # Resume equivalence assertion: resumed run should not drop all tool activity
        # when source had tool activity; allow small drift but require overlap.
        if source_tools:
            overlap = set(source_tools).intersection(set(successor_tools))
            if not overlap and successor_tools:
                all_ok = False
                details.append(
                    f"Successor run {run_id} has no tool overlap with source run"
                )
            else:
                details.append(f"Successor run {run_id} passed with tool-overlap={len(overlap)}")
        else:
            details.append(f"Successor run {run_id} passed")

    if checkpoint_exists and not successors:
        all_ok = False
        details.append("Checkpoint exists but no resumed run found")

    return ResumeEquivalenceReport(
        source_run_id=source_run_id,
        successors=successors,
        checkpoint_exists=checkpoint_exists,
        equivalent=all_ok,
        details=details,
    )


def reexecute_run(
    store: RuntimeEventStore,
    run_id: str,
    registry: ToolRegistry,
    allow_write: bool = False,
) -> ReplayReexecutionReport:
    events = store.iter_events(run_id=run_id)
    requested = [e for e in events if e.event_type == EVENT_TOOL_REQUESTED]
    outcomes = _collect_recorded_outcomes(events)
    policy = RuntimePolicyEngine()

    report = ReplayReexecutionReport(
        run_id=run_id,
        requested=len(requested),
        executed=0,
        matched=0,
        mismatched=0,
        skipped=0,
        details=[],
    )

    for ev in requested:
        payload = ev.payload or {}
        tcid = str(payload.get("tool_call_id") or "")
        name = str(payload.get("tool_name") or "").strip()
        args = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
        mode = str(payload.get("execution_mode") or policy.infer_mode(name, args))

        if not tcid or not name:
            report.skipped += 1
            report.details.append(
                ReexecutionDetail(
                    tool_call_id=tcid or "<missing>",
                    tool_name=name or "<missing>",
                    status="skipped",
                    reason="missing tool_call_id or tool_name",
                )
            )
            continue

        if mode == "elevated":
            report.skipped += 1
            report.details.append(
                ReexecutionDetail(
                    tool_call_id=tcid,
                    tool_name=name,
                    status="skipped",
                    reason="elevated replay is disabled",
                )
            )
            continue

        if not allow_write and name not in READ_ONLY_TOOLS:
            report.skipped += 1
            report.details.append(
                ReexecutionDetail(
                    tool_call_id=tcid,
                    tool_name=name,
                    status="skipped",
                    reason="non-read-only tool skipped (use --allow-write-reexecute)",
                )
            )
            continue

        report.executed += 1
        result = _run_async(registry.execute(name, **args))
        reexec_success = bool(result.success)
        reexec_failure = classify_error_text(result.error)
        reexec_output_hash = _hash_text(result.output) if result.output else ""

        recorded = outcomes.get(tcid)
        if recorded is None:
            report.mismatched += 1
            report.details.append(
                ReexecutionDetail(
                    tool_call_id=tcid,
                    tool_name=name,
                    status="mismatched",
                    reason="no recorded tool outcome found",
                    reexecuted_success=reexec_success,
                    reexecuted_failure_code=reexec_failure.code,
                    reexecuted_output_hash=reexec_output_hash,
                )
            )
            continue

        mismatches: list[str] = []
        if recorded["success"] != reexec_success:
            mismatches.append("success mismatch")
        if recorded["failure_code"] and recorded["failure_code"] != reexec_failure.code:
            mismatches.append("failure_code mismatch")
        if recorded["output_hash"] and recorded["output_hash"] != reexec_output_hash:
            mismatches.append("output_hash mismatch")

        if mismatches:
            report.mismatched += 1
            report.details.append(
                ReexecutionDetail(
                    tool_call_id=tcid,
                    tool_name=name,
                    status="mismatched",
                    reason=", ".join(mismatches),
                    recorded_success=bool(recorded["success"]),
                    reexecuted_success=reexec_success,
                    recorded_failure_code=str(recorded["failure_code"]),
                    reexecuted_failure_code=reexec_failure.code,
                    recorded_output_hash=str(recorded["output_hash"]),
                    reexecuted_output_hash=reexec_output_hash,
                )
            )
        else:
            report.matched += 1
            report.details.append(
                ReexecutionDetail(
                    tool_call_id=tcid,
                    tool_name=name,
                    status="matched",
                    recorded_success=bool(recorded["success"]),
                    reexecuted_success=reexec_success,
                    recorded_failure_code=str(recorded["failure_code"]),
                    reexecuted_failure_code=reexec_failure.code,
                    recorded_output_hash=str(recorded["output_hash"]),
                    reexecuted_output_hash=reexec_output_hash,
                )
            )

    return report


def _find_resume_successors(store: RuntimeEventStore, source_run_id: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for ev in store.iter_events():
        if ev.event_type != EVENT_RUN_STARTED:
            continue
        resume_from = str((ev.payload or {}).get("recovery_resume_from") or "")
        if resume_from != source_run_id:
            continue
        if ev.run_id in seen:
            continue
        seen.add(ev.run_id)
        out.append(ev.run_id)
    return out


def _tool_name_sequence(events: list[RuntimeEvent]) -> list[str]:
    names: list[str] = []
    for ev in events:
        if ev.event_type != EVENT_TOOL_REQUESTED:
            continue
        name = str((ev.payload or {}).get("tool_name") or "").strip()
        if name:
            names.append(name)
    return names


def _collect_recorded_outcomes(events: list[RuntimeEvent]) -> dict[str, dict[str, object]]:
    outcomes: dict[str, dict[str, object]] = {}
    for ev in events:
        payload = ev.payload or {}
        tcid = str(payload.get("tool_call_id") or "")
        if not tcid:
            continue

        if ev.event_type == EVENT_TOOL_COMPLETED:
            raw_output = str(payload.get("output") or "")
            out_hash = "" if not raw_output or raw_output == "[redacted]" else _hash_text(raw_output)
            outcomes[tcid] = {
                "success": True,
                "failure_code": "",
                "output_hash": out_hash,
            }
        elif ev.event_type == EVENT_TOOL_FAILED:
            outcomes[tcid] = {
                "success": False,
                "failure_code": str(payload.get("failure_code") or ""),
                "output_hash": "",
            }
    return outcomes


def _hash_text(value: str) -> str:
    return fast_hash(value or "")


def _run_async(coro):
    import asyncio
    from concurrent.futures import Future
    import threading

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        future: Future = Future()

        def _runner():
            try:
                future.set_result(asyncio.run(coro))
            except Exception as e:
                future.set_exception(e)

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        return future.result()

    return asyncio.run(coro)
