"""Replay screen: inspect structured runtime events for one run_id."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Input, Label, RichLog, Static


def load_replay_lines(workspace, run_id: str, limit: int = 200) -> list[str]:
    from clawlet.cli.runtime_paths import resolve_replay_dir
    from clawlet.runtime.events import RuntimeEventStore

    store = RuntimeEventStore(resolve_replay_dir(workspace) / "events.jsonl")
    events = store.iter_events(run_id=run_id, limit=limit)
    if not events:
        return [f"No events recorded for run_id={run_id}"]
    lines = [f"{len(events)} event(s) for run_id={run_id}", ""]
    for event in events:
        payload = str(event.payload)[:160]
        lines.append(f"[{event.timestamp}] {event.event_type} · session={event.session_id}")
        lines.append(f"  {payload}")
    return lines


class ReplayScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Label("REPLAY — run events", classes="panel-title", id="replay-screen")
        yield Input(placeholder="run_id, Enter to load", id="replay-id")
        yield RichLog(id="replay-log", auto_scroll=True)
        yield Static("Enter: load · Esc: back", classes="screen-hint")

    def on_mount(self) -> None:
        self.query_one("#replay-id", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "replay-id":
            return
        run_id = event.value.strip()
        event.input.value = ""
        if run_id:
            self.run_worker(self._load(run_id), exclusive=True)

    async def _load(self, run_id: str) -> None:
        from rich.text import Text

        log = self.query_one("#replay-log", RichLog)
        log.clear()
        log.write("Loading…")
        lines = await asyncio.to_thread(
            load_replay_lines, self.app.controller.workspace, run_id
        )
        log.clear()
        log.write_lines([Text(line) for line in lines])

    def action_back(self) -> None:
        self.app.pop_screen()
