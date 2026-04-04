from __future__ import annotations

from pathlib import Path

import pytest

from clawlet.storage.sqlite import SQLiteStorage


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sqlite_storage_persists_messages_across_reopen(tmp_path: Path):
    db_path = tmp_path / "messages.db"
    storage = SQLiteStorage(db_path)
    await storage.initialize()

    message_id = await storage.store_message(
        session_id="session-1",
        role="assistant",
        content="stored asynchronously",
        metadata={"source": "test"},
    )

    assert message_id > 0
    await storage.close()

    reopened = SQLiteStorage(db_path)
    await reopened.initialize()
    messages = await reopened.get_messages("session-1", limit=5)

    assert len(messages) == 1
    assert messages[0].content == "stored asynchronously"
    assert messages[0].metadata == {"source": "test"}

    cleared = await reopened.clear_messages("session-1")
    assert cleared == 1
    assert await reopened.get_messages("session-1", limit=5) == []

    await reopened.close()
