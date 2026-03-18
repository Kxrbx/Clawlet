from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from loguru import logger

from clawlet.tools.registry import BaseTool, ToolResult
from clawlet.workspace_layout import get_workspace_layout


UTC = timezone.utc


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_folder(value: str | None) -> str:
    folder = (value or "default").strip().strip("/")
    folder = re.sub(r"[^A-Za-z0-9._/-]+", "-", folder)
    folder = re.sub(r"-{2,}", "-", folder).strip("-")
    return folder or "default"


def _parse_tags(value: str | None) -> list[str]:
    if not value:
        return []
    seen: set[str] = set()
    tags: list[str] = []
    for raw in value.split(","):
        tag = re.sub(r"[^A-Za-z0-9._/-]+", "-", raw.strip().lower()).strip("-")
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags


def _truncate(text: str, limit: int = 280) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


@dataclass(slots=True)
class NoteRecord:
    note_id: str
    title: str
    content: str
    folder: str
    tags: list[str]
    created_at: str
    updated_at: str


class NotesStore:
    def __init__(self, workspace: str | Path):
        self.layout = get_workspace_layout(Path(workspace).expanduser().resolve())
        self.layout.ensure_directories()
        self.db_path = self.layout.notes_db_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), timeout=30.0)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    folder TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_notes_folder_updated
                ON notes(folder, updated_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    note_id TEXT,
                    message TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reminders_status_remind_at
                ON reminders(status, remind_at)
                """
            )
            conn.commit()

    @staticmethod
    def _row_to_note(row: tuple[Any, ...]) -> NoteRecord:
        note_id, title, content, folder, tags_json, created_at, updated_at = row
        try:
            tags = list(json.loads(tags_json or "[]"))
        except Exception:
            tags = []
        return NoteRecord(
            note_id=str(note_id),
            title=str(title),
            content=str(content),
            folder=str(folder),
            tags=[str(tag) for tag in tags],
            created_at=str(created_at),
            updated_at=str(updated_at),
        )

    def create_note(
        self,
        *,
        title: str,
        content: str,
        tags: str | None = None,
        folder: str | None = None,
    ) -> NoteRecord:
        clean_title = (title or "").strip()
        clean_content = (content or "").strip()
        if not clean_title:
            raise ValueError("title is required")
        if not clean_content:
            raise ValueError("content is required")
        record = NoteRecord(
            note_id=f"note_{uuid4().hex[:12]}",
            title=clean_title,
            content=clean_content,
            folder=_normalize_folder(folder),
            tags=_parse_tags(tags),
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notes (id, title, content, folder, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.note_id,
                    record.title,
                    record.content,
                    record.folder,
                    json.dumps(record.tags, sort_keys=True),
                    record.created_at,
                    record.updated_at,
                ),
            )
            conn.commit()
        return record

    def list_notes(
        self,
        *,
        tags: str | None = None,
        folder: str | None = None,
        search: str | None = None,
        limit: int = 20,
    ) -> list[NoteRecord]:
        sql = "SELECT id, title, content, folder, tags_json, created_at, updated_at FROM notes WHERE 1=1"
        params: list[Any] = []
        if folder:
            sql += " AND folder = ?"
            params.append(_normalize_folder(folder))
        if search:
            sql += " AND (LOWER(title) LIKE ? OR LOWER(content) LIKE ?)"
            needle = f"%{search.strip().lower()}%"
            params.extend([needle, needle])
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(int(limit or 20), 100)))
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        notes = [self._row_to_note(row) for row in rows]
        wanted_tags = set(_parse_tags(tags))
        if not wanted_tags:
            return notes
        return [note for note in notes if wanted_tags.issubset(set(note.tags))]

    def get_note(self, note_id: str) -> Optional[NoteRecord]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, content, folder, tags_json, created_at, updated_at
                FROM notes WHERE id = ?
                """,
                ((note_id or "").strip(),),
            ).fetchone()
        return None if row is None else self._row_to_note(row)

    def update_note(
        self,
        *,
        note_id: str,
        title: str | None = None,
        content: str | None = None,
        append: bool = False,
        tags: str | None = None,
    ) -> NoteRecord:
        record = self.get_note(note_id)
        if record is None:
            raise ValueError(f"note not found: {note_id}")

        next_title = (title or "").strip() or record.title
        next_content = record.content
        if content is not None:
            incoming = content.strip()
            if append and incoming:
                next_content = f"{record.content.rstrip()}\n\n{incoming}"
            elif incoming:
                next_content = incoming
        next_tags = record.tags if tags is None else _parse_tags(tags)
        updated_at = _utcnow()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notes
                SET title = ?, content = ?, tags_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_title,
                    next_content,
                    json.dumps(next_tags, sort_keys=True),
                    updated_at,
                    record.note_id,
                ),
            )
            conn.commit()
        return self.get_note(record.note_id) or record

    def delete_note(self, note_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM notes WHERE id = ?", (((note_id or "").strip()),))
            conn.commit()
            return int(cursor.rowcount or 0) > 0

    def create_reminder(
        self,
        *,
        message: str,
        remind_at: str,
        note_id: str | None = None,
    ) -> str:
        if not (message or "").strip():
            raise ValueError("message is required")
        if not (remind_at or "").strip():
            raise ValueError("remind_at is required")
        if note_id:
            existing = self.get_note(note_id)
            if existing is None:
                raise ValueError(f"note not found: {note_id}")
        reminder_id = f"rem_{uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reminders (id, note_id, message, remind_at, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    reminder_id,
                    (note_id or "").strip() or None,
                    message.strip(),
                    remind_at.strip(),
                    _utcnow(),
                    _utcnow(),
                ),
            )
            conn.commit()
        return reminder_id


class _BaseNotesTool(BaseTool):
    def __init__(self, workspace: str | Path):
        self.store = NotesStore(workspace)


class NotesCreateNoteTool(_BaseNotesTool):
    @property
    def name(self) -> str:
        return "notes_create_note"

    @property
    def description(self) -> str:
        return "Create a persistent note in the workspace notes store."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "string"},
                "folder": {"type": "string"},
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs) -> ToolResult:
        record = self.store.create_note(
            title=kwargs.get("title", ""),
            content=kwargs.get("content", ""),
            tags=kwargs.get("tags"),
            folder=kwargs.get("folder"),
        )
        return ToolResult(
            success=True,
            output=(
                f"Created note `{record.note_id}` in folder `{record.folder}`.\n"
                f"Title: {record.title}\n"
                f"Tags: {', '.join(record.tags) if record.tags else '(none)'}"
            ),
            data=asdict(record),
        )


class NotesListNotesTool(_BaseNotesTool):
    @property
    def name(self) -> str:
        return "notes_list_notes"

    @property
    def description(self) -> str:
        return "List notes with optional folder, tag, or text filtering."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tags": {"type": "string"},
                "folder": {"type": "string"},
                "search": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "additionalProperties": False,
        }

    async def execute(self, **kwargs) -> ToolResult:
        notes = self.store.list_notes(
            tags=kwargs.get("tags"),
            folder=kwargs.get("folder"),
            search=kwargs.get("search"),
            limit=kwargs.get("limit", 20),
        )
        if not notes:
            return ToolResult(success=True, output="No notes found.", data=[])
        lines = ["## Notes"]
        for note in notes:
            lines.append(
                f"- {note.note_id} [{note.folder}] {note.title} | "
                f"tags={','.join(note.tags) if note.tags else '(none)'} | "
                f"{_truncate(note.content, 100)}"
            )
        return ToolResult(success=True, output="\n".join(lines), data=[asdict(note) for note in notes])


class NotesGetNoteTool(_BaseNotesTool):
    @property
    def name(self) -> str:
        return "notes_get_note"

    @property
    def description(self) -> str:
        return "Read a single note by its note_id."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"note_id": {"type": "string"}},
            "required": ["note_id"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs) -> ToolResult:
        note = self.store.get_note(kwargs.get("note_id", ""))
        if note is None:
            return ToolResult(success=False, output="", error="Note not found.")
        return ToolResult(
            success=True,
            output=(
                f"## {note.title}\n"
                f"- ID: {note.note_id}\n"
                f"- Folder: {note.folder}\n"
                f"- Tags: {', '.join(note.tags) if note.tags else '(none)'}\n"
                f"- Updated: {note.updated_at}\n\n"
                f"{note.content}"
            ),
            data=asdict(note),
        )


class NotesUpdateNoteTool(_BaseNotesTool):
    @property
    def name(self) -> str:
        return "notes_update_note"

    @property
    def description(self) -> str:
        return "Update an existing note by replacing or appending content."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "note_id": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "append": {"type": "boolean"},
                "tags": {"type": "string"},
            },
            "required": ["note_id"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs) -> ToolResult:
        record = self.store.update_note(
            note_id=kwargs.get("note_id", ""),
            title=kwargs.get("title"),
            content=kwargs.get("content"),
            append=bool(kwargs.get("append", False)),
            tags=kwargs.get("tags"),
        )
        return ToolResult(
            success=True,
            output=f"Updated note `{record.note_id}`. Latest content: {_truncate(record.content, 120)}",
            data=asdict(record),
        )


class NotesDeleteNoteTool(_BaseNotesTool):
    @property
    def name(self) -> str:
        return "notes_delete_note"

    @property
    def description(self) -> str:
        return "Delete a note by its note_id."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"note_id": {"type": "string"}},
            "required": ["note_id"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs) -> ToolResult:
        deleted = self.store.delete_note(kwargs.get("note_id", ""))
        if not deleted:
            return ToolResult(success=False, output="", error="Note not found.")
        return ToolResult(success=True, output="Deleted note successfully.")


class NotesCreateReminderTool(_BaseNotesTool):
    @property
    def name(self) -> str:
        return "notes_create_reminder"

    @property
    def description(self) -> str:
        return "Create a reminder linked to a note or standalone message."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "note_id": {"type": "string"},
                "message": {"type": "string"},
                "remind_at": {"type": "string"},
            },
            "required": ["message", "remind_at"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs) -> ToolResult:
        reminder_id = self.store.create_reminder(
            note_id=kwargs.get("note_id"),
            message=kwargs.get("message", ""),
            remind_at=kwargs.get("remind_at", ""),
        )
        return ToolResult(
            success=True,
            output=(
                f"Created reminder `{reminder_id}` for `{kwargs.get('remind_at', '')}`. "
                "Reminder storage is active; delivery scheduling can use this persisted state later."
            ),
            data={"reminder_id": reminder_id},
        )


class NotesTools:
    def __init__(self, workspace: str | Path):
        self.create_note = NotesCreateNoteTool(workspace)
        self.list_notes = NotesListNotesTool(workspace)
        self.get_note = NotesGetNoteTool(workspace)
        self.update_note = NotesUpdateNoteTool(workspace)
        self.delete_note = NotesDeleteNoteTool(workspace)
        self.create_reminder = NotesCreateReminderTool(workspace)

    def all_tools(self) -> list[BaseTool]:
        return [
            self.create_note,
            self.list_notes,
            self.get_note,
            self.update_note,
            self.delete_note,
            self.create_reminder,
        ]
