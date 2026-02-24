"""
Tests for AgentLoop integration.
"""

import asyncio

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
