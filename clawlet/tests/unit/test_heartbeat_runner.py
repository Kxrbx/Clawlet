"""Unit tests for heartbeat runner and outbound suppression behavior."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from clawlet.agent.identity import Identity
from clawlet.agent.loop import AgentLoop
from clawlet.bus.queue import InboundMessage, MessageBus, OutboundMessage
from clawlet.config import RuntimeSettings, SQLiteConfig, StorageConfig
from clawlet.heartbeat.runner import HeartbeatRunner
from clawlet.metrics import get_metrics, reset_metrics
from clawlet.providers.base import BaseProvider, LLMResponse
from clawlet.tools.registry import ToolRegistry


class _DummyProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "dummy"

    def get_default_model(self) -> str:
        return "dummy-model"

    async def complete(self, messages, model=None, temperature=0.7, max_tokens=4096, **kwargs):
        return LLMResponse(content="ok", model=model or "dummy-model", usage={}, finish_reason="stop")

    async def stream(self, messages, model=None, temperature=0.7, max_tokens=4096, **kwargs):
        yield "ok"

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_heartbeat_tick_publishes_inbound_with_metadata():
    bus = MessageBus()
    runner = HeartbeatRunner(
        bus=bus,
        interval_minutes=30,
        quiet_hours_start=2,
        quiet_hours_end=9,
        target="main",
        ack_max_chars=42,
    )

    await runner._tick(datetime.now(timezone.utc))

    msg = await bus.consume_inbound()
    assert msg.channel == "scheduler"
    assert msg.chat_id == "main"
    assert msg.metadata.get("heartbeat") is True
    assert msg.metadata.get("source") == "heartbeat"
    assert msg.metadata.get("ack_max_chars") == 42


@pytest.mark.asyncio
async def test_heartbeat_tick_uses_last_route_provider():
    bus = MessageBus()
    runner = HeartbeatRunner(
        bus=bus,
        interval_minutes=30,
        quiet_hours_start=2,
        quiet_hours_end=9,
        target="last",
        route_provider=lambda: {
            "channel": "telegram",
            "chat_id": "123",
            "user_id": "u1",
            "user_name": "Alice",
        },
    )

    await runner._tick(datetime.now(timezone.utc))
    msg = await bus.consume_inbound()
    assert msg.channel == "telegram"
    assert msg.chat_id == "123"
    assert msg.user_id == "u1"
    assert msg.user_name == "Alice"


@pytest.mark.asyncio
async def test_publish_outbound_suppresses_trivial_heartbeat_ack(tmp_path: Path):
    reset_metrics()
    bus = MessageBus()
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    for filename in ("SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"):
        (workspace / filename).write_text("# x\n", encoding="utf-8")

    agent = AgentLoop(
        bus=bus,
        workspace=workspace,
        identity=Identity(agent_name="A", user_name="U"),
        provider=_DummyProvider(),
        tools=ToolRegistry(),
        model="dummy-model",
        storage_config=StorageConfig(backend="sqlite", sqlite=SQLiteConfig(path=str(workspace / "clawlet.db"))),
        runtime_config=RuntimeSettings(),
    )

    published = await agent._publish_outbound_with_retry(
        OutboundMessage(
            channel="telegram",
            chat_id="123",
            content="HEARTBEAT_OK",
            metadata={"heartbeat": True, "ack_max_chars": 24},
        )
    )

    assert published is True
    assert bus.outbound_size == 0
    assert get_metrics().heartbeat_acks_suppressed_total >= 1


@pytest.mark.asyncio
async def test_heartbeat_target_last_uses_agent_last_route(tmp_path: Path):
    bus = MessageBus()
    workspace = tmp_path / "ws_last"
    workspace.mkdir(parents=True, exist_ok=True)
    for filename in ("SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"):
        (workspace / filename).write_text("# x\n", encoding="utf-8")

    agent = AgentLoop(
        bus=bus,
        workspace=workspace,
        identity=Identity(agent_name="A", user_name="U"),
        provider=_DummyProvider(),
        tools=ToolRegistry(),
        model="dummy-model",
        storage_config=StorageConfig(backend="sqlite", sqlite=SQLiteConfig(path=str(workspace / "clawlet.db"))),
        runtime_config=RuntimeSettings(),
    )
    # Avoid DB init in this environment; allow queued persistence tasks to drain.
    agent._storage_ready.set()

    # Seed last active route by processing one inbound message.
    await agent._process_message(
        InboundMessage(
            channel="telegram",
            chat_id="chat-42",
            content="hello",
            user_id="u42",
            user_name="Alice",
        )
    )

    runner = HeartbeatRunner(
        bus=bus,
        interval_minutes=15,
        quiet_hours_start=0,
        quiet_hours_end=0,  # disabled quiet-hours gate for deterministic test
        target="last",
        route_provider=agent.get_last_route,
    )
    await runner._tick(datetime.now(timezone.utc))

    hb_msg = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert hb_msg.channel == "telegram"
    assert hb_msg.chat_id == "chat-42"
    assert hb_msg.metadata.get("heartbeat") is True
    assert hb_msg.metadata.get("source") == "heartbeat"


@pytest.mark.asyncio
async def test_heartbeat_tick_invokes_on_tick_hook():
    bus = MessageBus()
    calls = {"n": 0}

    async def _on_tick(_now):
        calls["n"] += 1

    runner = HeartbeatRunner(
        bus=bus,
        interval_minutes=30,
        quiet_hours_start=2,
        quiet_hours_end=9,
        target="main",
        on_tick=_on_tick,
    )
    await runner._tick(datetime.now(timezone.utc))
    assert calls["n"] == 1
