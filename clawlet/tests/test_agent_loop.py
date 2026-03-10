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


def test_tool_call_signature_is_stable_for_duplicate_suppression(agent_loop):
    from clawlet.agent.loop import ToolCall

    first = ToolCall(id="1", name="fetch_url", arguments={"url": "https://example.com", "max_chars": 100})
    second = ToolCall(id="2", name="fetch_url", arguments={"max_chars": 100, "url": "https://example.com"})

    assert agent_loop._tool_call_signature(first) == agent_loop._tool_call_signature(second)


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
    import sqlite3
    db_path = temp_workspace / "clawlet.db"
    assert db_path.exists()

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            (agent_loop._session_id,),
        )
        count = int(cursor.fetchone()[0])
    finally:
        conn.close()
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


def test_list_dir_expands_home_directory_paths(temp_workspace, event_loop, monkeypatch):
    """list_dir should treat ~/ as the user's home before security checks."""
    from clawlet.tools.files import ListDirTool

    monkeypatch.setenv("HOME", str(temp_workspace))
    (temp_workspace / "sample.txt").write_text("ok", encoding="utf-8")

    tool = ListDirTool(allowed_dir=temp_workspace)
    result = event_loop.run_until_complete(tool.execute("~/"))

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


def test_build_messages_keeps_large_recent_tool_output(agent_loop):
    """Large tool outputs should remain in the next prompt instead of being dropped."""
    agent_loop.CONTEXT_WINDOW = 10
    history = [
        Message(role="user", content="Read this document and follow the instructions."),
        Message(role="tool", content="A" * 15050, metadata={"tool_name": "fetch_url", "tool_call_id": "tc1"}),
        Message(role="assistant", content="I am reviewing the instructions."),
    ]
    messages = agent_loop._build_messages(history)

    non_system = [m for m in messages if m.get("role") != "system"]
    assert len(non_system) == 3
    assert non_system[1]["role"] == "tool"
    assert non_system[1]["content"] == "A" * 15050


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


def test_build_messages_includes_separate_memory_context(agent_loop):
    agent_loop.memory.remember(
        "favorite_color",
        "User prefers green accents in interfaces",
        category="preferences",
        importance=9,
    )

    history = [Message(role="user", content="What design direction should I use?")]
    messages = agent_loop._build_messages(history)
    system_messages = [m for m in messages if m.get("role") == "system"]

    assert any("## Relevant Memories" in m.get("content", "") for m in system_messages)
    assert any("favorite_color" in m.get("content", "") for m in system_messages)


def test_should_enable_tools_is_false_for_simple_chat(agent_loop):
    assert agent_loop._should_enable_tools("Hello") is False
    assert agent_loop._should_enable_tools("Thanks!") is False
    assert agent_loop._should_enable_tools("How are you?") is False


def test_should_enable_tools_is_true_for_actionable_requests(agent_loop):
    assert agent_loop._should_enable_tools("Install skilltree skill") is True
    assert agent_loop._should_enable_tools("Search latest Python release notes") is True
    assert agent_loop._should_enable_tools("Run `git status`") is True


def test_requires_confirmation_for_policy_controlled_mode(agent_loop):
    from clawlet.agent.loop import ToolCall

    agent_loop._runtime_policy.require_approval_for.add("workspace_write")
    tool_call = ToolCall(id="tc-1", name="write_file", arguments={"path": "notes.txt", "content": "x"})

    reason = agent_loop._requires_confirmation(tool_call)
    assert "Policy requires approval" in reason


def test_confirmation_response_includes_telegram_buttons(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage
    from clawlet.providers.base import LLMResponse

    class ConfirmingProvider:
        @property
        def name(self) -> str:
            return "confirming"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, *args, **kwargs):
            return LLMResponse(
                content="I need approval before editing the file.",
                model="dummy-model",
                usage={},
                finish_reason="tool_calls",
                tool_calls=[
                    {
                        "id": "tc-confirm",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": "{\"path\":\"notes.txt\",\"content\":\"hello\"}",
                        },
                    }
                ],
            )

        async def stream(self, *args, **kwargs):
            yield ""

        async def close(self):
            pass

    agent_loop.provider = ConfirmingProvider()
    agent_loop._runtime_policy.require_approval_for.add("workspace_write")

    response = event_loop.run_until_complete(
        agent_loop._process_message(
            InboundMessage(channel="telegram", chat_id="approval-chat", content="Write notes.txt")
        )
    )

    assert response is not None
    assert "confirm" in response.content.lower()
    assert response.metadata["telegram_pending_approval"]["tool_name"] == "write_file"
    assert response.metadata["telegram_buttons"][0][0]["text"] == "Approve"


def test_progress_updates_are_published_for_telegram_runs(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage
    from clawlet.providers.base import LLMResponse
    from clawlet.tools.registry import ToolResult

    class ProgressProvider:
        def __init__(self):
            self.index = 0

        @property
        def name(self) -> str:
            return "progress"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, *args, **kwargs):
            self.index += 1
            if self.index == 1:
                return LLMResponse(
                    content="Reading the file first.",
                    model="dummy-model",
                    usage={},
                    finish_reason="tool_calls",
                    tool_calls=[
                        {
                            "id": "tc-progress",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": "{\"path\":\"README.md\"}",
                            },
                        }
                    ],
                )
            return LLMResponse(content="Done.", model="dummy-model", usage={}, finish_reason="stop")

        async def stream(self, *args, **kwargs):
            yield ""

        async def close(self):
            pass

    async def fake_execute_tool(tc, approved=False):
        return ToolResult(success=True, output="read ok")

    agent_loop.provider = ProgressProvider()
    agent_loop._execute_tool = fake_execute_tool  # type: ignore[assignment]

    response = event_loop.run_until_complete(
        agent_loop._process_message(
            InboundMessage(channel="telegram", chat_id="progress-chat", content="Read README.md")
        )
    )

    assert response is not None
    progress_messages = []
    while agent_loop.bus.outbound_size:
        outbound = event_loop.run_until_complete(agent_loop.bus.consume_outbound())
        if (outbound.metadata or {}).get("progress"):
            progress_messages.append(outbound)

    assert progress_messages
    assert any(msg.metadata.get("progress_event") == "provider_started" for msg in progress_messages)
    assert any(msg.metadata.get("progress_event") == "tool_requested" for msg in progress_messages)


class _FakeSentMessage:
    def __init__(self, message_id: int):
        self.message_id = message_id


class _FakeTelegramBot:
    def __init__(self):
        self.sent_messages = []
        self.edited_messages = []
        self.chat_actions = []
        self.commands = []
        self.menu_button_calls = 0

    async def send_message(self, **kwargs):
        self.sent_messages.append(kwargs)
        return _FakeSentMessage(len(self.sent_messages))

    async def edit_message_text(self, **kwargs):
        self.edited_messages.append(kwargs)

    async def send_chat_action(self, **kwargs):
        self.chat_actions.append(kwargs)

    async def set_my_commands(self, commands):
        self.commands = commands

    async def set_chat_menu_button(self, **kwargs):
        self.menu_button_calls += 1


class _FakeTelegramApp:
    def __init__(self):
        self.bot = _FakeTelegramBot()


class _FakeCallbackQuery:
    def __init__(self, data: str, chat_id: str):
        from types import SimpleNamespace

        self.data = data
        self.message = SimpleNamespace(chat=SimpleNamespace(id=int(chat_id)))
        self.answered = False
        self.edits = []

    async def answer(self, *args, **kwargs):
        self.answered = True

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)


def test_telegram_channel_streams_progress_then_finalizes(agent_loop, event_loop):
    from clawlet.bus.queue import OutboundMessage
    from clawlet.channels.telegram import TelegramChannel

    channel = TelegramChannel(
        bus=agent_loop.bus,
        config={
            "token": "test-token",
            "stream_mode": "progress",
            "stream_update_interval_seconds": 0.0,
            "disable_web_page_preview": True,
        },
        agent=agent_loop,
    )
    channel.app = _FakeTelegramApp()
    channel._running = True

    event_loop.run_until_complete(
        channel.send(
            OutboundMessage(
                channel="telegram",
                chat_id="123",
                content="Thinking about the next step.",
                metadata={"progress": True, "progress_event": "provider_started"},
            )
        )
    )
    event_loop.run_until_complete(
        channel.send(
            OutboundMessage(
                channel="telegram",
                chat_id="123",
                content="Final answer.",
                metadata={},
            )
        )
    )

    assert len(channel.app.bot.sent_messages) == 1
    assert channel.app.bot.edited_messages
    assert channel._ensure_chat_state("123")["active_stream_message_id"] is None


def test_telegram_callback_updates_stream_mode_and_persists(agent_loop, event_loop):
    from types import SimpleNamespace

    from clawlet.channels.telegram import TelegramChannel

    channel = TelegramChannel(
        bus=agent_loop.bus,
        config={"token": "test-token", "stream_mode": "progress", "stream_update_interval_seconds": 0.0},
        agent=agent_loop,
    )
    channel.app = _FakeTelegramApp()
    channel._running = True
    update = SimpleNamespace(
        callback_query=_FakeCallbackQuery("settings:stream_mode:verbose_debug", "123"),
        effective_user=SimpleNamespace(id=77, first_name="Tester"),
    )

    event_loop.run_until_complete(channel._handle_callback_query(update, None))

    assert channel._ensure_chat_state("123")["stream_mode"] == "verbose_debug"
    persisted = Path(channel._ui_state_path).read_text(encoding="utf-8")
    assert "verbose_debug" in persisted


def test_telegram_approval_callback_publishes_confirm_message(agent_loop, event_loop):
    from types import SimpleNamespace

    from clawlet.channels.telegram import TelegramChannel

    channel = TelegramChannel(
        bus=agent_loop.bus,
        config={"token": "test-token", "stream_mode": "progress", "stream_update_interval_seconds": 0.0},
        agent=agent_loop,
    )
    channel.app = _FakeTelegramApp()
    channel._running = True
    channel._remember_pending_approval(
        "123",
        {
            "token": "654321",
            "tool_name": "write_file",
            "reason": "Policy requires approval",
            "details": "Tool: write_file",
        },
    )
    update = SimpleNamespace(
        callback_query=_FakeCallbackQuery("approval:approve:654321", "123"),
        effective_user=SimpleNamespace(id=77, first_name="Tester"),
    )

    event_loop.run_until_complete(channel._handle_callback_query(update, None))
    inbound = event_loop.run_until_complete(channel.bus.consume_inbound())
    event_loop.run_until_complete(channel._stop_typing("123"))

    assert inbound.content == "confirm 654321"
    assert inbound.metadata["approval_token"] == "654321"


def test_telegram_text_menu_status_button_is_handled_locally(agent_loop, event_loop):
    from types import SimpleNamespace

    from clawlet.channels.telegram import TelegramChannel

    class ReplyRecorder:
        def __init__(self):
            self.calls = []
            self.text = "Status"

        async def reply_text(self, text, **kwargs):
            self.calls.append({"text": text, "kwargs": kwargs})

    message = ReplyRecorder()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=77, first_name="Tester", username="tester"),
        message=message,
    )

    channel = TelegramChannel(
        bus=agent_loop.bus,
        config={"token": "test-token", "stream_mode": "progress"},
        agent=agent_loop,
    )
    channel.app = _FakeTelegramApp()
    channel._running = True

    event_loop.run_until_complete(channel._handle_message(update, None))

    assert message.calls
    assert "Telegram status" in message.calls[0]["text"]
    assert agent_loop.bus.inbound_size == 0


def test_telegram_text_menu_heartbeat_button_shows_disabled_quiet_hours(agent_loop, event_loop):
    from types import SimpleNamespace

    from clawlet.channels.telegram import TelegramChannel

    class ReplyRecorder:
        def __init__(self):
            self.calls = []
            self.text = "Heartbeat"

        async def reply_text(self, text, **kwargs):
            self.calls.append({"text": text, "kwargs": kwargs})

    message = ReplyRecorder()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=77, first_name="Tester", username="tester"),
        message=message,
    )

    channel = TelegramChannel(
        bus=agent_loop.bus,
        config={
            "token": "test-token",
            "stream_mode": "progress",
            "heartbeat": {
                "enabled": True,
                "interval_minutes": 30,
                "quiet_hours_start": 0,
                "quiet_hours_end": 0,
                "target": "last",
                "ack_max_chars": 24,
                "proactive_enabled": False,
            },
        },
        agent=agent_loop,
    )
    channel.app = _FakeTelegramApp()
    channel._running = True

    event_loop.run_until_complete(channel._handle_message(update, None))

    assert message.calls
    assert "Heartbeat status" in message.calls[0]["text"]
    assert "Quiet hours: <code>disabled</code>" in message.calls[0]["text"]
    assert agent_loop.bus.inbound_size == 0


def test_telegram_channel_does_not_trust_model_html_by_default(agent_loop, event_loop):
    from clawlet.bus.queue import OutboundMessage
    from clawlet.channels.telegram import TelegramChannel

    channel = TelegramChannel(
        bus=agent_loop.bus,
        config={"token": "test-token", "stream_mode": "progress"},
        agent=agent_loop,
    )
    channel.app = _FakeTelegramApp()
    channel._running = True

    event_loop.run_until_complete(
        channel.send(
            OutboundMessage(
                channel="telegram",
                chat_id="123",
                content="<b>model text</b>",
                metadata={},
            )
        )
    )

    assert channel.app.bot.sent_messages
    assert channel.app.bot.sent_messages[0]["text"] == "&lt;b&gt;model text&lt;/b&gt;"


def test_telegram_verbose_debug_progress_keeps_code_format(agent_loop, event_loop):
    from clawlet.bus.queue import OutboundMessage
    from clawlet.channels.telegram import TelegramChannel

    channel = TelegramChannel(
        bus=agent_loop.bus,
        config={"token": "test-token", "stream_mode": "verbose_debug", "stream_update_interval_seconds": 0.0},
        agent=agent_loop,
    )
    channel.app = _FakeTelegramApp()
    channel._running = True
    channel._ensure_chat_state("123")["stream_mode"] = "verbose_debug"

    event_loop.run_until_complete(
        channel.send(
            OutboundMessage(
                channel="telegram",
                chat_id="123",
                content="Running `read_file`.",
                metadata={
                    "progress": True,
                    "progress_event": "tool_started",
                    "progress_detail": "read_file",
                },
            )
        )
    )

    assert channel.app.bot.sent_messages
    assert "<code>" in channel.app.bot.sent_messages[0]["text"]


def test_parallel_batch_eligible_for_read_only_calls(agent_loop):
    from clawlet.agent.loop import ToolCall

    calls = [
        ToolCall(id="tc-1", name="read_file", arguments={"path": "README.md"}),
        ToolCall(id="tc-2", name="list_dir", arguments={"path": "."}),
    ]
    assert agent_loop._should_parallelize_tool_calls(calls) is True


def test_parallel_batch_disabled_for_write_or_serial_lane(agent_loop):
    from clawlet.agent.loop import ToolCall

    write_calls = [
        ToolCall(id="tc-1", name="read_file", arguments={"path": "README.md"}),
        ToolCall(id="tc-2", name="write_file", arguments={"path": "x.txt", "content": "x"}),
    ]
    serial_lane_calls = [
        ToolCall(id="tc-1", name="read_file", arguments={"path": "README.md"}),
        ToolCall(id="tc-2", name="list_dir", arguments={"path": ".", "_lane": "serial:forced"}),
    ]

    assert agent_loop._should_parallelize_tool_calls(write_calls) is False
    assert agent_loop._should_parallelize_tool_calls(serial_lane_calls) is False


def test_parallel_batch_respects_max_parallel_read_tools(agent_loop, event_loop):
    from clawlet.agent.loop import ToolCall
    from clawlet.tools.registry import ToolResult

    running = 0
    peak = 0

    async def fake_execute(tc, approved=False):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.03)
        running -= 1
        return ToolResult(success=True, output=f"ok:{tc.id}")

    agent_loop._max_parallel_read_tools = 2
    agent_loop._execute_tool = fake_execute  # type: ignore[assignment]

    calls = [
        ToolCall(id=f"tc-{i}", name="read_file", arguments={"path": "README.md"})
        for i in range(4)
    ]
    out = event_loop.run_until_complete(agent_loop._execute_tool_batch_parallel(calls))
    assert len(out) == 4
    assert peak <= 2


def test_plan_tool_execution_groups_for_mixed_calls(agent_loop):
    from clawlet.agent.loop import ToolCall

    calls = [
        ToolCall(id="tc-1", name="read_file", arguments={"path": "README.md"}),
        ToolCall(id="tc-2", name="list_dir", arguments={"path": "."}),
        ToolCall(id="tc-3", name="write_file", arguments={"path": "x.txt", "content": "x"}),
        ToolCall(id="tc-4", name="read_file", arguments={"path": "MEMORY.md"}),
        ToolCall(id="tc-5", name="read_file", arguments={"path": "SOUL.md"}),
    ]

    groups = agent_loop._plan_tool_execution_groups(calls)
    assert [g[0] for g in groups] == ["parallel", "serial", "parallel"]
    assert [tc.id for tc in groups[0][1]] == ["tc-1", "tc-2"]
    assert [tc.id for tc in groups[1][1]] == ["tc-3"]
    assert [tc.id for tc in groups[2][1]] == ["tc-4", "tc-5"]


def test_execute_tool_calls_optimized_uses_parallel_and_serial(agent_loop, event_loop):
    from clawlet.agent.loop import ToolCall
    from clawlet.tools.registry import ToolResult

    calls = [
        ToolCall(id="tc-1", name="read_file", arguments={"path": "README.md"}),
        ToolCall(id="tc-2", name="list_dir", arguments={"path": "."}),
        ToolCall(id="tc-3", name="write_file", arguments={"path": "x.txt", "content": "x"}),
        ToolCall(id="tc-4", name="read_file", arguments={"path": "MEMORY.md"}),
        ToolCall(id="tc-5", name="read_file", arguments={"path": "SOUL.md"}),
    ]

    trace: list[str] = []

    async def fake_parallel(batch):
        trace.append("parallel:" + ",".join(tc.id for tc in batch))
        return [(tc, ToolResult(success=True, output=f"p:{tc.id}")) for tc in batch]

    async def fake_execute(tc, approved=False):
        trace.append(f"serial:{tc.id}")
        return ToolResult(success=True, output=f"s:{tc.id}")

    agent_loop._execute_tool_batch_parallel = fake_parallel  # type: ignore[assignment]
    agent_loop._execute_tool = fake_execute  # type: ignore[assignment]

    out = event_loop.run_until_complete(agent_loop._execute_tool_calls_optimized(calls))
    assert len(out) == 5
    assert trace == [
        "parallel:tc-1,tc-2",
        "serial:tc-3",
        "parallel:tc-4,tc-5",
    ]
    assert agent_loop._tool_stats["parallel_batches"] >= 2
    assert agent_loop._tool_stats["parallel_batch_tools"] >= 4
    assert agent_loop._tool_stats["serial_batches"] >= 1


def test_plan_tool_execution_groups_when_parallel_disabled(agent_loop):
    from clawlet.agent.loop import ToolCall

    agent_loop._enable_parallel_read_batches = False
    calls = [
        ToolCall(id="tc-1", name="read_file", arguments={"path": "README.md"}),
        ToolCall(id="tc-2", name="list_dir", arguments={"path": "."}),
    ]
    groups = agent_loop._plan_tool_execution_groups(calls)
    assert groups == [("serial", [calls[0]]), ("serial", [calls[1]])]
    assert agent_loop._should_parallelize_tool_calls(calls) is False


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


def test_identity_loader_excludes_autogen_memory_section_from_identity(event_loop):
    from clawlet.agent.identity import IdentityLoader
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "SOUL.md").write_text("# SOUL\n## Name\nTestAgent", encoding="utf-8")
        (workspace / "USER.md").write_text("# USER\n## Name\nHuman", encoding="utf-8")
        (workspace / "MEMORY.md").write_text(
            "# MEMORY\nManual identity note\n\n"
            "<!-- CLAWLET_MEMORY_AUTOGEN_START -->\n"
            "## Auto-Saved Memories\n"
            "- **fact1**: Episodic memory\n"
            "<!-- CLAWLET_MEMORY_AUTOGEN_END -->\n",
            encoding="utf-8",
        )
        (workspace / "HEARTBEAT.md").write_text("# HEARTBEAT\n- noop", encoding="utf-8")

        identity = IdentityLoader(workspace).load_all()

        assert "Manual identity note" in identity.memory
        assert "Episodic memory" not in identity.memory


def test_process_message_stops_on_tool_call_budget(event_loop):
    from clawlet.agent.loop import AgentLoop
    from clawlet.agent.identity import IdentityLoader
    from clawlet.bus.queue import InboundMessage, MessageBus
    from clawlet.providers.base import BaseProvider, LLMResponse
    from clawlet.tools.registry import ToolRegistry, BaseTool, ToolResult
    from clawlet.config import StorageConfig, SQLiteConfig
    import tempfile

    class LoopingToolProvider(BaseProvider):
        def __init__(self):
            self.calls = 0

        @property
        def name(self) -> str:
            return "looping"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, messages, model=None, temperature=0.7, max_tokens=4096, **kwargs):
            self.calls += 1
            return LLMResponse(
                content="Working...",
                model=model or "dummy-model",
                usage={},
                finish_reason="tool_calls",
                tool_calls=[
                    {
                        "id": f"call_{self.calls}",
                        "type": "function",
                        "function": {"name": "dummy_tool", "arguments": f'{{"step": {self.calls}}}'},
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
            max_tool_calls_per_message=3,
            storage_config=StorageConfig(backend="sqlite", sqlite=SQLiteConfig(path=str(workspace / "clawlet.db"))),
        )
        event_loop.run_until_complete(agent._initialize_storage())

        msg = InboundMessage(channel="test", chat_id="123", content="search recent updates")
        response = event_loop.run_until_complete(agent._process_message(msg))

        assert response is not None
        assert "avoid excessive tool calls" in response.content.lower()
        event_loop.run_until_complete(agent.close())


def test_commitment_without_action_does_not_send_empty_promise(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage

    # Force provider to return commitments with no tool calls.
    agent_loop.provider.responses = ["I will install that now and report back."]
    agent_loop.provider.index = 0

    msg = InboundMessage(channel="test", chat_id="auto-1", content="Install skilltree")
    response = event_loop.run_until_complete(agent_loop._process_message(msg))

    assert response is not None
    assert "I will install that now" not in response.content
    assert "did not execute the promised action" in response.content
    assert agent_loop.bus.inbound_size == 0


def test_does_not_schedule_autonomous_followup_when_response_is_question(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage

    agent_loop.provider.responses = ["I can do that. Would you like me to proceed?"]
    agent_loop.provider.index = 0

    msg = InboundMessage(channel="test", chat_id="auto-2", content="Install skilltree")
    response = event_loop.run_until_complete(agent_loop._process_message(msg))

    assert response is not None
    assert "Would you like me to proceed?" in response.content
    assert agent_loop.bus.inbound_size == 0


def test_commitment_without_action_forces_same_turn_followthrough(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage

    agent_loop.provider.responses = [
        "I'll do that now.",
        "Done. I could not complete installation because the remote endpoint requires a manual claim step.",
    ]
    agent_loop.provider.index = 0

    response = event_loop.run_until_complete(
        agent_loop._process_message(InboundMessage(channel="test", chat_id="followthrough-1", content="Install Moltbook"))
    )

    assert response is not None
    assert response.content.startswith("Done.")
    assert agent_loop.bus.inbound_size == 0


def test_post_tool_let_me_fetch_is_treated_as_followthrough_not_final_answer(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage
    from clawlet.providers.base import LLMResponse

    class SequencedProvider:
        def __init__(self):
            self.index = 0

        @property
        def name(self) -> str:
            return "sequenced"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, *args, **kwargs):
            self.index += 1
            if self.index == 1:
                return LLMResponse(
                    content="I'll fetch the URL to read the instructions for joining Moltbook.",
                    model="dummy-model",
                    usage={},
                    finish_reason="stop",
                    tool_calls=[
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {
                                "name": "fetch_url",
                                "arguments": "{\"url\":\"https://www.moltbook.com/skill.md\"}",
                            },
                        }
                    ],
                )
            if self.index == 2:
                return LLMResponse(
                    content="The content was truncated. Let me fetch the full document to see all the instructions.",
                    model="dummy-model",
                    usage={},
                    finish_reason="stop",
                )
            return LLMResponse(
                content="Done. I fetched what I could and the next blocker is that registration requires a real API call.",
                model="dummy-model",
                usage={},
                finish_reason="stop",
            )

        async def stream(self, *args, **kwargs):
            yield ""

        async def close(self):
            pass

    async def fake_execute_tool(tc, approved=False):
        from clawlet.tools.registry import ToolResult

        return ToolResult(
            success=True,
            output="URL: https://www.moltbook.com/skill.md\nStatus: 200\nNote: content truncated to 12000 characters",
        )

    agent_loop.provider = SequencedProvider()
    agent_loop._execute_tool = fake_execute_tool  # type: ignore[assignment]

    response = event_loop.run_until_complete(
        agent_loop._process_message(
            InboundMessage(
                channel="test",
                chat_id="followthrough-2",
                content="Read https://www.moltbook.com/skill.md and follow the instructions to join Moltbook",
            )
        )
    )

    assert response is not None
    assert response.content.startswith("Done.")
    assert "Let me fetch the full document" not in response.content


def test_post_tool_intermediate_status_gets_finalization_pass(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage
    from clawlet.providers.base import LLMResponse

    class SequencedProvider:
        def __init__(self):
            self.index = 0

        @property
        def name(self) -> str:
            return "sequenced"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, *args, **kwargs):
            self.index += 1
            if self.index == 1:
                return LLMResponse(
                    content="I'll inspect the file first.",
                    model="dummy-model",
                    usage={},
                    finish_reason="stop",
                    tool_calls=[
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": "{\"path\":\"README.md\"}",
                            },
                        }
                    ],
                )
            if self.index == 2:
                return LLMResponse(
                    content="I found the relevant section. Next I'll summarize the fix.",
                    model="dummy-model",
                    usage={},
                    finish_reason="stop",
                )
            return LLMResponse(
                content="The fix is to update the README example to use the current command.",
                model="dummy-model",
                usage={},
                finish_reason="stop",
            )

        async def stream(self, *args, **kwargs):
            yield ""

        async def close(self):
            pass

    async def fake_execute_tool(tc, approved=False):
        from clawlet.tools.registry import ToolResult

        return ToolResult(success=True, output="README content")

    agent_loop.provider = SequencedProvider()
    agent_loop._execute_tool = fake_execute_tool  # type: ignore[assignment]

    response = event_loop.run_until_complete(
        agent_loop._process_message(
            InboundMessage(channel="test", chat_id="finalization-1", content="Check README and fix the issue")
        )
    )

    assert response is not None
    assert response.content == "The fix is to update the README example to use the current command."
    assert "Next I'll summarize" not in response.content


def test_iteration_cap_after_tool_use_gets_one_finalization_only_pass(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage
    from clawlet.providers.base import LLMResponse

    class SequencedProvider:
        def __init__(self):
            self.index = 0

        @property
        def name(self) -> str:
            return "sequenced"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, *args, **kwargs):
            self.index += 1
            if self.index == 1:
                return LLMResponse(
                    content="I'll inspect the document.",
                    model="dummy-model",
                    usage={},
                    finish_reason="stop",
                    tool_calls=[
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {
                                "name": "fetch_url",
                                "arguments": "{\"url\":\"https://example.com/doc.md\"}",
                            },
                        }
                    ],
                )
            return LLMResponse(
                content="I fetched the document and completed the requested step.",
                model="dummy-model",
                usage={},
                finish_reason="stop",
            )

        async def stream(self, *args, **kwargs):
            yield ""

        async def close(self):
            pass

    async def fake_execute_tool(tc, approved=False):
        from clawlet.tools.registry import ToolResult

        return ToolResult(success=True, output="full document content")

    agent_loop.provider = SequencedProvider()
    agent_loop._execute_tool = fake_execute_tool  # type: ignore[assignment]
    agent_loop.max_iterations = 1

    response = event_loop.run_until_complete(
        agent_loop._process_message(
            InboundMessage(channel="test", chat_id="iteration-finalize-1", content="Read the doc and do the task")
        )
    )

    assert response is not None
    assert response.content == "I fetched the document and completed the requested step."


def test_finalization_only_pass_strips_tool_markup_and_incomplete_promise(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage
    from clawlet.providers.base import LLMResponse

    class SequencedProvider:
        def __init__(self):
            self.index = 0

        @property
        def name(self) -> str:
            return "sequenced"

        def get_default_model(self) -> str:
            return "dummy-model"

        async def complete(self, *args, **kwargs):
            self.index += 1
            if self.index == 1:
                return LLMResponse(
                    content="I'll inspect the heartbeat file.",
                    model="dummy-model",
                    usage={},
                    finish_reason="stop",
                    tool_calls=[
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": "{\"path\":\"HEARTBEAT.md\"}",
                            },
                        }
                    ],
                )
            return LLMResponse(
                content=(
                    "Great! I've completed the setup.\n\n"
                    "Now I need to update HEARTBEAT.md.<tool_call>\n"
                    "<function=edit_file><parameter=path>HEARTBEAT.md</parameter></function>\n"
                    "</tool_call>"
                ),
                model="dummy-model",
                usage={},
                finish_reason="stop",
            )

        async def stream(self, *args, **kwargs):
            yield ""

        async def close(self):
            pass

    async def fake_execute_tool(tc, approved=False):
        from clawlet.tools.registry import ToolResult

        return ToolResult(success=True, output="heartbeat contents")

    agent_loop.provider = SequencedProvider()
    agent_loop._execute_tool = fake_execute_tool  # type: ignore[assignment]
    agent_loop.max_iterations = 1

    response = event_loop.run_until_complete(
        agent_loop._process_message(
            InboundMessage(channel="test", chat_id="iteration-finalize-2", content="Finish the setup")
        )
    )

    assert response is not None
    assert "<tool_call>" not in response.content
    assert "I did not execute the remaining step in this turn." in response.content
    assert response.content.startswith("Partial progress:")


def test_internal_autonomous_followup_cannot_end_with_second_empty_promise(agent_loop, event_loop):
    from clawlet.bus.queue import InboundMessage

    agent_loop.provider.responses = [
        "I will install that now and report back.",
        "I will install it right away.",
        "I will handle it now.",
    ]
    agent_loop.provider.index = 0

    initial = event_loop.run_until_complete(
        agent_loop._process_message(InboundMessage(channel="test", chat_id="auto-3", content="Install skilltree"))
    )
    assert initial is not None
    assert "did not execute the promised action" in initial.content
    assert agent_loop.bus.inbound_size == 0


def test_suppresses_trivial_heartbeat_ack(agent_loop):
    from clawlet.bus.queue import OutboundMessage

    response = OutboundMessage(
        channel="test",
        chat_id="hb-1",
        content="HEARTBEAT_OK",
        metadata={"heartbeat": True, "ack_max_chars": 24},
    )
    assert agent_loop._should_suppress_outbound(response) is True


def test_does_not_suppress_non_trivial_heartbeat_message(agent_loop):
    from clawlet.bus.queue import OutboundMessage

    response = OutboundMessage(
        channel="test",
        chat_id="hb-2",
        content="I checked updates and queued a follow-up on the release gate failures.",
        metadata={"heartbeat": True, "ack_max_chars": 24},
    )
    assert agent_loop._should_suppress_outbound(response) is False


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


def test_rust_bridge_apply_unified_patch_uses_fake_module(monkeypatch):
    import sys
    import types
    from clawlet.runtime import rust_bridge

    fake = types.SimpleNamespace(
        apply_unified_patch=lambda original, patch: (True, "patched\n", ""),
    )
    monkeypatch.setitem(sys.modules, "clawlet_rust_core", fake)

    result = rust_bridge.apply_unified_patch("before\n", "@@ -1,1 +1,1 @@\n-before\n+patched\n")
    assert result == (True, "patched\n", "")


def test_apply_patch_tool_uses_rust_bridge_when_available(temp_workspace, event_loop, monkeypatch):
    from clawlet.tools.patch import ApplyPatchTool

    target = temp_workspace / "a.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    patch = "@@ -1,2 +1,2 @@\n alpha\n-beta\n+beta_done\n"

    monkeypatch.setattr("clawlet.tools.patch.rust_apply_unified_patch", lambda original, diff: (True, "rust\n", ""))
    tool = ApplyPatchTool(allowed_dir=temp_workspace, use_rust_core=True)

    result = event_loop.run_until_complete(tool.execute("a.txt", patch))
    assert result.success is True
    assert result.data["engine"] == "rust"
    assert target.read_text(encoding="utf-8") == "rust\n"


def test_apply_patch_tool_falls_back_to_python_when_rust_unavailable(temp_workspace, event_loop, monkeypatch):
    from clawlet.tools.patch import ApplyPatchTool

    target = temp_workspace / "a.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    patch = "@@ -1,2 +1,2 @@\n alpha\n-beta\n+beta_done\n"

    monkeypatch.setattr("clawlet.tools.patch.rust_apply_unified_patch", lambda original, diff: None)
    tool = ApplyPatchTool(allowed_dir=temp_workspace, use_rust_core=True)

    result = event_loop.run_until_complete(tool.execute("a.txt", patch))
    assert result.success is True
    assert result.data["engine"] == "python"
    assert "beta_done" in target.read_text(encoding="utf-8")


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


def test_render_tool_result_does_not_truncate(agent_loop):
    from clawlet.tools.registry import ToolResult

    raw = "x" * 10000
    rendered = agent_loop._render_tool_result(ToolResult(success=True, output=raw))
    assert rendered == raw


def test_fetch_url_returns_full_content_when_max_chars_omitted(event_loop):
    from clawlet.tools.fetch_url import FetchUrlTool

    class MockResponse:
        status_code = 200
        headers = {"content-type": "text/plain"}
        text = "A" * 15050
        url = "https://example.com/doc.md"

    class MockClient:
        async def get(self, url: str):
            return MockResponse()

    tool = FetchUrlTool()
    tool._client = MockClient()  # type: ignore[assignment]
    result = event_loop.run_until_complete(tool.execute("https://example.com/doc.md"))

    assert result.success is True
    assert "Note: content truncated" not in result.output
    assert "A" * 15050 in result.output


def test_shell_tool_executes_redirection_and_chaining_in_dangerous_mode(temp_workspace, event_loop):
    from clawlet.tools.shell import ShellTool

    tool = ShellTool(
        workspace=temp_workspace,
        allowed_commands=["printf"],
        allow_dangerous=True,
        use_rust_core=False,
    )
    result = event_loop.run_until_complete(
        tool.execute('printf "alpha" > first.txt && printf "beta" > second.txt')
    )

    assert result.success is True
    assert (temp_workspace / "first.txt").read_text(encoding="utf-8") == "alpha"
    assert (temp_workspace / "second.txt").read_text(encoding="utf-8") == "beta"


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


def test_tool_failed_event_preserves_output_and_data(temp_workspace, event_loop):
    from clawlet.runtime import DeterministicToolRuntime, RuntimeEventStore, RuntimePolicyEngine, ToolCallEnvelope
    from clawlet.tools.registry import BaseTool, ToolRegistry, ToolResult

    class VerboseFailingTool(BaseTool):
        @property
        def name(self) -> str:
            return "verbose_failing_tool"

        @property
        def description(self) -> str:
            return "Fails with detailed output"

        async def execute(self, **kwargs) -> ToolResult:
            return ToolResult(
                success=False,
                output="[stderr]\ncurl: (3) URL rejected: Malformed input to a URL function",
                error="Exit code: 3",
                data={"stderr": "curl: (3) URL rejected: Malformed input to a URL function", "returncode": 3},
            )

    registry = ToolRegistry()
    registry.register(VerboseFailingTool())
    store = RuntimeEventStore(temp_workspace / ".runtime" / "events.jsonl")
    policy = RuntimePolicyEngine(allowed_modes=("read_only", "workspace_write", "elevated"))
    runtime = DeterministicToolRuntime(registry=registry, event_store=store, policy=policy)

    envelope = ToolCallEnvelope(
        run_id="verbose-failure-run",
        session_id="s1",
        tool_call_id="tc1",
        tool_name="verbose_failing_tool",
        arguments={},
        execution_mode="workspace_write",
    )
    result, _ = event_loop.run_until_complete(runtime.execute(envelope))
    assert result.success is False

    events = store.iter_events(run_id="verbose-failure-run")
    failed = [e for e in events if e.event_type == "ToolFailed"]
    assert failed
    payload = failed[-1].payload
    assert "curl: (3)" in payload.get("output", "")
    assert payload.get("data", {}).get("returncode") == 3


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
