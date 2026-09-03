"""SessionDB — unified session truth (Hermes-style SessionDB, v1).

Adds three things on top of the existing ``clawlet.db`` (same file, new
tables — fully backward compatible, existing ``messages`` table untouched):

- ``sessions``: one row per conversation incl. sub-agent lineage
  (``parent_session_id``), ``task_kind``, ``profile_snapshot`` JSON,
  ``source`` (cli|telegram|...) and the frozen ``system_prompt`` used
  for resume fidelity.
- ``messages_fts``: FTS5 index over message content for ``session_search``
  without an auxiliary LLM (~ms instead of ~30s). Falls back to ``LIKE``
  scans when FTS5 is unavailable.
- :meth:`SessionStore.session_search`: full-text search across sessions.

WAL + NORMAL synchronous + foreign keys mirror ``SQLiteStorage`` so both
connections share the same durability profile.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite
from loguru import logger

SCHEMA_VERSION = 1


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    parent_session_id: str = ""
    task_kind: str = ""
    profile_snapshot: dict = field(default_factory=dict)
    system_prompt: str = ""
    source: str = ""
    created_at: str = ""


class SessionStore:
    """Session metadata + full-text search over the shared clawlet.db."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._fts_available = False

    async def initialize(self) -> None:
        async with self._lock:
            if self._db is not None:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            db = await aiosqlite.connect(str(self.db_path), timeout=30.0)
            self._db = db
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    parent_session_id TEXT NOT NULL DEFAULT '',
                    task_kind TEXT NOT NULL DEFAULT '',
                    profile_snapshot TEXT NOT NULL DEFAULT '{}',
                    system_prompt TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_parent "
                "ON sessions(parent_session_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_kind ON sessions(task_kind)"
            )
            self._fts_available = await self._ensure_fts(db)
            await db.commit()
            logger.info(
                f"SessionStore initialized at {self.db_path} (fts={self._fts_available})"
            )

    async def _ensure_fts(self, db: aiosqlite.Connection) -> bool:
        """Create FTS5 index + sync triggers. Return False when unsupported."""
        try:
            await db.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts "
                "USING fts5(session_id, role, content, tokenize='trigram')"
            )
            await db.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_messages_fts_insert
                AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid, session_id, role, content)
                    VALUES (new.id, new.session_id, new.role, new.content);
                END
                """
            )
            await db.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_messages_fts_delete
                AFTER DELETE ON messages BEGIN
                    DELETE FROM messages_fts WHERE rowid = old.id;
                END
                """
            )
            # Backfill rows predating the triggers (idempotent-ish: skip
            # rowids already indexed).
            await db.execute(
                """
                INSERT INTO messages_fts(rowid, session_id, role, content)
                SELECT id, session_id, role, content FROM messages
                WHERE id NOT IN (SELECT rowid FROM messages_fts)
                """
            )
            return True
        except Exception as e:
            logger.warning(f"FTS5 unavailable, session_search falls back to LIKE: {e}")
            return False

    async def record_session(self, record: SessionRecord) -> None:
        """Upsert a session row (idempotent, safe to call per turn)."""
        if self._db is None:
            raise RuntimeError("SessionStore not initialized")
        async with self._lock:
            await self._db.execute(
                """
                INSERT INTO sessions
                    (session_id, parent_session_id, task_kind, profile_snapshot, system_prompt, source)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    parent_session_id = excluded.parent_session_id,
                    task_kind = excluded.task_kind,
                    profile_snapshot = excluded.profile_snapshot,
                    system_prompt = excluded.system_prompt,
                    source = excluded.source
                """,
                (
                    record.session_id,
                    record.parent_session_id,
                    record.task_kind,
                    json.dumps(
                        record.profile_snapshot,
                        ensure_ascii=True,
                        sort_keys=True,
                        default=str,
                    ),
                    record.system_prompt,
                    record.source,
                ),
            )
            await self._db.commit()

    async def get_session(self, session_id: str) -> SessionRecord | None:
        if self._db is None:
            raise RuntimeError("SessionStore not initialized")
        async with self._lock:
            cursor = await self._db.execute(
                "SELECT session_id, parent_session_id, task_kind, profile_snapshot,"
                " system_prompt, source, created_at FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        try:
            snapshot = json.loads(row[3] or "{}")
        except Exception:
            snapshot = {}
        return SessionRecord(
            session_id=row[0],
            parent_session_id=row[1] or "",
            task_kind=row[2] or "",
            profile_snapshot=snapshot if isinstance(snapshot, dict) else {},
            system_prompt=row[4] or "",
            source=row[5] or "",
            created_at=row[6] or "",
        )

    async def session_search(
        self, query: str, *, limit: int = 20, session_id: str = ""
    ) -> list[dict[str, Any]]:
        """Full-text search over message content (FTS5 trigram, LIKE fallback).

        Returns ``[{session_id, role, snippet}]`` — snippets are bounded to
        200 chars. Never raises on bad queries (returns []).
        """
        query = (query or "").strip()
        if not query or self._db is None:
            return []
        try:
            async with self._lock:
                if self._fts_available:
                    sql = (
                        "SELECT session_id, role,"
                        " substr(content, 1, 200) FROM messages_fts"
                        " WHERE messages_fts MATCH ?"
                    )
                    params: tuple[Any, ...] = (query,)
                    if session_id:
                        sql += " AND session_id = ?"
                        params = (query, session_id)
                    sql += " LIMIT ?"
                    cursor = await self._db.execute(sql, (*params, limit))
                else:
                    like = f"%{query}%"
                    if session_id:
                        cursor = await self._db.execute(
                            "SELECT session_id, role, substr(content, 1, 200) FROM messages"
                            " WHERE content LIKE ? AND session_id = ? LIMIT ?",
                            (like, session_id, limit),
                        )
                    else:
                        cursor = await self._db.execute(
                            "SELECT session_id, role, substr(content, 1, 200) FROM messages"
                            " WHERE content LIKE ? LIMIT ?",
                            (like, limit),
                        )
                rows = await cursor.fetchall()
        except Exception as e:
            logger.warning(f"session_search failed ({e}); returning []")
            return []
        return [{"session_id": r[0], "role": r[1], "snippet": r[2]} for r in rows]

    async def close(self) -> None:
        async with self._lock:
            if self._db:
                db = self._db
                self._db = None
                await db.close()

    def is_initialized(self) -> bool:
        return self._db is not None
