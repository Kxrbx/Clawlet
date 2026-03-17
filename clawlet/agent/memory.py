"""
Memory management for agent context and history.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json
import sqlite3
from typing import Optional, Any
from pathlib import Path
import re

from loguru import logger
from clawlet.workspace_layout import get_workspace_layout


AUTOGEN_START = "<!-- CLAWLET_MEMORY_AUTOGEN_START -->"
AUTOGEN_END = "<!-- CLAWLET_MEMORY_AUTOGEN_END -->"
UTC = timezone.utc


@dataclass
class MemoryEntry:
    """A single memory entry."""
    key: str
    value: str
    category: str = "general"
    importance: int = 5  # 1-10 scale
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class MemoryManager:
    """
    Manages agent memory and context.
    
    Memory types:
    - Short-term: Recent conversation history
    - Long-term: Persistent memories stored in MEMORY.md
    - Working: Current task context
    """
    
    def __init__(self, workspace: Path, max_short_term: int = 50):
        """
        Initialize memory manager.
        
        Args:
            workspace: Path to workspace directory
            max_short_term: Maximum short-term memories to keep
        """
        self.workspace = workspace
        self.max_short_term = max_short_term
        self.db_path = self.workspace / "memory.db"
        
        self._short_term: list[MemoryEntry] = []
        self._long_term: dict[str, MemoryEntry] = {}
        self._working: dict[str, Any] = {}
        self._base_memory_content: str = ""
        self._db: Optional[sqlite3.Connection] = None
        self._fts_enabled = False

        self._initialize_db()
        
        # Load long-term memories from MEMORY.md
        self._load_long_term()
        self._load_long_term_from_db()
        removed = self.compact_long_term()
        if removed:
            logger.info(f"Compacted {removed} low-value long-term memories")
        
        logger.info(f"MemoryManager initialized with {len(self._long_term)} long-term memories")
    
    def _load_long_term(self) -> None:
        """Load long-term memories from MEMORY.md."""
        memory_file = self.workspace / "MEMORY.md"
        if not memory_file.exists():
            logger.debug(f"No MEMORY.md found at {memory_file}")
            return
        
        try:
            content = memory_file.read_text(encoding="utf-8")
            base_content, generated_content = self._split_memory_sections(content)
            self._base_memory_content = base_content.strip()
            self._long_term["__file__"] = MemoryEntry(
                key="__file__",
                value=content,
                category="system",
                importance=10,
            )
            if not self._db_has_memory_entries():
                self._load_structured_entries(generated_content or content)
                self._sync_long_term_to_db()
        except Exception as e:
            logger.warning(f"Failed to load MEMORY.md: {e}")

    def _initialize_db(self) -> None:
        """Initialize the SQLite-backed memory store."""
        try:
            self.workspace.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    importance INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            self._db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_entries_category_updated
                ON memory_entries(category, updated_at DESC)
                """
            )
            try:
                self._db.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_entries_fts
                    USING fts5(key, value, category)
                    """
                )
                self._fts_enabled = True
            except Exception as e:
                logger.debug(f"FTS5 unavailable for memory DB {self.db_path}: {e}")
                self._fts_enabled = False
            self._db.commit()
        except Exception as e:
            logger.warning(f"Failed to initialize memory DB {self.db_path}: {e}")
            self._db = None

    def _db_has_memory_entries(self) -> bool:
        if self._db is None:
            return False
        try:
            row = self._db.execute("SELECT COUNT(*) FROM memory_entries").fetchone()
            return bool(row and int(row[0]) > 0)
        except Exception as e:
            logger.warning(f"Failed to inspect memory DB {self.db_path}: {e}")
            return False

    def _load_long_term_from_db(self) -> None:
        """Load structured memories from SQLite if available."""
        if self._db is None:
            return
        try:
            rows = self._db.execute(
                """
                SELECT key, value, category, importance, created_at, updated_at, metadata
                FROM memory_entries
                ORDER BY updated_at DESC, key ASC
                """
            ).fetchall()
        except Exception as e:
            logger.warning(f"Failed to load memories from DB {self.db_path}: {e}")
            return

        for row in rows:
            entry = self._entry_from_row(row)
            if entry is not None:
                self._long_term[entry.key] = entry

    @staticmethod
    def _fts_query(text: str) -> str:
        tokens = [token for token in re.findall(r"[A-Za-z0-9_]+", text.lower()) if token]
        return " ".join(tokens[:8])

    def _dedupe_entries(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        """Deduplicate memory entries by key, preferring the freshest/highest-signal copy."""
        deduped: dict[str, MemoryEntry] = {}
        for entry in entries:
            if entry.key == "__file__":
                continue
            existing = deduped.get(entry.key)
            if existing is None:
                deduped[entry.key] = entry
                continue
            if (
                entry.updated_at > existing.updated_at
                or (
                    entry.updated_at == existing.updated_at
                    and entry.importance >= existing.importance
                )
            ):
                deduped[entry.key] = entry
        return list(deduped.values())

    def _all_entries(self) -> list[MemoryEntry]:
        """Return the merged in-memory view without duplicate keys."""
        return self._dedupe_entries(self._short_term + list(self._long_term.values()))

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.now(UTC)

    def _upsert_db_entry(self, entry: MemoryEntry) -> None:
        if self._db is None or entry.key == "__file__":
            return
        try:
            self._db.execute(
                """
                INSERT INTO memory_entries (key, value, category, importance, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    category=excluded.category,
                    importance=excluded.importance,
                    updated_at=excluded.updated_at,
                    metadata=excluded.metadata
                """,
                (
                    entry.key,
                    entry.value,
                    entry.category,
                    int(entry.importance),
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                    json.dumps(entry.metadata or {}, sort_keys=True),
                ),
            )
            if self._fts_enabled:
                self._db.execute("DELETE FROM memory_entries_fts WHERE key = ?", (entry.key,))
                self._db.execute(
                    "INSERT INTO memory_entries_fts (key, value, category) VALUES (?, ?, ?)",
                    (entry.key, entry.value, entry.category),
                )
            self._db.commit()
        except Exception as e:
            logger.warning(f"Failed to persist memory '{entry.key}' to DB: {e}")

    def _delete_db_entry(self, key: str) -> None:
        if self._db is None:
            return
        try:
            self._db.execute("DELETE FROM memory_entries WHERE key = ?", (key,))
            if self._fts_enabled:
                self._db.execute("DELETE FROM memory_entries_fts WHERE key = ?", (key,))
            self._db.commit()
        except Exception as e:
            logger.warning(f"Failed to delete memory '{key}' from DB: {e}")

    def _sync_long_term_to_db(self) -> None:
        if self._db is None:
            return
        for entry in self._long_term.values():
            if entry.key == "__file__":
                continue
            self._upsert_db_entry(entry)

    def _split_memory_sections(self, content: str) -> tuple[str, str]:
        """Split manual MEMORY.md content from the auto-generated section."""
        if AUTOGEN_START not in content or AUTOGEN_END not in content:
            return content, ""
        prefix, remainder = content.split(AUTOGEN_START, 1)
        generated, _suffix = remainder.split(AUTOGEN_END, 1)
        return prefix.rstrip(), generated.strip()

    def _load_structured_entries(self, content: str) -> None:
        """Parse generated markdown entries back into structured long-term memories."""
        current_category = "general"
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("## "):
                current_category = line[3:].strip().lower()
                continue
            m = re.match(r"- \*\*(.+?)\*\*: (.+)$", line)
            if not m:
                continue
            key = m.group(1).strip()
            value = self._sanitize_memory_value(m.group(2).strip())
            if key == "__file__":
                continue
            if not value:
                continue
            self._long_term[key] = MemoryEntry(
                key=key,
                value=value,
                category=current_category,
                importance=8,
            )
    
    def remember(
        self,
        key: str,
        value: str,
        category: str = "general",
        importance: int = 5,
        metadata: Optional[dict[str, Any]] = None,
        write_daily_note: bool = True,
    ) -> None:
        """
        Store something in short-term memory.
        
        Args:
            key: Memory key
            value: Memory value
            category: Category for organization
            importance: Importance level (1-10)
        """
        sanitized_value = self._sanitize_memory_value(value)
        if not sanitized_value:
            logger.debug(f"Skipping low-value memory entry: {key}")
            return

        entry = MemoryEntry(
            key=key,
            value=sanitized_value,
            category=category,
            importance=importance,
            metadata=dict(metadata or {}),
        )
        
        # Add to short-term
        self._short_term.append(entry)
        
        # Also add/update in long-term storage for persistence
        self._long_term[key] = entry
        self._upsert_db_entry(entry)
        if write_daily_note:
            self._append_daily_note(entry)
        
        # Trim short-term if needed
        if len(self._short_term) > self.max_short_term:
            # Remove lowest importance, oldest entries
            self._short_term.sort(key=lambda e: (e.importance, e.created_at), reverse=True)
            self._short_term = self._short_term[:self.max_short_term]
        
        logger.debug(f"Remembered: {key} (importance={importance})")
    
    def recall(self, key: str) -> Optional[str]:
        """
        Recall a memory by key.
        
        Checks short-term first, then long-term.
        
        Args:
            key: Memory key
            
        Returns:
            Memory value or None
        """
        # Check short-term (most recent first)
        for entry in reversed(self._short_term):
            if entry.key == key:
                return entry.value
        
        # Check long-term
        if key in self._long_term:
            return self._long_term[key].value
        
        return None
    
    def recall_by_category(self, category: str, limit: int = 10) -> list[MemoryEntry]:
        """
        Recall memories by category.
        
        Args:
            category: Category to filter by
            limit: Maximum entries to return
            
        Returns:
            List of memory entries
        """
        all_memories = self._all_entries()
        filtered = [m for m in all_memories if m.category == category]
        filtered.sort(key=lambda e: (e.importance, e.updated_at), reverse=True)
        
        return filtered[:limit]

    def search(self, query: str, category: Optional[str] = None, limit: int = 10) -> list[MemoryEntry]:
        """Search memories by free-text query, preferring the SQLite store."""
        text = (query or "").strip().lower()
        if not text:
            return []
        if self._db is not None:
            try:
                fts_query = self._fts_query(text)
                if fts_query and self._fts_enabled:
                    sql = (
                        "SELECT e.key, e.value, e.category, e.importance, e.created_at, e.updated_at, e.metadata "
                        "FROM memory_entries_fts f "
                        "JOIN memory_entries e ON e.key = f.key "
                        "WHERE memory_entries_fts MATCH ?"
                    )
                    params: list[Any] = [fts_query]
                    if category:
                        sql += " AND e.category = ?"
                        params.append(category)
                    sql += " ORDER BY e.importance DESC, e.updated_at DESC LIMIT ?"
                    params.append(limit)
                    rows = self._db.execute(sql, tuple(params)).fetchall()
                    results: list[MemoryEntry] = []
                    for row in rows:
                        entry = self._entry_from_row(row)
                        if entry is not None:
                            results.append(entry)
                    if results:
                        return results

                sql = (
                    "SELECT key, value, category, importance, created_at, updated_at, metadata "
                    "FROM memory_entries WHERE (LOWER(key) LIKE ? OR LOWER(value) LIKE ?)"
                )
                params: list[Any] = [f"%{text}%", f"%{text}%"]
                if category:
                    sql += " AND category = ?"
                    params.append(category)
                sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
                params.append(limit)
                rows = self._db.execute(sql, tuple(params)).fetchall()
                results: list[MemoryEntry] = []
                for row in rows:
                    entry = self._entry_from_row(row)
                    if entry is not None:
                        results.append(entry)
                return results
            except Exception as e:
                logger.warning(f"Failed to search memories in DB {self.db_path}: {e}")

        all_memories = self._all_entries()
        filtered = [
            m for m in all_memories
            if m.key != "__file__"
            and (not category or m.category == category)
            and (text in m.key.lower() or text in m.value.lower())
        ]
        filtered.sort(key=lambda e: (e.importance, e.updated_at), reverse=True)
        return filtered[:limit]

    def recent(self, limit: int = 10, category: Optional[str] = None) -> list[MemoryEntry]:
        """Return recent memories, preferring the SQLite-backed long-term store."""
        if self._db is not None:
            try:
                sql = (
                    "SELECT key, value, category, importance, created_at, updated_at, metadata "
                    "FROM memory_entries"
                )
                params: list[Any] = []
                if category:
                    sql += " WHERE category = ?"
                    params.append(category)
                sql += " ORDER BY updated_at DESC, importance DESC LIMIT ?"
                params.append(limit)
                rows = self._db.execute(sql, tuple(params)).fetchall()
                results: list[MemoryEntry] = []
                for row in rows:
                    entry = self._entry_from_row(row)
                    if entry is not None:
                        results.append(entry)
                return results
            except Exception as e:
                logger.warning(f"Failed to load recent memories from DB {self.db_path}: {e}")

        all_memories = [m for m in self._all_entries() if m.key != "__file__"]
        if category:
            all_memories = [m for m in all_memories if m.category == category]
        all_memories.sort(key=lambda e: e.updated_at, reverse=True)
        return all_memories[:limit]
    
    def forget(self, key: str) -> bool:
        """
        Remove a memory.
        
        Args:
            key: Memory key
            
        Returns:
            True if memory was removed
        """
        removed = False
        
        # Remove from short-term
        for i, entry in enumerate(self._short_term):
            if entry.key == key:
                self._short_term.pop(i)
                logger.debug(f"Forgot short-term memory: {key}")
                removed = True
                break  # key unique, stop after first
        
        # Remove from long-term
        if key in self._long_term:
            del self._long_term[key]
            logger.debug(f"Forgot long-term memory: {key}")
            removed = True
        if removed:
            self._delete_db_entry(key)
        
        return removed
    
    def set_working(self, key: str, value: Any) -> None:
        """Set a working memory value (current task context)."""
        self._working[key] = value
    
    def get_working(self, key: str, default: Any = None) -> Any:
        """Get a working memory value."""
        return self._working.get(key, default)
    
    def clear_working(self) -> None:
        """Clear all working memory."""
        self._working.clear()
    
    def get_context(self, max_entries: int = 20, query: str = "") -> str:
        """
        Build context string from memories.
        
        Args:
            max_entries: Maximum entries to include
            query: Optional query hint to prioritize relevant memories
            
        Returns:
            Formatted context string
        """
        max_entries = max(1, min(int(max_entries or 1), 50))
        query = (query or "").strip()
        top_memories = self._context_entries(max_entries=max_entries, query=query)
        if not top_memories:
            return ""
        
        # Build context
        lines = ["## Relevant Memories\n"]
        for entry in top_memories:
            lines.append(f"- [{entry.category}] {entry.key}: {entry.value[:100]}...")
        
        return "\n".join(lines)

    def _context_entries(self, max_entries: int, query: str = "") -> list[MemoryEntry]:
        """Select prompt memory with a relevance-first path and recent/high-signal fallback."""
        query = (query or "").strip()
        selected: list[MemoryEntry] = []
        seen: set[str] = set()

        def add(entry: MemoryEntry) -> None:
            if entry.key == "__file__":
                return
            if entry.key in seen:
                return
            if self._is_low_value_memory(entry.value):
                return
            selected.append(entry)
            seen.add(entry.key)

        if query:
            for entry in self.search(query=query, limit=max_entries):
                add(entry)
                if len(selected) >= max_entries:
                    return selected

            recent_limit = max(3, min(max_entries, max_entries // 2 + 2))
            for entry in self.recent(limit=recent_limit):
                if int(entry.importance or 0) >= 7:
                    add(entry)
                if len(selected) >= max_entries:
                    return selected

        all_memories = [
            memory
            for memory in self._all_entries()
            if memory.key != "__file__" and not self._is_low_value_memory(memory.value)
        ]
        all_memories.sort(key=lambda entry: (entry.importance, entry.updated_at), reverse=True)
        for entry in all_memories:
            add(entry)
            if len(selected) >= max_entries:
                break
        return selected

    def get_identity_memory(self) -> str:
        """Return only the manual identity memory section, excluding auto-generated memories."""
        return self._base_memory_content.strip()
    
    def save_long_term(self) -> None:
        """Save long-term memories to MEMORY.md."""
        memory_file = self.workspace / "MEMORY.md"
        
        try:
            lines: list[str] = []
            if self._base_memory_content:
                lines.append(self._base_memory_content.rstrip())
            
            # Group by category
            categories: dict[str, list[MemoryEntry]] = {}
            for entry in self._long_term.values():
                if entry.key == "__file__":
                    continue
                if self._is_low_value_memory(entry.value):
                    continue
                is_curated = bool((entry.metadata or {}).get("curated"))
                if not is_curated and int(entry.importance or 0) < 8:
                    continue
                if entry.category not in categories:
                    categories[entry.category] = []
                categories[entry.category].append(entry)
            
            generated_lines = [AUTOGEN_START, "## Auto-Saved Memories"]
            for category, entries in sorted(categories.items()):
                generated_lines.append(f"\n## {category.title()}")
                for entry in sorted(entries, key=lambda e: e.importance, reverse=True):
                    generated_lines.append(f"- **{entry.key}**: {entry.value}")
            generated_lines.append(AUTOGEN_END)

            if lines:
                lines.append("")
            lines.extend(generated_lines)

            content = "\n".join(lines).rstrip() + "\n"
            memory_file.write_text(content, encoding="utf-8")
            self._long_term["__file__"] = MemoryEntry(
                key="__file__",
                value=content,
                category="system",
                importance=10,
            )
        
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")

    def compact_long_term(self) -> int:
        """Drop low-value long-term memories that should not survive across sessions."""
        removed = 0
        for key in list(self._long_term.keys()):
            if key == "__file__":
                continue
            entry = self._long_term[key]
            sanitized = self._sanitize_memory_value(entry.value)
            if not sanitized:
                del self._long_term[key]
                self._delete_db_entry(key)
                removed += 1
                continue
            if sanitized != entry.value:
                entry.value = sanitized
                entry.updated_at = datetime.now(UTC)
                self._upsert_db_entry(entry)
        return removed
    
    def get_stats(self) -> dict:
        """Get memory statistics."""
        durable_entries = [m for m in self._long_term.values() if m.key != "__file__"]
        curated_entries = [
            m for m in durable_entries
            if bool((m.metadata or {}).get("curated")) or int(m.importance or 0) >= 8
        ]
        episodic_entries = [
            m for m in durable_entries
            if str((m.metadata or {}).get("scope", "")).strip() == "daily_note"
        ]
        return {
            "short_term_count": len(self._short_term),
            "long_term_count": len(self._long_term),
            "working_count": len(self._working),
            "db_path": str(self.db_path),
            "sqlite_entry_count": len(durable_entries),
            "curated_projection_count": len(curated_entries),
            "daily_note_count": len(episodic_entries),
            "memory_md_path": str(self.workspace / "MEMORY.md"),
            "daily_notes_dir": str(self.daily_notes_dir),
            "categories": sorted({m.category for m in self._all_entries()}),
        }

    def close(self) -> None:
        """Flush and close the SQLite-backed memory store."""
        try:
            self.save_long_term()
        finally:
            if self._db is not None:
                db = self._db
                self._db = None
                db.close()

    @property
    def daily_notes_dir(self) -> Path:
        return get_workspace_layout(self.workspace).memory_dir

    def append_note(self, text: str, category: str = "notes", source: str = "manual") -> None:
        """Append an unstructured episodic note to today's daily memory file."""
        cleaned = self._sanitize_memory_value(text)
        if not cleaned:
            return
        key = f"note_{int(datetime.now(UTC).timestamp() * 1_000_000)}"
        metadata = {
            "source": source,
            "scope": "daily_note",
            "curated": False,
        }
        self.remember(
            key=key,
            value=cleaned,
            category=category,
            importance=5,
            metadata=metadata,
            write_daily_note=False,
        )
        entry = self._long_term.get(key)
        if entry is not None:
            self._append_daily_note(entry)

    def get_recent_daily_notes(self, days: int = 7, limit: int = 200) -> str:
        """Return recent daily note content for review/curation."""
        days = max(1, min(int(days or 1), 30))
        limit = max(1, min(int(limit or 50), 500))
        if not self.daily_notes_dir.exists():
            return ""

        cutoff = datetime.now(UTC).date() - timedelta(days=days - 1)
        note_paths = []
        for path in sorted(self.daily_notes_dir.glob("*.md"), reverse=True):
            try:
                note_date = datetime.strptime(path.stem, "%Y-%m-%d").date()
            except ValueError:
                continue
            if note_date >= cutoff:
                note_paths.append(path)

        lines: list[str] = []
        for path in note_paths:
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            lines.append(f"## {path.stem}")
            for line in content.splitlines()[1:]:
                if line.strip():
                    lines.append(line)
                if len(lines) >= limit:
                    break
            if len(lines) >= limit:
                break

        return "\n".join(lines).strip()

    def curate_from_recent_daily_notes(self, days: int = 7, limit: int = 50) -> list[str]:
        """Promote durable items from recent daily notes into curated long-term memory."""
        days = max(1, min(int(days or 1), 30))
        limit = max(1, min(int(limit or 10), 200))
        raw = self.get_recent_daily_notes(days=days, limit=limit * 4)
        if not raw:
            return []

        promoted: list[str] = []
        seen_values: set[str] = set()
        important_categories = {"preferences", "health", "projects", "project", "tasks", "personal", "facts", "user"}

        for raw_line in raw.splitlines():
            line = raw_line.strip()
            if not line.startswith("- "):
                continue
            match = re.match(
                r"-\s+\d{2}:\d{2}:\d{2}\s+\[(?P<category>[^\]]+)\]\s+(?:(?:\[[^\]]+\])\s+)?(?P<key>[^:]+):\s+(?P<value>.+)$",
                line,
            )
            if not match:
                continue
            category = match.group("category").strip().lower()
            key = match.group("key").strip()
            value = self._sanitize_memory_value(match.group("value").strip())
            if not value or value in seen_values:
                continue
            if self._is_low_value_memory(value):
                continue
            importance = 9 if category in important_categories else 6
            if importance < 8 and not any(
                token in value.lower()
                for token in ("prefer", "deadline", "important", "allergic", "working on", "project", "task", "remember")
            ):
                continue

            metadata = {
                "curated": True,
                "curated_from_daily": True,
                "curated_at": datetime.now(UTC).isoformat(),
            }
            self.remember(
                key=key,
                value=value,
                category=category,
                importance=importance,
                metadata=metadata,
                write_daily_note=False,
            )
            promoted.append(f"{key}: {value}")
            seen_values.add(value)
            if len(promoted) >= limit:
                break

        if promoted:
            self.save_long_term()
        return promoted

    def _append_daily_note(self, entry: MemoryEntry) -> None:
        try:
            self.daily_notes_dir.mkdir(parents=True, exist_ok=True)
            note_path = self.daily_notes_dir / f"{datetime.now(UTC).date().isoformat()}.md"
            prefix = ""
            if not note_path.exists():
                prefix = f"# {note_path.stem}\n\n"
            timestamp = datetime.now(UTC).strftime("%H:%M:%S")
            source = str((entry.metadata or {}).get("source", "") or "").strip()
            source_prefix = f"[{source}] " if source else ""
            line = (
                f"- {timestamp} [{entry.category}] {source_prefix}"
                f"{entry.key}: {entry.value}\n"
            )
            with note_path.open("a", encoding="utf-8") as fh:
                if prefix:
                    fh.write(prefix)
                fh.write(line)
        except Exception as e:
            logger.warning(f"Failed to append daily memory note for '{entry.key}': {e}")

    def _entry_from_row(self, row: tuple) -> Optional[MemoryEntry]:
        try:
            key, value, category, importance, created_at, updated_at, metadata_json = row
        except Exception:
            return None
        if key == "__file__":
            return None
        sanitized_value = self._sanitize_memory_value(str(value or ""))
        if not sanitized_value:
            return None
        try:
            metadata = json.loads(metadata_json or "{}")
        except Exception:
            metadata = {}
        return MemoryEntry(
            key=str(key),
            value=sanitized_value,
            category=str(category or "general"),
            importance=int(importance or 5),
            created_at=self._parse_dt(str(created_at or "")),
            updated_at=self._parse_dt(str(updated_at or "")),
            metadata=metadata,
        )

    @staticmethod
    def _sanitize_memory_value(value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        secret_patterns = [
            r"moltbook_sk_[A-Za-z0-9_\-]+",
            r"sk-or-v1-[A-Za-z0-9]+",
            r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b",
        ]
        for pattern in secret_patterns:
            cleaned = re.sub(pattern, "[redacted]", cleaned)
        return "" if MemoryManager._is_low_value_memory(cleaned) else cleaned

    @staticmethod
    def _is_low_value_memory(value: str) -> bool:
        lowered = (value or "").strip().lower()
        if not lowered:
            return True
        noisy_fragments = (
            "placeholder header",
            "likely just placeholders",
            "user.md exists but hasn't been populated",
            "user.md exists but not populated",
            "would you like to set up your user.md",
            "no personal information about you",
            "[your ",
            "your_api_key",
            "your_telegram_bot_token",
            "read heartbeat.md",
            "heartbeat_ok",
            "heartbeat_complete",
            "authorization: bearer",
            "http_request",
            "curl ",
            "votre_cle_api",
        )
        if any(fragment in lowered for fragment in noisy_fragments):
            return True
        if MemoryManager._looks_like_conversation_noise(lowered):
            return True
        return False

    @staticmethod
    def _looks_like_conversation_noise(value: str) -> bool:
        compact = " ".join((value or "").split())
        greeting_patterns = (
            r"^(hello|hi|hey|bonjour|salut)[!. ]*$",
            r"^(hello|hi|hey|bonjour|salut)[^a-z0-9]+[a-z0-9 _-]{0,20}[!. ]*$",
            r"^nice to meet you\b.*$",
            r"^let me check\b.*$",
            r"^here'?s the current heartbeat status\b.*$",
            r"^here'?s the content of my heartbeat file\b.*$",
        )
        return any(re.match(pattern, compact) for pattern in greeting_patterns)
