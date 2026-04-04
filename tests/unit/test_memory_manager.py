from __future__ import annotations

from pathlib import Path
import re

import pytest

from clawlet.agent.memory import MemoryManager


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_manager_remember_recall_forget_and_recent(tmp_workspace: Path):
    memory = MemoryManager(tmp_workspace)
    await memory.initialize()

    await memory.remember("pref", "Prefers concise updates", category="preferences", importance=9)

    assert await memory.recall("pref") == "Prefers concise updates"
    assert [entry.key for entry in await memory.recent(limit=5)] == ["pref"]
    assert await memory.forget("pref") is True
    assert await memory.recall("pref") is None

    await memory.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_manager_search_context_and_curation(tmp_workspace: Path):
    memory = MemoryManager(tmp_workspace)
    await memory.initialize()

    await memory.remember("project_status", "Working on async sqlite migration", category="projects", importance=9)
    await memory.append_note("Remember deadline for async sqlite migration", category="tasks", source="test")

    matches = await memory.search("sqlite", limit=5)
    assert any(entry.key == "project_status" for entry in matches)

    context = await memory.get_context(max_entries=5, query="sqlite")
    assert "project_status" in context

    promoted = await memory.curate_from_recent_daily_notes(days=1, limit=5)
    assert any("async sqlite migration" in item for item in promoted)

    await memory.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_manager_sanitizes_and_compacts_low_value_entries(tmp_workspace: Path):
    memory = MemoryManager(tmp_workspace)
    await memory.initialize()

    assert MemoryManager._sanitize_memory_value("moltbook_sk_secret_123") == "[redacted]"
    assert MemoryManager._is_low_value_memory("hello") is True

    await memory.remember("noise", "hello", importance=2)
    assert await memory.recall("noise") is None

    await memory.remember("real", "Important project preference", importance=8)
    memory._long_term["real"].value = "hello"
    removed = await memory.compact_long_term()

    assert removed == 1
    assert "real" not in memory._long_term

    await memory.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_manager_persists_async_memory_and_uuid_daily_notes(tmp_workspace: Path):
    memory = MemoryManager(tmp_workspace)
    await memory.initialize()

    await memory.remember("pref", "Prefers async persistence", category="preferences", importance=9)
    await memory.append_note("Track async write migration", category="tasks", source="test")
    note_entries = await memory.recent(limit=10, category="tasks")
    note_keys = [entry.key for entry in note_entries if entry.metadata.get("scope") == "daily_note"]

    assert len(note_keys) == 1
    assert re.fullmatch(r"note_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", note_keys[0])

    await memory.close()

    reloaded = MemoryManager(tmp_workspace)
    await reloaded.initialize()

    assert await reloaded.recall("pref") == "Prefers async persistence"
    assert "Track async write migration" in reloaded.get_recent_daily_notes(days=1, limit=20)

    await reloaded.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_manager_short_term_recall_keeps_latest_entries(tmp_workspace: Path):
    memory = MemoryManager(tmp_workspace, max_short_term=2)
    await memory.initialize()

    await memory.remember("alpha", "first", importance=6)
    await memory.remember("beta", "second", importance=6)
    await memory.remember("alpha", "first updated", importance=7)
    await memory.remember("gamma", "third", importance=6)

    assert len(memory._short_term) == 2
    assert await memory.recall("alpha") == "first updated"
    assert await memory.recall("gamma") == "third"
    assert "beta" not in memory._short_term

    await memory.close()
