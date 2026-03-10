"""Unit tests for proactive queue worker."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from clawlet.bus.queue import MessageBus
from clawlet.heartbeat.proactive_queue import ProactiveQueueWorker
from clawlet.metrics import get_metrics, reset_metrics


@pytest.mark.asyncio
async def test_proactive_worker_dispatches_top_priority_and_marks_done(tmp_path):
    reset_metrics()
    workspace = tmp_path / "ws"
    queue_file = workspace / "tasks" / "QUEUE.md"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        "- [ ] [P2] medium task\n"
        "- [ ] [P1] urgent task\n",
        encoding="utf-8",
    )

    bus = MessageBus()
    worker = ProactiveQueueWorker(
        bus=bus,
        workspace=workspace,
        max_turns_per_hour=5,
    )
    sent = await worker.on_heartbeat_tick(datetime.now(timezone.utc))
    assert sent == 1

    msg = await bus.consume_inbound()
    assert msg.metadata.get("proactive") is True
    assert "urgent task" in msg.content

    updated = queue_file.read_text(encoding="utf-8")
    assert "- [x] [P1] urgent task" in updated
    assert get_metrics().proactive_tasks_completed_total >= 1


@pytest.mark.asyncio
async def test_proactive_worker_respects_max_turns_per_hour(tmp_path):
    workspace = tmp_path / "ws"
    queue_file = workspace / "tasks" / "QUEUE.md"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text("- [ ] task one\n- [ ] task two\n", encoding="utf-8")
    bus = MessageBus()
    worker = ProactiveQueueWorker(bus=bus, workspace=workspace, max_turns_per_hour=1)
    now = datetime.now(timezone.utc)

    first = await worker.on_heartbeat_tick(now)
    second = await worker.on_heartbeat_tick(now)
    assert first == 1
    assert second == 0


@pytest.mark.asyncio
async def test_proactive_worker_does_not_mark_done_when_dispatch_fails(tmp_path):
    workspace = tmp_path / "ws"
    queue_file = workspace / "tasks" / "QUEUE.md"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text("- [ ] [P1] important task\n", encoding="utf-8")

    class _FailingBus(MessageBus):
        async def publish_inbound(self, msg):  # type: ignore[override]
            raise RuntimeError("dispatch failed")

    worker = ProactiveQueueWorker(bus=_FailingBus(), workspace=workspace, max_turns_per_hour=1)
    sent = await worker.on_heartbeat_tick(datetime.now(timezone.utc))
    assert sent == 0
    updated = queue_file.read_text(encoding="utf-8")
    assert "- [ ] [P1] important task" in updated
