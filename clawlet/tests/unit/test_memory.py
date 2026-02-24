"""Unit tests for MemoryManager."""

import tempfile
from pathlib import Path
import pytest

from clawlet.agent.memory import MemoryManager, MemoryEntry


def test_memory_manager_basic():
    """Test basic memory operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        mem = MemoryManager(workspace)
        
        # Remember something
        mem.remember("test_key", "test_value", category="test", importance=8)
        
        # Recall it
        val = mem.recall("test_key")
        assert val == "test_value"
        
        # Recall by category
        results = mem.recall_by_category("test", limit=10)
        assert len(results) >= 1
        assert any(e.key == "test_key" for e in results)


def test_memory_manager_forget():
    """Test forgetting memories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        mem = MemoryManager(workspace)
        
        mem.remember("key1", "value1")
        mem.remember("key2", "value2")
        
        assert mem.recall("key1") == "value1"
        
        mem.forget("key1")
        assert mem.recall("key1") is None
        assert mem.recall("key2") == "value2"


def test_memory_manager_save_long_term(tmp_path):
    """Test saving long-term memories to MEMORY.md."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    mem = MemoryManager(workspace)
    mem.remember("fact1", "User likes pizza", category="preferences", importance=9)
    mem.remember("fact2", "User is allergic to peanuts", category="health", importance=10)
    mem.remember("fact3", "User has a dog named Max", category="personal", importance=7)
    
    # Save to disk
    mem.save_long_term()
    
    # Read MEMORY.md
    memory_file = workspace / "MEMORY.md"
    assert memory_file.exists()
    content = memory_file.read_text()
    
    # Check that all facts are present
    assert "fact1" in content
    assert "pizza" in content
    assert "fact2" in content
    assert "peanuts" in content
    assert "fact3" in content
    assert "Max" in content


def test_memory_manager_stats():
    """Test memory statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        mem = MemoryManager(workspace)
        
        mem.remember("a", "1")
        mem.remember("b", "2")
        mem.remember("c", "3")
        mem.remember("d", "4")
        mem.remember("e", "5")
        
        stats = mem.get_stats()
        assert stats["short_term_count"] == 5
        assert stats["working_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
