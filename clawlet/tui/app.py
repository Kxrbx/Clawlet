from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import App

from clawlet.tui.commands import ClawletCommands
from clawlet.tui.controller import TuiController
from clawlet.tui.modals.approval import ApprovalModal
from clawlet.tui.screens.main import SLASH_COMMANDS, MainScreen

HELP_KEYS = "Keys: q quit · ? help · f force heartbeat · p pause/resume · i inspect · r replay · c raw context · e export · / input"

HELP_TEXT = HELP_KEYS + " — Commands: " + ", ".join(f"/{name}" for name, _ in SLASH_COMMANDS)


class ClawletTuiApp(App):
    TITLE = "Clawlet"
    CSS_PATH = "sakura.tcss"
    COMMANDS = {ClawletCommands}

    def __init__(self, workspace: Path, model: Optional[str] = None):
        super().__init__()
        self.workspace = workspace
        self.controller = TuiController(workspace, model)
        self._approval_open = False

    async def on_mount(self) -> None:
        self.sub_title = self.workspace.name
        self.controller.on_event = self._on_runtime_event
        await self.push_screen(MainScreen())
        await self.controller.start()
        self.refresh_ui()

    def _on_runtime_event(self) -> None:
        try:
            self.call_from_thread(self.refresh_ui)
        except RuntimeError:
            self.refresh_ui()  # ponytail: already on the UI thread, refresh inline

    def refresh_ui(self) -> None:
        if not self.screen_stack:
            return  # ponytail: teardown emits after screens are popped
        state = self.controller.store.state
        self.sub_title = f"{self.workspace.name} · session={state.session_id}"
        if isinstance(self.screen, MainScreen):
            self.screen.refresh_from_store(state)
        if state.pending_approval is not None and not self._approval_open:
            self._approval_open = True
            self.push_screen(ApprovalModal(state.pending_approval), self._on_approval_result)

    def _on_approval_result(self, approved: bool | None) -> None:
        approval = self.controller.store.state.pending_approval
        self.controller.store.state.pending_approval = None
        self._approval_open = False
        if approval is None:
            return
        if approved:
            self.run_worker(self.controller.submit(f"confirm {approval.token}"))
        else:
            self.run_worker(self.controller.submit("cancel"))
        self.refresh_ui()

    async def handle_slash_command(self, value: str) -> None:
        parts = value[1:].strip().split(None, 1)
        command = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        if command in {"quit", "q"}:
            self.exit()
        elif command in {"heartbeat", "pulse"}:
            self.controller.emit_snapshot()
            self.refresh_ui()
        elif command in {"force", "run"}:
            await self.controller.submit("Run the current heartbeat tasks now and summarize the result.")
        elif command == "pause":
            await self.toggle_pause()
        elif command == "replay":
            from clawlet.tui.screens.replay import ReplayScreen

            await self.push_screen(ReplayScreen())
            if arg:
                screen = self.screen
                if isinstance(screen, ReplayScreen):
                    await screen._load(arg)
        elif command == "sessions":
            from clawlet.tui.screens.sessions import SessionsScreen

            await self.push_screen(SessionsScreen())
        elif command == "context":
            from clawlet.tui.screens.raw_context import RawContextScreen

            await self.push_screen(RawContextScreen())
        elif command == "export":
            await self.export_transcript(Path(arg) if arg else None)
        elif command == "help":
            self.notify_help()
        else:
            self.notify(f"Unknown command: {value}", severity="warning")

    def notify_help(self) -> None:
        self.notify(HELP_TEXT)

    async def toggle_pause(self) -> None:
        enabled = self.controller.toggle_pause()
        if enabled is None:
            self.notify("No config.yaml, cannot toggle heartbeat.", severity="warning")
        else:
            self.notify(f"Heartbeat {'enabled' if enabled else 'paused'}.")
        self.refresh_ui()

    async def export_transcript(self, path: Path | None = None) -> None:
        try:
            target = self.controller.export_transcript(path)
        except OSError as exc:
            self.notify(f"Export failed: {exc}", severity="error")
            return
        self.notify(f"Transcript exported to {target}")
        self.refresh_ui()

    async def on_unmount(self) -> None:
        await self.controller.stop()


def _route_logs_to_file(workspace: Path) -> Path:
    """Send loguru records to clawlet.log — stderr writes corrupt Textual rendering."""
    from loguru import logger

    logger.remove()
    log_path = workspace / "clawlet.log"
    logger.add(
        str(log_path),
        rotation="10 MB",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )
    return log_path


def run_tui_app(workspace: Path, model: Optional[str] = None) -> None:
    _route_logs_to_file(workspace)
    app = ClawletTuiApp(workspace=workspace, model=model)
    app.run()
