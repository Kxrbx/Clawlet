from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from clawlet.bus.queue import MessageBus, OutboundMessage
from clawlet.channels.base import BaseChannel
from clawlet.runtime.events import EVENT_CHANNEL_FAILED, RuntimeEventStore
from clawlet.runtime.executor import DeterministicToolRuntime
from clawlet.runtime.policy import RuntimePolicyEngine
from clawlet.runtime.types import ToolCallEnvelope
from clawlet.tools.memory import RecallTool
from clawlet.tools.registry import ToolRegistry


class _ReplayConfig:
    enabled = True


class _RuntimeConfig:
    replay = _ReplayConfig()


class _AgentStub:
    def __init__(self, event_log: Path):
        self.runtime_config = _RuntimeConfig()
        self._event_store = RuntimeEventStore(event_log)


class _FlakyChannel(BaseChannel):
    def __init__(self, bus, config, agent=None):
        super().__init__(bus, config, agent=agent)
        self.attempts = 0
        self.sent: list[str] = []

    @property
    def name(self) -> str:
        return "telegram"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("simulated telegram send failure")
        self.sent.append(msg.content)


class _MemoryStub:
    def recall(self, key: str):
        return "moltbook_test_key" if key == "moltbook_api_key" else None


@pytest.mark.asyncio
async def test_base_channel_retries_failed_delivery_and_records_runtime_event(tmp_path):
    bus = MessageBus()
    channel = _FlakyChannel(
        bus,
        {"delivery_retries": 1, "delivery_retry_backoff_seconds": 0.0},
        agent=_AgentStub(tmp_path / "events.jsonl"),
    )
    await channel.start()
    task = asyncio.create_task(channel._run_outbound_loop())

    await bus.publish_outbound(
        OutboundMessage(
            channel="telegram",
            chat_id="319944040",
            content="hello from clawlet",
            metadata={"_session_id": "session-1", "_run_id": "session-1-run"},
        )
    )

    for _ in range(200):
        if channel.sent:
            break
        await asyncio.sleep(0.01)

    assert channel.sent == ["hello from clawlet"]

    await channel.stop()
    await asyncio.wait_for(task, timeout=2.0)

    events = channel.agent._event_store.iter_events(run_id="session-1-run")
    failures = [event for event in events if event.event_type == EVENT_CHANNEL_FAILED]
    assert len(failures) == 1
    assert failures[0].payload["channel"] == "telegram"
    assert failures[0].payload["attempt"] == 1


@pytest.mark.asyncio
async def test_deterministic_tool_runtime_does_not_break_narrow_memory_tool_signatures(tmp_path):
    registry = ToolRegistry()
    registry.register(RecallTool(_MemoryStub()))
    runtime = DeterministicToolRuntime(
        registry=registry,
        event_store=RuntimeEventStore(tmp_path / "events.jsonl"),
        policy=RuntimePolicyEngine(),
    )

    result, metadata = await runtime.execute(
        ToolCallEnvelope(
            run_id="run-1",
            session_id="session-1",
            tool_call_id="call-1",
            tool_name="recall",
            arguments={"key": "moltbook_api_key"},
            execution_mode="read_only",
            workspace_path="/tmp/ws",
        )
    )

    assert result.success is True
    assert "moltbook_test_key" in result.output
    assert metadata.attempts == 1
