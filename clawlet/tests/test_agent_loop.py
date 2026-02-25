"""
Tests for AgentLoop integration.
"""

import asyncio

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
