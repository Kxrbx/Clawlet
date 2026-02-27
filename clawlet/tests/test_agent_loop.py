"""
Tests for AgentLoop integration.
"""

import asyncio
from pathlib import Path

from clawlet.agent.loop import Message


def test_extract_tool_calls_parses_raw_json(agent_loop):
    """Raw JSON tool payloads should be interpreted as tool calls."""
    calls = agent_loop._extract_tool_calls('{"name":"list_dir","arguments":{"path":"."}}')
    assert len(calls) == 1
    assert calls[0].name == "list_dir"
    assert calls[0].arguments == {"path": "."}


def test_validate_tool_params_rejects_unknown_when_additional_properties_false():
    from clawlet.tools.registry import validate_tool_params

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }
    valid, error, _ = validate_tool_params(
        tool_name="list_dir",
        params={"path": ".", "extra": "nope"},
        schema=schema,
    )

    assert valid is False
    assert "Unknown parameter 'extra'" in error

def test_agent_loop_processes_message(agent_loop, temp_workspace, event_loop):
    """Test that AgentLoop processes a message and persists it."""
    from clawlet.bus.queue import InboundMessage
    
    # Create an inbound message
    msg = InboundMessage(
        channel="test",
        chat_id="12345",
        content="Hello, agent!"
    )
    
    # Process the message
    response = event_loop.run_until_complete(agent_loop._process_message(msg))
    
    # Check response exists
    assert response is not None
    assert response.content  # non-empty
    
    # Check that message was added to history
    assert len(agent_loop._history) >= 2  # user + assistant
    
    # Wait for async persistence tasks to complete
    event_loop.run_until_complete(asyncio.sleep(0.5))
    
    # Verify storage (DB)
    import aiosqlite
    db_path = temp_workspace / "clawlet.db"
    assert db_path.exists()
    
    async def check_db():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (agent_loop._session_id,))
            count = (await cursor.fetchone())[0]
            return count
    
    count = event_loop.run_until_complete(check_db())
    assert count >= 2  # user and assistant messages stored
    
    # Verify MEMORY.md was written (by checking file exists and contains something)
    memory_path = temp_workspace / "MEMORY.md"
    assert memory_path.exists()
    content = memory_path.read_text()
    # Should contain at least the assistant response
    assert len(content) > 0


def test_list_dir_defaults_to_workspace_root(temp_workspace, event_loop):
    """list_dir should work without explicit path argument."""
    from clawlet.tools.files import ListDirTool

    (temp_workspace / "sample.txt").write_text("ok", encoding="utf-8")
    tool = ListDirTool(allowed_dir=temp_workspace)
    result = event_loop.run_until_complete(tool.execute())

    assert result.success is True
    assert "sample.txt (file)" in result.output


def test_agent_loop_isolates_histories_between_chats(agent_loop, event_loop):
    """Each chat should maintain an independent history/session."""
    from clawlet.bus.queue import InboundMessage

    msg_a1 = InboundMessage(channel="test", chat_id="chat-a", content="Hello from A")
    msg_b1 = InboundMessage(channel="test", chat_id="chat-b", content="Hello from B")

    event_loop.run_until_complete(agent_loop._process_message(msg_a1))
    event_loop.run_until_complete(agent_loop._process_message(msg_b1))

    state_a = event_loop.run_until_complete(agent_loop._get_conversation_state("test", "chat-a"))
    state_b = event_loop.run_until_complete(agent_loop._get_conversation_state("test", "chat-b"))

    assert state_a.session_id != state_b.session_id
    assert any("Hello from A" in m.content for m in state_a.history)
    assert not any("Hello from A" in m.content for m in state_b.history)
    assert any("Hello from B" in m.content for m in state_b.history)
    assert not any("Hello from B" in m.content for m in state_a.history)


def test_build_messages_applies_context_character_budget(agent_loop):
    """Message builder should prune oldest entries when char budget is exceeded."""
    agent_loop.CONTEXT_WINDOW = 10
    agent_loop.CONTEXT_CHAR_BUDGET = 60
    history = [
        Message(role="user", content="x" * 25),
        Message(role="assistant", content="y" * 25),
        Message(role="user", content="z" * 25),
    ]
    messages = agent_loop._build_messages(history)

    non_system = [m for m in messages if m.get("role") != "system"]
    assert len(non_system) == 2
    assert non_system[0]["content"] == "y" * 25
    assert non_system[1]["content"] == "z" * 25


def test_build_messages_includes_repository_context(agent_loop, temp_workspace):
    target = temp_workspace / "context_target.py"
    target.write_text(
        "def fast_retry():\n"
        "    return 'retry ok'\n",
        encoding="utf-8",
    )

    history = [Message(role="user", content="How does retry work in this repo?")]
    messages = agent_loop._build_messages(history, query_hint="retry implementation")
    system_messages = [m for m in messages if m.get("role") == "system"]

    assert any("Repository Context (auto-selected):" in m.get("content", "") for m in system_messages)
    assert any("context_target.py" in m.get("content", "") for m in system_messages)


def test_should_enable_tools_is_false_for_simple_chat(agent_loop):
    assert agent_loop._should_enable_tools("Hello") is False
    assert agent_loop._should_enable_tools("Thanks!") is False
    assert agent_loop._should_enable_tools("How are you?") is False


def test_should_enable_tools_is_true_for_actionable_requests(agent_loop):
    assert agent_loop._should_enable_tools("Install skilltree skill") is True
    assert agent_loop._should_enable_tools("Search latest Python release notes") is True
    assert agent_loop._should_enable_tools("Run `git status`") is True


def test_call_provider_without_tools_omits_tool_payload(event_loop):
    from clawlet.agent.loop import AgentLoop
    from clawlet.agent.identity import IdentityLoader
    from clawlet.bus.queue import MessageBus
    from clawlet.providers.base import BaseProvider, LLMResponse
    from clawlet.tools.registry import ToolRegistry
    from clawlet.config import StorageConfig, SQLiteConfig
    import tempfile

    class CapturingProvider(BaseProvider):
        def __init__(self):
            self.last_kwargs = {}

        @property
        def name(self) -> str:
            return "capturing"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, messages, model=None, temperature=0.7, max_tokens=4096, **kwargs):
            self.last_kwargs = kwargs
            return LLMResponse(content="ok", model=model or "dummy-model", usage={}, finish_reason="stop")

        async def stream(self, messages, model=None, temperature=0.7, max_tokens=4096, **kwargs):
            yield "ok"

        async def close(self):
            pass

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "SOUL.md").write_text("# SOUL\n## Name\nTestAgent", encoding="utf-8")
        (workspace / "USER.md").write_text("# USER\n## Name\nHuman", encoding="utf-8")
        (workspace / "MEMORY.md").write_text("# MEMORY\nInitial", encoding="utf-8")
        (workspace / "HEARTBEAT.md").write_text("# HEARTBEAT\n- noop", encoding="utf-8")

        identity = IdentityLoader(workspace).load_all()
        provider = CapturingProvider()
        agent = AgentLoop(
            bus=MessageBus(),
            workspace=workspace,
            identity=identity,
            provider=provider,
            tools=ToolRegistry(),
            model="dummy-model",
            storage_config=StorageConfig(backend="sqlite", sqlite=SQLiteConfig(path=str(workspace / "clawlet.db"))),
        )
        event_loop.run_until_complete(agent._initialize_storage())

        messages = [{"role": "system", "content": "test"}, {"role": "user", "content": "hello"}]
        event_loop.run_until_complete(agent._call_provider_with_retry(messages, enable_tools=False))

        assert provider.last_kwargs.get("tools") is None
        assert provider.last_kwargs.get("tool_choice") is None
        event_loop.run_until_complete(agent.close())


def test_process_message_stops_on_tool_call_budget(event_loop):
    from clawlet.agent.loop import AgentLoop
    from clawlet.agent.identity import IdentityLoader
    from clawlet.bus.queue import InboundMessage, MessageBus
    from clawlet.providers.base import BaseProvider, LLMResponse
    from clawlet.tools.registry import ToolRegistry, BaseTool, ToolResult
    from clawlet.config import StorageConfig, SQLiteConfig
    import tempfile

    class LoopingToolProvider(BaseProvider):
        @property
        def name(self) -> str:
            return "looping"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, messages, model=None, temperature=0.7, max_tokens=4096, **kwargs):
            return LLMResponse(
                content="Working...",
                model=model or "dummy-model",
                usage={},
                finish_reason="tool_calls",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "dummy_tool", "arguments": "{}"},
                    }
                ],
            )

        async def stream(self, messages, model=None, temperature=0.7, max_tokens=4096, **kwargs):
            yield "ok"

        async def close(self):
            pass

    class DummyTool(BaseTool):
        @property
        def name(self) -> str:
            return "dummy_tool"

        @property
        def description(self) -> str:
            return "A test tool."

        async def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, output="done")

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "SOUL.md").write_text("# SOUL\n## Name\nTestAgent", encoding="utf-8")
        (workspace / "USER.md").write_text("# USER\n## Name\nHuman", encoding="utf-8")
        (workspace / "MEMORY.md").write_text("# MEMORY\nInitial", encoding="utf-8")
        (workspace / "HEARTBEAT.md").write_text("# HEARTBEAT\n- noop", encoding="utf-8")

        identity = IdentityLoader(workspace).load_all()
        tools = ToolRegistry()
        tools.register(DummyTool())

        agent = AgentLoop(
            bus=MessageBus(),
            workspace=workspace,
            identity=identity,
            provider=LoopingToolProvider(),
            tools=tools,
            model="dummy-model",
            storage_config=StorageConfig(backend="sqlite", sqlite=SQLiteConfig(path=str(workspace / "clawlet.db"))),
        )
        event_loop.run_until_complete(agent._initialize_storage())

        msg = InboundMessage(channel="test", chat_id="123", content="search recent updates")
        response = event_loop.run_until_complete(agent._process_message(msg))

        assert response is not None
        assert "avoid excessive tool calls" in response.content.lower()
        event_loop.run_until_complete(agent.close())


def test_schedules_autonomous_followup_on_commitment(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage

    # Force provider to return a commitment with no tool calls.
    agent_loop.provider.responses = ["I will install that now and report back."]
    agent_loop.provider.index = 0

    msg = InboundMessage(channel="test", chat_id="auto-1", content="Install skilltree")
    response = event_loop.run_until_complete(agent_loop._process_message(msg))

    assert response is not None
    assert "I will install that now" in response.content
    assert agent_loop.bus.inbound_size >= 1

    queued = event_loop.run_until_complete(agent_loop.bus.consume_inbound())
    assert queued.metadata.get("internal_autonomous_followup") is True
    assert queued.metadata.get("autonomous_followup_depth") == 1
    assert "Autonomous follow-up" in queued.content


def test_does_not_schedule_autonomous_followup_when_response_is_question(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage

    agent_loop.provider.responses = ["I can do that. Would you like me to proceed?"]
    agent_loop.provider.index = 0

    msg = InboundMessage(channel="test", chat_id="auto-2", content="Install skilltree")
    response = event_loop.run_until_complete(agent_loop._process_message(msg))

    assert response is not None
    assert "Would you like me to proceed?" in response.content
    assert agent_loop.bus.inbound_size == 0


def test_process_message_writes_runtime_events(agent_loop, temp_workspace, event_loop):
    from clawlet.bus.queue import InboundMessage
    import json

    msg = InboundMessage(channel="test", chat_id="events-1", content="List files in this folder")
    response = event_loop.run_until_complete(agent_loop._process_message(msg))

    assert response is not None

    event_log = temp_workspace / ".runtime" / "events.jsonl"
    assert event_log.exists()

    lines = [line for line in event_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    events = [json.loads(line) for line in lines]
    event_types = [ev.get("event_type") for ev in events]
    assert "RunStarted" in event_types
    assert "RunCompleted" in event_types


def test_interrupted_run_keeps_checkpoint(temp_workspace, event_loop):
    from clawlet.agent.identity import IdentityLoader
    from clawlet.agent.loop import AgentLoop
    from clawlet.bus.queue import InboundMessage, MessageBus
    from clawlet.providers.base import BaseProvider
    from clawlet.tools.registry import ToolRegistry
    from clawlet.config import RuntimeReplaySettings, RuntimeSettings, SQLiteConfig, StorageConfig

    class FailingProvider(BaseProvider):
        @property
        def name(self) -> str:
            return "failing"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, *args, **kwargs):
            raise RuntimeError("provider offline")

        async def stream(self, *args, **kwargs):
            yield ""

        async def close(self):
            pass

    identity = IdentityLoader(temp_workspace).load_all()
    runtime_cfg = RuntimeSettings(
        replay=RuntimeReplaySettings(
            enabled=True,
            directory=str(temp_workspace / ".runtime"),
            retention_days=7,
            redact_tool_outputs=False,
        )
    )
    agent = AgentLoop(
        bus=MessageBus(),
        workspace=temp_workspace,
        identity=identity,
        provider=FailingProvider(),
        tools=ToolRegistry(),
        model="dummy-model",
        storage_config=StorageConfig(backend="sqlite", sqlite=SQLiteConfig(path=str(temp_workspace / "clawlet.db"))),
        runtime_config=runtime_cfg,
    )
    event_loop.run_until_complete(agent._initialize_storage())

    response = event_loop.run_until_complete(
        agent._process_message(InboundMessage(channel="test", chat_id="c1", content="Do the task"))
    )
    assert response is not None
    assert "encountered an error" in response.content.lower()

    checkpoint_file = temp_workspace / ".runtime" / "checkpoints" / f"{agent._current_run_id}.json"
    assert checkpoint_file.exists()
    event_loop.run_until_complete(agent.close())


def test_resume_checkpoint_queues_inbound(agent_loop, temp_workspace, event_loop):
    from clawlet.runtime.recovery import RunCheckpoint

    cp = RunCheckpoint(
        run_id="recover-1",
        session_id="sess-1",
        channel="test",
        chat_id="chat-1",
        stage="interrupted",
        user_message="Continue patching files",
    )
    agent_loop._recovery_manager.save(cp)

    ok = event_loop.run_until_complete(agent_loop.resume_checkpoint("recover-1"))
    assert ok is True
    assert agent_loop.bus.inbound_size >= 1

    queued = event_loop.run_until_complete(agent_loop.bus.consume_inbound())
    assert queued.metadata.get("recovery_resume") is True
    assert queued.metadata.get("recovery_run_id") == "recover-1"


def test_engine_equivalence_smokecheck_reports_pass(temp_workspace):
    from clawlet.benchmarks.equivalence import run_engine_equivalence_smokecheck

    result = run_engine_equivalence_smokecheck(temp_workspace)
    assert result.passed is True
    assert result.shell_equivalent is True
    assert result.file_equivalent is True
    assert result.patch_equivalent is True


def test_rust_bridge_file_helpers_use_fake_module(monkeypatch):
    import sys
    import types
    from clawlet.runtime import rust_bridge

    fake = types.SimpleNamespace(
        read_text_file=lambda path: (True, "content", ""),
        write_text_file=lambda path, content: (True, len(content), ""),
        list_dir_entries=lambda path: (True, [("a.txt", False), ("src", True)], ""),
    )
    monkeypatch.setitem(sys.modules, "clawlet_rust_core", fake)

    assert rust_bridge.read_text_file("x.txt") == (True, "content", "")
    assert rust_bridge.write_text_file("x.txt", "abc") == (True, 3, "")
    assert rust_bridge.list_dir_entries(".") == (True, [("a.txt", False), ("src", True)], "")


def test_read_file_uses_rust_bridge_when_available(temp_workspace, event_loop, monkeypatch):
    from clawlet.tools.files import ReadFileTool

    target = temp_workspace / "a.txt"
    target.write_text("python", encoding="utf-8")
    monkeypatch.setattr("clawlet.tools.files.rust_read_text_file", lambda p: (True, "rust", ""))

    tool = ReadFileTool(allowed_dir=temp_workspace, use_rust_core=True)
    result = event_loop.run_until_complete(tool.execute("a.txt"))
    assert result.success is True
    assert result.output == "rust"
    assert result.data["engine"] == "rust"


def test_replay_run_detects_valid_event_flow(temp_workspace):
    from clawlet.runtime import RuntimeEvent, RuntimeEventStore, replay_run

    store = RuntimeEventStore(temp_workspace / ".runtime" / "events.jsonl")
    run_id = "run-replay-ok"
    store.append(RuntimeEvent(event_type="RunStarted", run_id=run_id, session_id="s1", payload={}))
    store.append(
        RuntimeEvent(
            event_type="ToolRequested",
            run_id=run_id,
            session_id="s1",
            payload={"tool_call_id": "t1", "tool_name": "list_dir"},
        )
    )
    store.append(
        RuntimeEvent(
            event_type="ToolStarted",
            run_id=run_id,
            session_id="s1",
            payload={"tool_call_id": "t1", "tool_name": "list_dir"},
        )
    )
    store.append(
        RuntimeEvent(
            event_type="ToolCompleted",
            run_id=run_id,
            session_id="s1",
            payload={"tool_call_id": "t1", "tool_name": "list_dir"},
        )
    )
    store.append(RuntimeEvent(event_type="RunCompleted", run_id=run_id, session_id="s1", payload={}))

    report = replay_run(store, run_id)
    assert report.passed is True
    assert report.has_start is True
    assert report.has_end is True
    assert report.tool_requested == 1
    assert report.tool_started == 1
    assert report.tool_finished == 1


def test_replay_run_detects_broken_tool_chain(temp_workspace):
    from clawlet.runtime import RuntimeEvent, RuntimeEventStore, replay_run

    store = RuntimeEventStore(temp_workspace / ".runtime" / "events.jsonl")
    run_id = "run-replay-bad"
    store.append(RuntimeEvent(event_type="RunStarted", run_id=run_id, session_id="s1", payload={}))
    store.append(
        RuntimeEvent(
            event_type="ToolCompleted",
            run_id=run_id,
            session_id="s1",
            payload={"tool_call_id": "t-missing", "tool_name": "list_dir"},
        )
    )
    store.append(RuntimeEvent(event_type="RunCompleted", run_id=run_id, session_id="s1", payload={}))

    report = replay_run(store, run_id)
    assert report.passed is False
    assert any("without request" in err for err in report.errors)


def test_verify_resume_equivalence_detects_successor(temp_workspace):
    from clawlet.runtime import (
        RecoveryManager,
        RunCheckpoint,
        RuntimeEvent,
        RuntimeEventStore,
        verify_resume_equivalence,
    )

    runtime_dir = temp_workspace / ".runtime"
    store = RuntimeEventStore(runtime_dir / "events.jsonl")
    recovery = RecoveryManager(runtime_dir / "checkpoints")

    source_run = "source-run-1"
    resumed_run = "resumed-run-1"

    recovery.save(
        RunCheckpoint(
            run_id=source_run,
            session_id="s1",
            channel="test",
            chat_id="c1",
            stage="interrupted",
            user_message="continue",
        )
    )

    store.append(RuntimeEvent(event_type="RunStarted", run_id=source_run, session_id="s1", payload={}))
    store.append(
        RuntimeEvent(
            event_type="ToolRequested",
            run_id=source_run,
            session_id="s1",
            payload={"tool_call_id": "a1", "tool_name": "list_dir"},
        )
    )
    store.append(RuntimeEvent(event_type="RunCompleted", run_id=source_run, session_id="s1", payload={}))

    store.append(
        RuntimeEvent(
            event_type="RunStarted",
            run_id=resumed_run,
            session_id="s1",
            payload={"recovery_resume": True, "recovery_resume_from": source_run},
        )
    )
    store.append(
        RuntimeEvent(
            event_type="ToolRequested",
            run_id=resumed_run,
            session_id="s1",
            payload={"tool_call_id": "b1", "tool_name": "list_dir"},
        )
    )
    store.append(RuntimeEvent(event_type="RunCompleted", run_id=resumed_run, session_id="s1", payload={}))

    report = verify_resume_equivalence(store, recovery, source_run)
    assert report.equivalent is True
    assert resumed_run in report.successors


def test_tool_failed_event_includes_failure_taxonomy(temp_workspace, event_loop):
    from clawlet.runtime import DeterministicToolRuntime, RuntimeEventStore, RuntimePolicyEngine, ToolCallEnvelope
    from clawlet.tools.registry import BaseTool, ToolRegistry, ToolResult

    class FailingTool(BaseTool):
        @property
        def name(self) -> str:
            return "failing_tool"

        @property
        def description(self) -> str:
            return "Always fails"

        async def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=False, output="", error="connection reset by peer")

    registry = ToolRegistry()
    registry.register(FailingTool())
    store = RuntimeEventStore(temp_workspace / ".runtime" / "events.jsonl")
    policy = RuntimePolicyEngine(allowed_modes=("read_only", "workspace_write", "elevated"))
    runtime = DeterministicToolRuntime(registry=registry, event_store=store, policy=policy)

    envelope = ToolCallEnvelope(
        run_id="taxonomy-run",
        session_id="s1",
        tool_call_id="tc1",
        tool_name="failing_tool",
        arguments={},
        execution_mode="workspace_write",
    )
    result, _ = event_loop.run_until_complete(runtime.execute(envelope))
    assert result.success is False

    events = store.iter_events(run_id="taxonomy-run")
    failed = [e for e in events if e.event_type == "ToolFailed"]
    assert failed
    payload = failed[-1].payload
    assert payload.get("failure_code") == "network_error"
    assert payload.get("retryable") is True


def test_provider_failure_classification_for_429():
    import httpx
    from clawlet.runtime.failures import classify_exception

    request = httpx.Request("GET", "https://example.com/models")
    response = httpx.Response(429, request=request)
    exc = httpx.HTTPStatusError("rate limit", request=request, response=response)
    info = classify_exception(exc)
    assert info.code == "provider_rate_limited"
    assert info.retryable is True


def test_reliability_report_counts_failure_channels(temp_workspace):
    from clawlet.runtime import RuntimeEvent, RuntimeEventStore, build_reliability_report

    store = RuntimeEventStore(temp_workspace / ".runtime" / "events.jsonl")
    run_id = "reliability-run-1"
    store.append(RuntimeEvent(event_type="RunStarted", run_id=run_id, session_id="s1", payload={}))
    store.append(
        RuntimeEvent(
            event_type="ToolCompleted",
            run_id=run_id,
            session_id="s1",
            payload={"tool_call_id": "t1", "tool_name": "list_dir"},
        )
    )
    store.append(
        RuntimeEvent(
            event_type="ToolFailed",
            run_id=run_id,
            session_id="s1",
            payload={"tool_call_id": "t2", "tool_name": "read_file", "failure_code": "not_found", "retryable": False},
        )
    )
    store.append(
        RuntimeEvent(
            event_type="ProviderFailed",
            run_id=run_id,
            session_id="s1",
            payload={"failure_code": "provider_rate_limited", "retryable": True},
        )
    )
    store.append(
        RuntimeEvent(
            event_type="StorageFailed",
            run_id=run_id,
            session_id="s1",
            payload={"error": "db locked"},
        )
    )
    store.append(
        RuntimeEvent(
            event_type="ChannelFailed",
            run_id=run_id,
            session_id="s1",
            payload={"error": "channel down"},
        )
    )
    store.append(
        RuntimeEvent(
            event_type="RunCompleted",
            run_id=run_id,
            session_id="s1",
            payload={"is_error": True},
        )
    )

    rr = build_reliability_report(store, run_id)
    assert rr.tool_completed == 1
    assert rr.tool_failed == 1
    assert rr.provider_failed == 1
    assert rr.storage_failed == 1
    assert rr.channel_failed == 1
    assert rr.total_failures == 4
    assert rr.run_completed_error is True
    assert rr.crash_like is True


def test_failure_taxonomy_smokecheck_passes(temp_workspace):
    from clawlet.benchmarks import run_failure_taxonomy_smokecheck

    ok, errors = run_failure_taxonomy_smokecheck(temp_workspace)
    assert ok is True
    assert errors == []


def test_reexecute_run_matches_recorded_read_only_tool(temp_workspace):
    from clawlet.runtime import RuntimeEvent, RuntimeEventStore, reexecute_run
    from clawlet.tools.registry import BaseTool, ToolRegistry, ToolResult

    class EchoTool(BaseTool):
        @property
        def name(self) -> str:
            return "echo_tool"

        @property
        def description(self) -> str:
            return "echo"

        async def execute(self, value: str = "", **kwargs) -> ToolResult:
            return ToolResult(success=True, output=value)

    store = RuntimeEventStore(temp_workspace / ".runtime" / "events.jsonl")
    run_id = "reexec-match-run"
    store.append(RuntimeEvent(event_type="RunStarted", run_id=run_id, session_id="s1", payload={}))
    store.append(
        RuntimeEvent(
            event_type="ToolRequested",
            run_id=run_id,
            session_id="s1",
            payload={
                "tool_call_id": "tc1",
                "tool_name": "echo_tool",
                "arguments": {"value": "hello"},
                "execution_mode": "read_only",
            },
        )
    )
    store.append(
        RuntimeEvent(
            event_type="ToolCompleted",
            run_id=run_id,
            session_id="s1",
            payload={"tool_call_id": "tc1", "tool_name": "echo_tool", "output": "hello"},
        )
    )
    store.append(RuntimeEvent(event_type="RunCompleted", run_id=run_id, session_id="s1", payload={"is_error": False}))

    registry = ToolRegistry()
    registry.register(EchoTool())
    report = reexecute_run(store, run_id, registry, allow_write=False)
    assert report.mismatched == 0
    assert report.matched == 1


def test_reexecute_run_skips_write_tool_by_default(temp_workspace):
    from clawlet.runtime import RuntimeEvent, RuntimeEventStore, reexecute_run
    from clawlet.tools.registry import BaseTool, ToolRegistry, ToolResult

    class WriteTool(BaseTool):
        @property
        def name(self) -> str:
            return "write_file"

        @property
        def description(self) -> str:
            return "write"

        async def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, output="ok")

    store = RuntimeEventStore(temp_workspace / ".runtime" / "events.jsonl")
    run_id = "reexec-skip-run"
    store.append(RuntimeEvent(event_type="RunStarted", run_id=run_id, session_id="s1", payload={}))
    store.append(
        RuntimeEvent(
            event_type="ToolRequested",
            run_id=run_id,
            session_id="s1",
            payload={
                "tool_call_id": "tc1",
                "tool_name": "write_file",
                "arguments": {"path": "x.txt", "content": "x"},
                "execution_mode": "workspace_write",
            },
        )
    )
    store.append(
        RuntimeEvent(
            event_type="ToolCompleted",
            run_id=run_id,
            session_id="s1",
            payload={"tool_call_id": "tc1", "tool_name": "write_file", "output": "ok"},
        )
    )
    store.append(RuntimeEvent(event_type="RunCompleted", run_id=run_id, session_id="s1", payload={"is_error": False}))

    registry = ToolRegistry()
    registry.register(WriteTool())
    report = reexecute_run(store, run_id, registry, allow_write=False)
    assert report.executed == 0
    assert report.skipped == 1
