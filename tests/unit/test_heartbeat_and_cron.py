"""Hardening checks for the two dark critical paths: heartbeat lifecycle and cron add→run-now."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from clawlet.heartbeat.cron_scheduler import Scheduler
from clawlet.heartbeat.models import ScheduledTask, TaskAction
from clawlet.heartbeat.state import HeartbeatStateStore


def test_heartbeat_state_lifecycle(tmp_path):
    store = HeartbeatStateStore(tmp_path / "heartbeat_state.json")
    now = datetime.now(timezone.utc)
    route = {"channel": "cli", "chat_id": "local"}

    # No route -> never run, whatever is due
    decision = store.evaluate_tick(
        now=now, context="review pending work", route=None, interval_minutes=30
    )
    assert decision.should_publish is False
    assert decision.reason == "no_route"

    store.record_runner_decision(now=now, status="skipped", reason="no_route")
    state = store.load()
    assert state["last_decision"] == "skipped"
    assert state["last_reason"] == "no_route"
    assert state["last_tick_at"]

    # Route + first-ever check -> publish due
    decision = store.evaluate_tick(
        now=now + timedelta(minutes=45), context="review pending work",
        route=route, interval_minutes=30,
    )
    assert decision.should_publish is True
    assert decision.reason == "checks_due"
    assert decision.route == route

    # Right after recording a check result, same check is in cooldown -> no publish
    # A successful cycle puts the inferred check type into its cooldown window
    store.record_cycle_result(
        now=now + timedelta(minutes=46),
        response_text="heartbeat_ok: nothing needs attention",
        tool_names=[],
        route=route,
        check_types=["memory"],  # the type inferred from "review pending work"
    )
    decision = store.evaluate_tick(
        now=now + timedelta(minutes=47), context="review pending work",
        route=route, interval_minutes=30,
    )
    assert decision.should_publish is False


async def test_cron_add_and_run_now(tmp_path):
    ran: list[dict] = []

    async def job(**kwargs):
        ran.append(kwargs)
        return "ok"

    scheduler = Scheduler(
        state_file=str(tmp_path / "scheduler_state.json"),
        jobs_file=str(tmp_path / "jobs.yaml"),
        runs_dir=str(tmp_path / "runs"),
    )
    task = ScheduledTask(
        id="t1",
        name="echo",
        interval=timedelta(minutes=5),
        action=TaskAction.CALLBACK,
        callback=job,
    )
    scheduler.add_task(task)
    assert scheduler.get_task("t1") is task
    assert scheduler.get_next_runs(1), "next_run must be computed on add"

    result = await scheduler.run_task("t1")
    assert result.success is True
    assert result.status.value == "completed"
    assert ran == [{}]  # callback executed with the task's (empty) params
    assert result.output == "ok"

    # Run persisted for `cron runs`
    assert scheduler.get_task("t1").last_result is not None
    assert scheduler.get_task("t1").last_run is not None

    missing = await scheduler.run_task("nope")
    assert missing.success is False
