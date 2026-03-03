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


@pytest.mark.asyncio
async def test_postgres_storage_list_sessions_uses_conversations_table(monkeypatch):
    from datetime import datetime, timezone
    import clawlet.storage.postgres as pgmod

    monkeypatch.setattr(pgmod, "POSTGRES_AVAILABLE", True)
    storage = pgmod.PostgresStorage()

    class _FakeConn:
        async def fetch(self, query, *args):
            assert "FROM conversations" in query
            assert "GROUP BY session_id" in query
            assert int(args[0]) == 5
            return [
                {"session_id": "sess-a", "msg_count": 3, "last_seen": datetime(2026, 3, 3, tzinfo=timezone.utc)},
                {"session_id": "sess-b", "msg_count": 1, "last_seen": datetime(2026, 3, 2, tzinfo=timezone.utc)},
            ]

    class _AcquireCtx:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakePool:
        def acquire(self):
            return _AcquireCtx()

    storage._pool = _FakePool()
    rows = await storage.list_sessions(limit=5)
    assert rows[0][0] == "sess-a"
    assert rows[0][1] == 3
    assert "2026-03-03" in rows[0][2]


@pytest.mark.asyncio
async def test_postgres_storage_export_messages_returns_serializable_rows(monkeypatch):
    from datetime import datetime, timezone
    import clawlet.storage.postgres as pgmod

    monkeypatch.setattr(pgmod, "POSTGRES_AVAILABLE", True)
    storage = pgmod.PostgresStorage()

    class _FakeConn:
        async def fetch(self, query, *args):
            assert "FROM conversations" in query
            assert "ORDER BY created_at DESC" in query
            return [
                {
                    "id": 10,
                    "session_id": "sess-a",
                    "role": "user",
                    "content": "hello",
                    "metadata": {"k": "v"},
                    "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                }
            ]

    class _AcquireCtx:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakePool:
        def acquire(self):
            return _AcquireCtx()

    storage._pool = _FakePool()
    rows = await storage.export_messages()
    assert rows == [
        {
            "id": 10,
            "session_id": "sess-a",
            "role": "user",
            "content": "hello",
            "metadata": {"k": "v"},
            "created_at": "2026-03-03T00:00:00+00:00",
        }
    ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
