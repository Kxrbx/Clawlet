"""Storage backend interfaces and SQLite implementation."""

import json
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import aiosqlite
from loguru import logger


@dataclass
class Message:
    """Stored message."""
    id: Optional[int]
    session_id: str
    role: str
    content: str
    created_at: datetime
    metadata: dict = field(default_factory=dict)


class StorageBackend(ABC):
    """Abstract storage backend."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage (create tables, etc.)."""
        pass
    
    @abstractmethod
    async def store_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """Store a message and return its ID."""
        pass
    
    @abstractmethod
    async def get_messages(self, session_id: str, limit: int = 100) -> List[Message]:
        """Get messages for a session."""
        pass
    
    @abstractmethod
    async def clear_messages(self, session_id: str) -> int:
        """Clear all messages for a session."""
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
    
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Initialize the database."""
        async with self._lock:
            if self._db is not None:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            db = await aiosqlite.connect(str(self.db_path), timeout=30.0)
            self._db = db
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("PRAGMA temp_store=MEMORY")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await self._ensure_metadata_column()
            await self._ensure_runtime_meta_table()
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, created_at DESC)
                """
            )
            await self._set_schema_version(1)
            await db.commit()
            logger.info(f"SQLite storage initialized at {self.db_path}")
    
    async def store_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """Store a message."""
        if self._db is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            cursor = await self._db.execute(
                "INSERT INTO messages (session_id, role, content, metadata) VALUES (?, ?, ?, ?)",
                (session_id, role, content, json.dumps(metadata or {}, ensure_ascii=True, sort_keys=True)),
            )
            await self._db.commit()
            row_id = cursor.lastrowid
            return int(row_id) if row_id is not None else 0
    
    async def get_messages(self, session_id: str, limit: int = 100) -> List[Message]:
        """Get messages for a session in chronological order."""
        if self._db is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            cursor = await self._db.execute(
                """
                SELECT id, session_id, role, content, metadata, created_at
                FROM (
                    SELECT id, session_id, role, content, metadata, created_at
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                )
                ORDER BY created_at ASC, id ASC
                """,
                (session_id, limit),
            )
            rows = await cursor.fetchall()

        messages: list[Message] = []
        for row in rows:
            messages.append(
                Message(
                    id=row[0],
                    session_id=row[1],
                    role=row[2],
                    content=row[3],
                    created_at=datetime.fromisoformat(row[5]),
                    metadata=self._decode_metadata(row[4]),
                )
            )
        return messages
    
    async def clear_messages(self, session_id: str) -> int:
        """Clear all messages for a session."""
        if self._db is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            cursor = await self._db.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (session_id,),
            )
            await self._db.commit()
            return int(cursor.rowcount)
    
    async def close(self) -> None:
        """Close the database connection."""
        async with self._lock:
            if self._db:
                db = self._db
                self._db = None
                await db.close()
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

    async def _ensure_metadata_column(self) -> None:
        """Backfill metadata storage on older databases."""
        assert self._db is not None
        db = self._db
        columns = {
            str(row[1]).lower()
            for row in await (await db.execute("PRAGMA table_info(messages)")).fetchall()
        }
        if "metadata" in columns:
            return
        await db.execute("ALTER TABLE messages ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
        await db.commit()

    async def _ensure_runtime_meta_table(self) -> None:
        assert self._db is not None
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    async def _set_schema_version(self, version: int) -> None:
        assert self._db is not None
        await self._db.execute(f"PRAGMA user_version = {int(version)}")
        await self._db.execute(
            "INSERT OR REPLACE INTO runtime_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(int(version))),
        )

    @staticmethod
    def _decode_metadata(raw: Optional[str]) -> dict:
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}
