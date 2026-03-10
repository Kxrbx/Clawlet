"""Unit tests for cron scheduler runtime wiring."""

from __future__ import annotations

from datetime import timedelta
import pytest

from clawlet.heartbeat.cron_scheduler import Scheduler
from clawlet.heartbeat.models import ScheduledTask, TaskAction


class _FakeBus:
    def __init__(self):
        self.messages = []
        self.outbound = []

    async def publish_inbound(self, msg):
        self.messages.append(msg)

    async def publish_outbound(self, msg):
        self.outbound.append(msg)
        return True


class _FailingOutboundBus(_FakeBus):
    async def publish_outbound(self, msg):
        self.outbound.append(msg)
        raise RuntimeError("delivery failed")


@pytest.mark.asyncio
async def test_execute_agent_queues_message_when_bus_injected():
    bus = _FakeBus()
    scheduler = Scheduler(message_bus=bus)
    task = ScheduledTask(
        id="job123",
        name="job",
        action=TaskAction.AGENT,
        params={"prompt": "run check", "session_target": "main", "wake_mode": "now"},
        interval=None,
    )

    result = await scheduler._execute_agent(task)
    assert "queued" in result.lower()
    assert len(bus.messages) == 1
    msg = bus.messages[0]
    assert msg.metadata.get("source") == "scheduler"
    assert msg.metadata.get("job_id") == "job123"


@pytest.mark.asyncio
async def test_execute_tool_errors_without_registry():
    scheduler = Scheduler(tool_registry=None)
    task = ScheduledTask(
        id="job-tool",
        name="job-tool",
        action=TaskAction.TOOL,
        params={"tool": "list_dir", "params": {"path": "."}},
    )

    with pytest.raises(ValueError, match="tool registry not configured"):
        await scheduler._execute_tool(task)


@pytest.mark.asyncio
async def test_execute_agent_stages_until_next_heartbeat_when_wake_mode_set():
    bus = _FakeBus()
    scheduler = Scheduler(message_bus=bus)
    task = ScheduledTask(
        id="job-staged",
        name="staged-job",
        action=TaskAction.AGENT,
        params={"prompt": "run later", "session_target": "main", "wake_mode": "next_heartbeat"},
    )

    result = await scheduler._execute_agent(task)
    assert "staged" in result.lower()
    assert len(bus.messages) == 0

    flushed = await scheduler.flush_staged_agent_jobs()
    assert flushed == 1
    assert len(bus.messages) == 1
    assert bus.messages[0].metadata.get("wake_mode") == "next_heartbeat"


@pytest.mark.asyncio
async def test_delivery_mode_announce_publishes_outbound():
    bus = _FakeBus()
    scheduler = Scheduler(message_bus=bus)
    task = ScheduledTask(
        id="job-deliver",
        name="deliver-job",
        action=TaskAction.AGENT,
        params={
            "prompt": "run now",
            "wake_mode": "now",
            "delivery_mode": "announce",
            "delivery_channel": "scheduler",
            "delivery_chat_id": "main",
        },
    )

    result = await scheduler._execute_task(task)
    assert len(bus.outbound) == 1
    out = bus.outbound[0]
    assert out.channel == "scheduler"
    assert out.chat_id == "main"
    assert "deliver-job" in out.content
    assert result.metadata.get("delivery_status") == "delivered"
    assert result.metadata.get("delivery_mode") == "announce"


@pytest.mark.asyncio
async def test_delivery_best_effort_does_not_fail_task():
    bus = _FailingOutboundBus()
    scheduler = Scheduler(message_bus=bus)
    task = ScheduledTask(
        id="job-best-effort",
        name="best-effort",
        action=TaskAction.AGENT,
        params={
            "prompt": "run now",
            "wake_mode": "now",
            "delivery_mode": "announce",
            "best_effort_delivery": True,
        },
    )

    result = await scheduler._execute_task(task)
    assert result.success is True
    assert result.metadata.get("delivery_status") == "not-delivered"


@pytest.mark.asyncio
async def test_manual_run_delete_after_run_removes_job():
    bus = _FakeBus()
    scheduler = Scheduler(message_bus=bus)
    task = ScheduledTask(
        id="job-delete",
        name="job-delete",
        action=TaskAction.AGENT,
        params={"prompt": "run now", "wake_mode": "now", "delete_after_run": True},
    )
    scheduler.add_task(task)
    assert scheduler.get_task("job-delete") is not None

    result = await scheduler.run_task("job-delete")
    assert result.success is True
    assert scheduler.get_task("job-delete") is None


@pytest.mark.asyncio
async def test_due_task_waits_when_dependency_is_missing(monkeypatch):
    scheduler = Scheduler()
    task = ScheduledTask(
        id="job-needs-dep",
        name="job-needs-dep",
        action=TaskAction.AGENT,
        interval=timedelta(minutes=5),
        params={"prompt": "x"},
        depends_on=["missing-job"],
    )
    scheduler.add_task(task)
    called: list[str] = []

    async def _fake_run_task_with_retry(_task):
        called.append(_task.id)

    monkeypatch.setattr(scheduler, "_run_task_with_retry", _fake_run_task_with_retry)
    await scheduler._check_and_run_tasks()
    assert called == []
