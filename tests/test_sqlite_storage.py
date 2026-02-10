"""
Tests for SQLite storage backend.
"""

import pytest
import tempfile
from pathlib import Path

from clawlet.storage.sqlite import SQLiteStorage
from clawlet.agent.memory import MemoryEntry


class TestSQLiteStorage:
    """Test SQLite storage operations."""
    
    @pytest.fixture
    async def db_path(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        # Cleanup
        if path.exists():
            path.unlink()
    
    @pytest.fixture
    async def storage(self, db_path):
        """Create storage instance."""
        storage = SQLiteStorage(db_path)
        await storage.initialize()
        yield storage
        await storage.close()
    
    @pytest.mark.asyncio
    async def test_initialize(self, db_path):
        """Test database initialization."""
        storage = SQLiteStorage(db_path)
        await storage.initialize()
        
        assert db_path.exists()
        
        await storage.close()
    
    @pytest.mark.asyncio
    async def test_save_memory(self, storage):
        """Test saving a memory entry."""
        entry = MemoryEntry(
            content="Test memory",
            importance=5,
            tags=["test"],
        )
        
        entry_id = await storage.save_memory(entry)
        
        assert entry_id is not None
        assert isinstance(entry_id, int)
        assert entry_id >= 1
    
    @pytest.mark.asyncio
    async def test_load_memory(self, storage):
        """Test loading a memory entry."""
        entry = MemoryEntry(
            content="Test memory",
            importance=7,
            tags=["important"],
        )
        
        entry_id = await storage.save_memory(entry)
        loaded = await storage.load_memory(entry_id)
        
        assert loaded is not None
        assert loaded.content == "Test memory"
        assert loaded.importance == 7
        assert loaded.tags == ["important"]
    
    @pytest.mark.asyncio
    async def test_list_memories(self, storage):
        """Test listing memory entries."""
        # Save multiple entries
        for i in range(5):
            entry = MemoryEntry(
                content=f"Memory {i}",
                importance=i,
            )
            await storage.save_memory(entry)
        
        memories = await storage.list_memories()
        
        assert len(memories) >= 5
    
    @pytest.mark.asyncio
    async def test_search_memories(self, storage):
        """Test searching memories."""
        entry1 = MemoryEntry(
            content="Python programming tips",
            importance=5,
            tags=["python", "programming"],
        )
        entry2 = MemoryEntry(
            content="JavaScript guide",
            importance=3,
            tags=["javascript", "programming"],
        )
        
        await storage.save_memory(entry1)
        await storage.save_memory(entry2)
        
        results = await storage.search_memories("python")
        
        assert len(results) >= 1
        assert any("python" in m.content.lower() for m in results)
    
    @pytest.mark.asyncio
    async def test_delete_memory(self, storage):
        """Test deleting a memory entry."""
        entry = MemoryEntry(
            content="To be deleted",
            importance=1,
        )
        
        entry_id = await storage.save_memory(entry)
        await storage.delete_memory(entry_id)
        
        loaded = await storage.load_memory(entry_id)
        assert loaded is None
    
    @pytest.mark.asyncio
    async def test_save_conversation(self, storage):
        """Test saving conversation history."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        
        await storage.save_conversation("user_123", messages)
        
        loaded = await storage.load_conversation("user_123")
        
        assert len(loaded) >= 2
        assert loaded[-1]["content"] == "Hi there!"
    
    @pytest.mark.asyncio
    async def test_increment_message_count(self, storage):
        """Test incrementing message counter."""
        await storage.increment_message_count("user_123")
        await storage.increment_message_count("user_123")
        
        count = await storage.get_message_count("user_123")
        
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_get_stats(self, storage):
        """Test getting storage statistics."""
        # Add some data
        entry = MemoryEntry(content="Test", importance=5)
        await storage.save_memory(entry)
        await storage.save_conversation("user_1", [{"role": "user", "content": "Test"}])
        await storage.increment_message_count("user_1")
        
        stats = await storage.get_stats()
        
        assert "memory_count" in stats
        assert "conversation_count" in stats
        assert "total_messages" in stats
