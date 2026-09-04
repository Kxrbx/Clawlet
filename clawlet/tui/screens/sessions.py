"""Sessions screen: browse past sessions, search, read-only preview."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView, RichLog, Static


def resolve_session_db(workspace: Path) -> Path | None:
    """SQLite path from workspace config. None when unavailable."""
    config_path = workspace / "config.yaml"
    if not config_path.exists():
        return None
    from clawlet.config import Config

    config = Config.from_yaml(config_path)
    if config.storage.backend != "sqlite":
        return None
    return Path(config.storage.sqlite.path).expanduser()


async def list_recent_sessions(db_path: Path, limit: int = 20) -> list[tuple[str, int, str]]:
    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute(
            "SELECT session_id, COUNT(*), MAX(created_at) FROM messages"
            " GROUP BY session_id ORDER BY MAX(created_at) DESC LIMIT ?",
            (limit,),
        )
        return [(row[0], row[1], str(row[2])) for row in await cursor.fetchall()]


async def read_session_messages(
    db_path: Path, session_id: str, limit: int = 100
) -> list[tuple[str, str, str]]:
    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ?"
            " ORDER BY created_at LIMIT ?",
            (session_id, limit),
        )
        return [(row[0], str(row[1])[:500], str(row[2])) for row in await cursor.fetchall()]


async def search_sessions(db_path: Path, query: str, limit: int = 20) -> list[dict]:
    from clawlet.storage.session_db import SessionStore

    store = SessionStore(db_path)
    await store.initialize()
    try:
        return await store.session_search(query, limit=limit)
    finally:
        await store.close()


class SessionsScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._ids: list[str] = []

    def compose(self) -> ComposeResult:
        yield Label("SESSIONS — history (read-only)", classes="panel-title")
        yield Input(placeholder="search, Enter to filter", id="session-search")
        with Vertical(id="sessions-split"):
            yield ListView(id="session-list")
            yield RichLog(id="session-view", auto_scroll=False)
        yield Static("Enter: filter/read · Esc: back", classes="screen-hint")

    def on_mount(self) -> None:
        self.run_worker(self._load_recent(), exclusive=True)
        self.query_one("#session-search", Input).focus()

    async def _db(self) -> Path | None:
        return resolve_session_db(self.app.controller.workspace)

    async def _load_recent(self) -> None:
        from rich.text import Text

        view = self.query_one("#session-view", RichLog)
        db_path = await self._db()
        if db_path is None or not db_path.exists():
            view.write("No session database for this workspace.")
            return
        rows = await list_recent_sessions(db_path)
        lst = self.query_one("#session-list", ListView)
        await lst.clear()
        self._ids = [session_id for session_id, _, _ in rows]
        for session_id, count, last_seen in rows:
            await lst.mount(ListItem(Label(f"{session_id[:16]}… [{count}] {last_seen}")))
        if rows:
            lst.index = 0
        else:
            view.write("No sessions recorded yet.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "session-search":
            return
        query = event.value.strip()
        if query:
            self.run_worker(self._search(query), exclusive=True)
        else:
            self.run_worker(self._load_recent(), exclusive=True)

    async def _search(self, query: str) -> None:
        from rich.text import Text

        view = self.query_one("#session-view", RichLog)
        db_path = await self._db()
        if db_path is None or not db_path.exists():
            view.write("No session database for this workspace.")
            return
        hits = await search_sessions(db_path, query)
        lst = self.query_one("#session-list", ListView)
        await lst.clear()
        self._ids = []
        seen: set[str] = set()
        for hit in hits:
            session_id = str(hit.get("session_id", ""))
            if session_id in seen:
                continue
            seen.add(session_id)
            self._ids.append(session_id)
            await lst.mount(ListItem(Label(f"{session_id[:16]}… · {str(hit.get('snippet', ''))[:60]}")))
        view.clear()
        view.write(Text(f"{len(self._ids)} session(s) match.", style="dim"))
        if self._ids:
            lst.index = 0

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        from rich.text import Text

        if not self._ids or event.list_view.id != "session-list":
            return
        items = list(event.list_view.children)
        try:
            position = items.index(event.item)
        except ValueError:
            return
        if position >= len(self._ids):
            return
        db_path = await self._db()
        if db_path is None:
            return
        view = self.query_one("#session-view", RichLog)
        view.clear()
        for role, content, created_at in await read_session_messages(db_path, self._ids[position]):
            view.write(Text(f"[{created_at}] [{role}] {content}"))

    def action_back(self) -> None:
        self.app.pop_screen()
