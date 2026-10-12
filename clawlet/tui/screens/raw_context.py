"""Raw context screen: dump the live conversation history."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Label, RichLog, Static


class RawContextScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Label("RAW CONTEXT — live history", classes="panel-title", id="context-screen")
        yield RichLog(id="context-log", auto_scroll=False)
        yield Static("Esc: back", classes="screen-hint")

    def on_mount(self) -> None:
        from rich.text import Text

        log = self.query_one("#context-log", RichLog)
        entries = self.app.controller.get_raw_history()
        if not entries:
            log.write("No live history yet — send a message first.")
            return
        for entry in entries:
            role = entry.get("role", "?")
            content = str(entry.get("content", ""))[:600]
            log.write(Text(f"[{role}] {content}"))
            for call in entry.get("tool_calls") or []:
                log.write(Text(f"  tool: {call}"))

    def action_back(self) -> None:
        self.app.pop_screen()
