"""
PostgreSQL storage backend.
"""

import asyncio
from datetime import datetime
from typing import Optional, Any
from pathlib import Path
import json

from loguru import logger

try:
    import asyncpg
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("asyncpg not installed. PostgreSQL storage unavailable.")


class PostgresStorage:
    """
    PostgreSQL storage backend for Clawlet.
    
    Stores:
    - Conversation history
    - Memory/context
    - Agent state
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "clawlet",
        user: str = "clawlet",
        password: str = "",
        min_pool_size: int = 2,
        max_pool_size: int = 10,
    ):
        """
        Initialize PostgreSQL storage.
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            min_pool_size: Minimum connection pool size
            max_pool_size: Maximum connection pool size
        """
        if not POSTGRES_AVAILABLE:
            raise RuntimeError("asyncpg not installed. Run: pip install asyncpg")
        
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        
        self._pool: Optional[asyncpg.Pool] = None
        
        logger.info(f"PostgresStorage configured: {host}:{port}/{database}")
    
    async def connect(self) -> None:
        """Establish connection pool."""
        if self._pool is not None:
            return
        
        self._pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            min_size=self.min_pool_size,
            max_size=self.max_pool_size,
        )
        
        # Create tables if they don't exist
        await self._create_tables()
        
        logger.info("PostgreSQL connection pool established")
    
    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")
    
    async def _create_tables(self) -> None:
        """Create necessary tables."""
        async with self._pool.acquire() as conn:
            # Conversations table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Memory table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id SERIAL PRIMARY KEY,
                    key VARCHAR(255) UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    category VARCHAR(100) DEFAULT 'general',
                    importance INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Agent state table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_state (
                    id SERIAL PRIMARY KEY,
                    agent_id VARCHAR(255) UNIQUE NOT NULL,
                    state JSONB NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_session 
                ON conversations(session_id, created_at DESC)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_category 
                ON memory(category, importance DESC)
            """)
            
            logger.debug("PostgreSQL tables created/verified")
    
    # Conversation methods
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict = None,
    ) -> int:
        """Add a message to conversation history."""
        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO conversations (session_id, role, content, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                session_id, role, content, json.dumps(metadata or {}),
            )
            return result["id"]
    
    async def get_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """Get conversation history for a session."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content, metadata, created_at
                FROM conversations
                WHERE session_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                session_id, limit,
            )
            
            # Reverse to get chronological order
            messages = []
            for row in reversed(rows):
                messages.append({
                    "role": row["role"],
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "timestamp": row["created_at"].isoformat(),
                })
            
            return messages
    
    async def clear_history(self, session_id: str) -> int:
        """Clear conversation history for a session."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM conversations WHERE session_id = $1",
                session_id,
            )
            return int(result.split()[-1])
    
    # Memory methods
    
    async def remember(
        self,
        key: str,
        value: str,
        category: str = "general",
        importance: int = 5,
    ) -> None:
        """Store something in memory."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory (key, value, category, importance, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    category = EXCLUDED.category,
                    importance = EXCLUDED.importance,
                    updated_at = NOW()
                """,
                key, value, category, importance,
            )
    
    async def recall(self, key: str) -> Optional[str]:
        """Recall something from memory."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM memory WHERE key = $1",
                key,
            )
            return row["value"] if row else None
    
    async def recall_by_category(self, category: str, limit: int = 20) -> list[dict]:
        """Recall memories by category."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT key, value, importance, created_at, updated_at
                FROM memory
                WHERE category = $1
                ORDER BY importance DESC, updated_at DESC
                LIMIT $2
                """,
                category, limit,
            )
            
            return [
                {
                    "key": row["key"],
                    "value": row["value"],
                    "importance": row["importance"],
                    "created": row["created_at"].isoformat(),
                    "updated": row["updated_at"].isoformat(),
                }
                for row in rows
            ]
    
    async def forget(self, key: str) -> bool:
        """Remove something from memory."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM memory WHERE key = $1",
                key,
            )
            return "DELETE 1" in result
    
    # Agent state methods
    
    async def save_state(self, agent_id: str, state: dict) -> None:
        """Save agent state."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_state (agent_id, state, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (agent_id) DO UPDATE SET
                    state = EXCLUDED.state,
                    updated_at = NOW()
                """,
                agent_id, json.dumps(state),
            )
    
    async def load_state(self, agent_id: str) -> Optional[dict]:
        """Load agent state."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state FROM agent_state WHERE agent_id = $1",
                agent_id,
            )
            return row["state"] if row else None
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
