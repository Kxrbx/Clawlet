from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from clawlet.tui.events import LogEvent, UserSubmitted
from clawlet.tui.runtime_adapter import LocalRuntimeHandle, create_local_runtime
from clawlet.tui.state import TuiStore


class TuiController:
    def __init__(self, workspace: Path, model: Optional[str] = None):
        self.workspace = workspace
        self.model = model
        self.store = TuiStore(str(workspace))
        self.runtime: LocalRuntimeHandle | None = None
        self._poller: asyncio.Task | None = None

    def emit(self, event: object) -> None:
        self.store.reduce(event)

    async def start(self) -> None:
        self.runtime = await create_local_runtime(self.workspace, self.model, emit=self.emit)
        self.runtime.emit_snapshot()
        self._poller = asyncio.create_task(self._pump_outbound())

    async def _pump_outbound(self) -> None:
        assert self.runtime is not None
        while True:
            await self.runtime.poll_outbound()

    async def stop(self) -> None:
        if self._poller is not None:
            self._poller.cancel()
            try:
                await self._poller
            except asyncio.CancelledError:
                pass
        if self.runtime is not None:
            await self.runtime.stop()

    async def submit(self, text: str) -> None:
        if not self.runtime:
            return
        stripped = text.strip()
        if not stripped:
            return
        self.emit(UserSubmitted(session_id=self.runtime.session_id, content=stripped))
        await self.runtime.send_text(stripped)

    async def handle_shortcut(self, action: str) -> None:
        self.emit(LogEvent(level="INFO", channel="system", message=f"Shortcut triggered: {action}"))
        if action == "force_heartbeat":
            await self.submit("Run the current heartbeat tasks now and summarize the result.")
        elif action == "inspect_heartbeat":
            self.runtime.emit_snapshot() if self.runtime else None
        elif action == "pause":
            self.emit(LogEvent(level="WARNING", channel="heartbeat", message="Pause toggle requested (not yet connected to scheduler state)."))
