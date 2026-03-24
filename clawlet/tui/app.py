from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Static

from clawlet.tui.controller import TuiController
from clawlet.tui.theme import CSS
from clawlet.tui.widgets.brain_panel import BrainPanel
from clawlet.tui.widgets.chat_panel import ChatPanel
from clawlet.tui.widgets.footer import FooterPanel
from clawlet.tui.widgets.header import HeaderWidget
from clawlet.tui.widgets.heartbeat_panel import HeartbeatPanel
from clawlet.tui.widgets.logs_panel import LogsPanel


class ClawletTuiApp(App):
    CSS = CSS
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f1", "help", "Help"),
        ("f2", "replay", "Replay"),
        ("f3", "raw_context", "Raw Context"),
        ("f4", "export", "Export"),
        ("f", "force_heartbeat", "Force heartbeat"),
        ("p", "pause_heartbeat", "Pause heartbeat"),
        ("i", "inspect_heartbeat", "Inspect heartbeat"),
        ("ctrl+r", "focus_logs", "Focus logs"),
    ]

    def __init__(self, workspace: Path, model: Optional[str] = None):
        super().__init__()
        self.workspace = workspace
        self.model = model
        self.controller = TuiController(workspace, model)

    def compose(self) -> ComposeResult:
        yield HeaderWidget(id="header")
        yield ChatPanel(id="chat-panel")
        with Container(id="right-stack"):
            yield BrainPanel(id="brain-panel")
            yield HeartbeatPanel(id="heartbeat-panel")
        yield LogsPanel(id="logs-panel")
        yield FooterPanel(id="footer-panel")

    async def on_mount(self) -> None:
        await self.controller.start()
        self.set_interval(0.5, self.refresh_panels)
        self.refresh_panels()

    def refresh_panels(self) -> None:
        state = self.controller.store.state
        header = self.query_one(HeaderWidget)
        header.provider = state.brain.provider or "n/a"
        header.model = state.brain.model or "n/a"
        header.session_id = state.session_id
        header.status = state.brain.status
        self.query_one(ChatPanel).update_entries(state.transcript)
        self.query_one(BrainPanel).update_state(state.brain)
        self.query_one(HeartbeatPanel).update_state(state.heartbeat)
        self.query_one(LogsPanel).update_logs(state.logs, state.active_log_tab, state.log_filter, state.pending_approval)

    async def on_input_submitted(self, event) -> None:
        if event.input.id == "command-input":
            value = event.value.strip()
            event.input.value = ""
            if not value:
                return
            if value.startswith("/"):
                await self._handle_slash_command(value)
                return
            await self.controller.submit(value)
        elif event.input.id == "logs-filter":
            self.controller.store.state.log_filter = event.value.strip()
            self.refresh_panels()

    async def _handle_slash_command(self, value: str) -> None:
        command = value[1:].strip().lower()
        if command in {"quit", "q"}:
            self.exit()
            return
        if command in {"heartbeat", "pulse"}:
            await self.controller.handle_shortcut("inspect_heartbeat")
            self.refresh_panels()
            return
        if command in {"force", "run"}:
            await self.controller.handle_shortcut("force_heartbeat")
            return
        self.notify(f"Unknown command: {value}")

    async def action_help(self) -> None:
        self.notify("F1 Help · F2 Replay · F3 Raw Context · F4 Export · F Force heartbeat · P Pause · I Inspect")

    async def action_replay(self) -> None:
        self.notify("Replay panel not yet implemented; use clawlet replay <run_id>.")

    async def action_raw_context(self) -> None:
        self.notify("Raw context preview not yet implemented.")

    async def action_export(self) -> None:
        self.notify("Transcript export command not yet implemented.")

    async def action_force_heartbeat(self) -> None:
        await self.controller.handle_shortcut("force_heartbeat")

    async def action_pause_heartbeat(self) -> None:
        await self.controller.handle_shortcut("pause")

    async def action_inspect_heartbeat(self) -> None:
        await self.controller.handle_shortcut("inspect_heartbeat")
        self.refresh_panels()

    async def action_focus_logs(self) -> None:
        self.query_one("#logs-filter").focus()

    async def on_key(self, event: events.Key) -> None:
        if self.controller.store.state.pending_approval is None:
            return
        approval = self.controller.store.state.pending_approval
        if event.key.lower() == "y":
            await self.controller.submit(f"confirm {approval.token}")
            self.controller.store.state.pending_approval = None
            self.refresh_panels()
        elif event.key.lower() == "n":
            await self.controller.submit("cancel")
            self.controller.store.state.pending_approval = None
            self.refresh_panels()
        elif event.key.lower() == "e":
            self.notify("Edit args flow not yet implemented.")

    async def on_unmount(self) -> None:
        await self.controller.stop()


def run_tui_app(workspace: Path, model: Optional[str] = None) -> None:
    app = ClawletTuiApp(workspace=workspace, model=model)
    app.run()
