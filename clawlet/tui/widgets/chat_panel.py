from __future__ import annotations

import asyncio
import json

from rich.console import Group
from rich.markdown import Markdown as RichMarkdown
from rich.text import Text
from textual.containers import Container
from textual.widgets import Collapsible, Static

from clawlet.tui.models import TranscriptEntry
from clawlet.tui.theme import CYAN, MUTED, SAKURA, WARNING

ROLE_COLORS = {"user": CYAN, "assistant": SAKURA, "warning": WARNING}
EXPANDED_STATUSES = {"FAILED", "REQUIRES APPROVAL"}

TOOL_GLYPHS = {
    "RUNNING": "…",
    "SUCCESS": "✓",
    "FAILED": "✗",
    "REQUIRES APPROVAL": "⚠",
    "PENDING": "·",
}


def _header(timestamp: str, title: str, kind: str) -> Text:
    head = Text(f"[{timestamp}] ", style="dim")
    color = ROLE_COLORS.get(kind)
    head.append(title, style=f"bold {color}" if color else "bold")
    return head


def _assistant_group(entry: TranscriptEntry) -> Group:
    """Header (+ task badge) + Markdown body. Pure, directly unit-testable."""
    head = _header(entry.timestamp.strftime("%H:%M:%S"), entry.title, entry.kind)
    task_kind = entry.metadata.get("task_kind") or entry.metadata.get("delegated_kind")
    if task_kind:
        head.append(f" · task: {task_kind}", style=MUTED)
    return Group(head, RichMarkdown(entry.body or "…", code_theme="monokai"))


def _plain_text(entry: TranscriptEntry) -> Text:
    out = _header(entry.timestamp.strftime("%H:%M:%S"), entry.title + "\n", entry.kind)
    out.append(f"{entry.body}\n")
    args = entry.metadata.get("arguments") or {}
    if args:
        out.append(f"  args: {json.dumps(args, ensure_ascii=False)}\n", style="dim")
    raw = entry.metadata.get("raw") or {}
    if raw:
        out.append("  raw:\n", style="dim")
        out.append(f"  {json.dumps(raw, ensure_ascii=False, indent=2)[:600]}\n", style="dim")
    return out


def _tool_detail(entry: TranscriptEntry) -> Text:
    """Expandable detail under a compact tool row: status + args + raw."""
    out = Text()
    args = entry.metadata.get("arguments") or {}
    if args:
        out.append(f"args: {json.dumps(args, ensure_ascii=False, indent=2)[:600]}\n", style="dim")
    raw = entry.metadata.get("raw") or {}
    if raw:
        out.append(f"raw: {json.dumps(raw, ensure_ascii=False, indent=2)[:400]}\n", style="dim")
    if out:
        out.rstrip()  # rich Text.rstrip() mutates in place, returns None
    return out


def _tool_row(entry: TranscriptEntry) -> Collapsible:
    """Compact one-line tool chip that expands to what the tool actually did."""
    glyph = TOOL_GLYPHS.get(entry.status, "·")
    name = entry.title.split("·", 1)[-1].strip() if "·" in entry.title else entry.title
    summary = (entry.body or "").strip()
    title = f"{glyph} {name}"
    if summary and summary != name:
        title += f"  ·  {summary[:56]}"
    status_class = entry.status.lower().replace(" ", "-")
    return Collapsible(
        Static(_tool_detail(entry)),
        title=title,
        collapsed=entry.status not in EXPANDED_STATUSES,
        classes=f"tool-row status-{status_class}",
    )


class ChatPanel(Container):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ponytail: (entry, widget) pairs — bare id() keys go stale on GC id-reuse
        self._widgets: dict[int, tuple[object, object]] = {}
        # ponytail: lock, NOT exclusive workers — cancelling between mount()
        # and dict registration leaves orphan duplicates mounted forever
        self._sync_lock = asyncio.Lock()

    def _build_entry(self, entry: TranscriptEntry):
        if entry.kind == "tool":
            return _tool_row(entry)
        if entry.kind == "assistant":
            return Static(_assistant_group(entry))
        return Static(_plain_text(entry))

    async def sync_entries(self, entries: list[TranscriptEntry]) -> None:
        """Incrementally mount new entries; drop trimmed ones. Call from a worker."""
        async with self._sync_lock:
            window = entries[-80:]
            live = {id(entry): entry for entry in window}
            for cached_id, (cached_entry, widget) in list(self._widgets.items()):
                if live.get(cached_id) is not cached_entry:
                    await widget.remove()
                    del self._widgets[cached_id]
            for entry in window:
                if id(entry) not in self._widgets:
                    widget = self._build_entry(entry)
                    await self.mount(widget)
                    self._widgets[id(entry)] = (entry, widget)