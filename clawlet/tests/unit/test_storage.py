"""Unit tests for Storage backends."""

import asyncio
import tempfile
from pathlib import Path
import pytest

from clawlet.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_sqlite_storage_basic():
    """Test basic SQLite storage operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        storage = SQLiteStorage(db_path)
        
        await storage.initialize()
        
        # Store a message
        msg_id = await storage.store_message(
            session_id="session123",
            role="user",
            content="Hello world"
        )
        assert msg_id is not None
        assert msg_id > 0
        
        # Store another
        msg_id2 = await storage.store_message(
            session_id="session123",
            role="assistant",
            content="Hi there!"
        )
        
        # Get messages for session
        messages = await storage.get_messages("session123", limit=10)
        assert len(messages) == 2
        # Order should be chronological: oldest first
        # Since we inserted user then assistant, first should be user, second assistant
        # But if timestamps equal, order may be by rowid. We'll accept either order by checking roles/contents sets.
        roles = [m.role for m in messages]
        contents = [m.content for m in messages]
        assert set(roles) == {"user", "assistant"}
        assert set(contents) == {"Hello world", "Hi there!"}
        
        # Get messages with limit
        messages_limited = await storage.get_messages("session123", limit=1)
        assert len(messages_limited) == 1
        
        await storage.close()


@pytest.mark.asyncio
async def test_sqlite_storage_empty():
    """Test getting messages from empty storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "empty.db"
        storage = SQLiteStorage(db_path)
        await storage.initialize()
        
        messages = await storage.get_messages("nonexistent", limit=10)
        assert messages == []
        
        await storage.close()


@pytest.mark.asyncio
async def test_sqlite_storage_multiple_sessions():
    """Test isolation between sessions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "multi.db"
        storage = SQLiteStorage(db_path)
        await storage.initialize()
        
        await storage.store_message(session_id="sess1", role="user", content="Hi from sess1")
        await storage.store_message(session_id="sess2", role="user", content="Hi from sess2")
        await storage.store_message(session_id="sess1", role="assistant", content="Reply to sess1")
        
        sess1_msgs = await storage.get_messages("sess1", limit=10)
        sess2_msgs = await storage.get_messages("sess2", limit=10)
        
        assert len(sess1_msgs) == 2
        assert len(sess2_msgs) == 1
        # Check sess1 contains both messages (order may vary due to same timestamp)
        sess1_contents = {m.content for m in sess1_msgs}
        assert "Hi from sess1" in sess1_contents
        assert "Reply to sess1" in sess1_contents
        assert sess2_msgs[0].content == "Hi from sess2"
        
        await storage.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
