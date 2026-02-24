"""
Tests for storage backends.
"""

import asyncio
import aiosqlite

def test_sqlite_storage_initializes(temp_workspace):
    from clawlet.storage.sqlite import SQLiteStorage
    
    db_path = temp_workspace / "test.db"
    storage = SQLiteStorage(db_path)
    
    async def run_test():
        await storage.initialize()
        assert db_path.exists()
        await storage.close()
    
    asyncio.run(run_test())


def test_sqlite_storage_crud(temp_workspace):
    from clawlet.storage.sqlite import SQLiteStorage, Message
    from datetime import datetime
    
    db_path = temp_workspace / "test.db"
    storage = SQLiteStorage(db_path)
    
    async def run_test():
        await storage.initialize()
        
        # Store messages
        msg_id1 = await storage.store_message("session1", "user", "Hello")
        msg_id2 = await storage.store_message("session1", "assistant", "Hi there")
        msg_id3 = await storage.store_message("session2", "user", "Other session")
        
        assert msg_id1 is not None
        assert msg_id2 is not None
        assert msg_id3 is not None
        
        # Retrieve messages for session1
        messages = await storage.get_messages("session1", limit=10)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"
        assert messages[1].role == "assistant"
        
        # Retrieve messages for session2
        messages2 = await storage.get_messages("session2", limit=10)
        assert len(messages2) == 1
        assert messages2[0].content == "Other session"
        
        await storage.close()
    
    asyncio.run(run_test())
