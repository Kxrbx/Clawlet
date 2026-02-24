"""
Storage backend interfaces and SQLite implementation.
"""

import aiosqlite
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from loguru import logger


@dataclass
class Message:
    """Stored message."""
    id: Optional[int]
    session_id: str
    role: str
    content: str
    created_at: datetime


class StorageBackend(ABC):
    """Abstract storage backend."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage (create tables, etc.)."""
        pass
    
    @abstractmethod
    async def store_message(self, session_id: str, role: str, content: str) -> int:
        """Store a message and return its ID."""
        pass
    
    @abstractmethod
    async def get_messages(self, session_id: str, limit: int = 100) -> List[Message]:
        """Get messages for a session."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the storage connection."""
        pass
    
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if storage is initialized and ready to use."""
        pass


class SQLiteStorage(StorageBackend):
    """SQLite storage backend."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        
    async def initialize(self) -> None:
        """Initialize the database."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._db = await aiosqlite.connect(self.db_path, timeout=30.0)
        
        # Create tables
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session 
            ON messages(session_id, created_at DESC)
        """)
        
        await self._db.commit()
        logger.info(f"SQLite storage initialized at {self.db_path}")
    
    async def store_message(self, session_id: str, role: str, content: str) -> int:
        """Store a message."""
        cursor = await self._db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        await self._db.commit()
        return cursor.lastrowid
    
    async def get_messages(self, session_id: str, limit: int = 100) -> List[Message]:
        """Get messages for a session in chronological order."""
        cursor = await self._db.execute(
            """
            SELECT id, session_id, role, content, created_at 
            FROM messages 
            WHERE session_id = ? 
            ORDER BY created_at ASC, id ASC 
            LIMIT ?
            """,
            (session_id, limit)
        )
        
        rows = await cursor.fetchall()
        
        messages = []
        for row in rows:  # Already in chronological order
            messages.append(Message(
                id=row[0],
                session_id=row[1],
                role=row[2],
                content=row[3],
                created_at=datetime.fromisoformat(row[4])
            ))
        
        return messages
    
    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            logger.info("SQLite storage closed")
    
    def is_initialized(self) -> bool:
        """Check if storage is initialized and ready."""
        return self._db is not None
    
    async def health_check(self) -> None:
        """Check database health."""
        if not self._db:
            raise RuntimeError("Database not initialized")
        try:
            await self._db.execute("SELECT 1")
        except Exception as e:
            raise RuntimeError(f"DB health check failed: {e}")
