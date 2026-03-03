"""Replay command helpers for the CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from clawlet.cli.common_ui import print_footer, print_section
from clawlet.cli.runtime_paths import resolve_replay_dir

console = Console()


def run_replay_command(
    run_id: str,
    workspace_path: Path,
    limit: int,
    show_signature: bool,
    verify: bool,
    verify_resume: bool,
    reliability: bool,
    reexecute: bool,
    allow_write_reexecute: bool,
    fail_on_mismatch: bool,
) -> None:
    """Inspect structured runtime events for a run."""
    from clawlet.config import load_config as load_runtime_config
    from clawlet.runtime import (
        RecoveryManager,
        RuntimeEventStore,
        build_reliability_report,
        reexecute_run,
        replay_run,
        verify_resume_equivalence,
    )
    from clawlet.tools import create_default_tool_registry

    replay_dir = resolve_replay_dir(workspace_path)
    store = RuntimeEventStore(replay_dir / "events.jsonl")

    events = store.iter_events(run_id=run_id, limit=limit)
    print_section("Replay", f"Run {run_id}")
    if not events:
        console.print("|  [yellow]No events found for this run id[/yellow]")
        print_footer()
        raise typer.Exit(1)

    for ev in events:
        payload = ev.payload or {}
        preview = str(payload)[:120].replace("\\n", " ")
        console.print(f"|  {ev.timestamp}  [{ev.event_type}] {preview}")

    if show_signature:
        signature = store.get_run_signature(run_id)
        console.print("|")
        console.print(f"|  Signature: [bold]{signature}[/bold]")

    if verify:
        report = replay_run(store, run_id)
        console.print("|")
        console.print(f"|  Verify signature: {'yes' if bool(report.signature) else 'no'}")
        console.print(f"|  Verify event-flow: {'yes' if report.has_start and report.has_end else 'no'}")
        console.print(
            "|  Verify tool-chain: "
            f"requested={report.tool_requested} started={report.tool_started} finished={report.tool_finished}"
        )
        for warning in report.warnings:
            console.print(f"|  warning: {warning}")
        for error in report.errors:
            console.print(f"|  error: {error}")
        if not report.passed:
            print_footer()
            raise typer.Exit(2)

    if verify_resume:
        manager = RecoveryManager(replay_dir / "checkpoints")
        resume_report = verify_resume_equivalence(store, manager, run_id)
        console.print("|")
        console.print(
            f"|  Verify resume-equivalence: {'yes' if resume_report.equivalent else 'no'}"
        )
        console.print(
            f"|  Resume successors: {len(resume_report.successors)} "
            f"({', '.join(resume_report.successors) if resume_report.successors else 'none'})"
        )
        for detail in resume_report.details:
            console.print(f"|  detail: {detail}")
        if not resume_report.equivalent:
            print_footer()
            raise typer.Exit(2)

    if reliability or verify:
        rr = build_reliability_report(store, run_id)
        console.print("|")
        console.print(
            "|  Reliability: "
            f"tool_success_rate={rr.tool_success_rate * 100:.1f}% "
            f"tool_failed={rr.tool_failed} provider_failed={rr.provider_failed} "
            f"storage_failed={rr.storage_failed} channel_failed={rr.channel_failed}"
        )
        console.print(
            f"|  Reliability crash-like: {'yes' if rr.crash_like else 'no'} "
            f"(run_completed_error={'yes' if rr.run_completed_error else 'no'})"
        )

    if reexecute:
        try:
            cfg = load_runtime_config(workspace_path)
        except Exception:
            cfg = None
        registry = create_default_tool_registry(allowed_dir=str(workspace_path), config=cfg)
        rex = reexecute_run(
            store=store,
            run_id=run_id,
            registry=registry,
            allow_write=allow_write_reexecute,
        )
        console.print("|")
        console.print(
            "|  Reexecute: "
            f"requested={rex.requested} executed={rex.executed} matched={rex.matched} "
            f"mismatched={rex.mismatched} skipped={rex.skipped}"
        )
        for detail in rex.details:
            if detail.status == "matched":
                continue
            console.print(
                f"|  {detail.status}: tcid={detail.tool_call_id} tool={detail.tool_name} reason={detail.reason}"
            )
        if rex.mismatched > 0 and fail_on_mismatch:
            print_footer()
            raise typer.Exit(2)

    print_footer()
