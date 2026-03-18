from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from clawlet.agent.loop import AgentLoop
from clawlet.bus.queue import MessageBus, OutboundMessage
from clawlet.channels.base import BaseChannel
from clawlet.runtime.events import EVENT_CHANNEL_FAILED, RuntimeEventStore
from clawlet.runtime.executor import DeterministicToolRuntime
from clawlet.runtime.policy import RuntimePolicyEngine
from clawlet.runtime.types import ToolCallEnvelope
from clawlet.storage.sqlite import SQLiteStorage
from clawlet.tools.registry import ToolResult
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


@pytest.mark.asyncio
async def test_sqlite_storage_returns_latest_messages_in_chronological_order_with_metadata(tmp_path):
    storage = SQLiteStorage(tmp_path / "clawlet.db")
    await storage.initialize()

    for idx in range(4):
        await storage.store_message(
            session_id="session-1",
            role="assistant" if idx % 2 else "user",
            content=f"message-{idx}",
            metadata={"summary": idx == 2, "index": idx},
        )

    messages = await storage.get_messages("session-1", limit=2)

    assert [message.content for message in messages] == ["message-2", "message-3"]
    assert messages[0].metadata == {"summary": True, "index": 2}
    assert messages[1].metadata == {"summary": False, "index": 3}


def test_agent_loop_skips_transient_assistant_persistence():
    loop = AgentLoop.__new__(AgentLoop)
    loop.memory = _LoopMemoryStub()

    assert loop._is_low_value_persisted_message(
        "assistant",
        "I'll use tools now",
        {"persist": False},
    )
    assert not loop._is_low_value_persisted_message(
        "assistant",
        "Final answer to the user",
        {"persist": True},
    )


class _LoopMemoryStub:
    @staticmethod
    def _is_low_value_memory(value: str) -> bool:
        lowered = (value or "").strip().lower()
        return lowered in {"", "hello", "hi", "hey"}


def test_agent_loop_captures_useful_user_turns_as_episodic_memory():
    loop = AgentLoop.__new__(AgentLoop)
    loop.memory = _LoopMemoryStub()

    capture = loop._memory_capture_plan(
        "user",
        "Mix this with the other post idea you had",
        {"session_id": "session-1"},
    )

    assert capture is not None
    assert capture["metadata"]["scope"] == "daily_note"
    assert capture["write_daily_note"] is True
    assert capture["metadata"]["curated"] is False


def test_agent_loop_promotes_explicit_user_preferences_to_durable_memory():
    loop = AgentLoop.__new__(AgentLoop)
    loop.memory = _LoopMemoryStub()

    capture = loop._memory_capture_plan(
        "user",
        "Please remember that I prefer concise answers for project updates.",
        {"session_id": "session-1"},
    )

    assert capture is not None
    assert capture["metadata"]["scope"] == "durable"
    assert capture["metadata"]["curated"] is True


def test_agent_loop_captures_meaningful_assistant_outcomes_as_episode_only():
    loop = AgentLoop.__new__(AgentLoop)
    loop.memory = _LoopMemoryStub()

    capture = loop._memory_capture_plan(
        "assistant",
        "I've prepared a combined post draft that shares the update and asks the community for ideas.",
        {"session_id": "session-1", "persist": True},
    )

    assert capture is not None
    assert capture["metadata"]["scope"] == "daily_note"
    assert capture["metadata"]["curated"] is False


def test_agent_loop_repairs_templated_moltbook_comment_call_from_live_context():
    loop = AgentLoop.__new__(AgentLoop)
    loop._recent_http_context = {
        "moltbook": {
            "last_post_id": "post-live-123",
            "last_comment_id": "comment-live-456",
            "last_molty_name": "ami-from-ami",
        }
    }

    repaired = loop._repair_templated_tool_args(
        "http_request",
        {
            "method": "POST",
            "url": "https://www.moltbook.com/api/v1/posts/:postId/comments",
            "auth_profile": "moltbook_api_key",
            "json_body": {
                "content": "Thanks for the question.",
                "parentId": "COMMENT_ID",
            },
        },
    )

    assert repaired is not None
    assert repaired["auth_profile"] == "moltbook"
    assert repaired["url"] == "https://www.moltbook.com/api/v1/posts/post-live-123/comments"
    assert repaired["json_body"]["parentId"] == "comment-live-456"


def test_agent_loop_remembers_live_moltbook_ids_from_http_results():
    loop = AgentLoop.__new__(AgentLoop)
    loop._recent_http_context = {}

    loop._remember_http_request_context(
        {"url": "https://www.moltbook.com/api/v1/home"},
        ToolResult(
            success=True,
            output=(
                '{"activity_on_your_posts":[{"post_id":"post-home-1","latest_commenters":["ulagent"]}]}'
            ),
        ),
    )
    loop._remember_http_request_context(
        {"url": "https://www.moltbook.com/api/v1/posts/post-home-1/comments?sort=new&limit=20"},
        ToolResult(
            success=True,
            output=(
                '{"comments":[{"id":"comment-new-1","post_id":"post-home-1","author":{"name":"ami-from-ami"}}]}'
            ),
        ),
    )

    assert loop._recent_http_context["moltbook"]["last_post_id"] == "post-home-1"
    assert loop._recent_http_context["moltbook"]["last_comment_id"] == "comment-new-1"
    assert loop._recent_http_context["moltbook"]["last_molty_name"] == "ami-from-ami"
