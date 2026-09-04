from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from clawlet.tui.events import HeartbeatSnapshot, LogEvent, UserSubmitted
from clawlet.tui.export import default_export_path, write_transcript_markdown
from clawlet.tui.runtime_adapter import LocalRuntimeHandle, create_local_runtime
from clawlet.tui.state import TuiStore


class TuiController:
    def __init__(
        self,
        workspace: Path,
        model: Optional[str] = None,
        on_event: Callable[[], None] | None = None,
    ):
        self.workspace = workspace
        self.model = model
        self.on_event = on_event
        self.store = TuiStore(str(workspace))
        self.runtime: LocalRuntimeHandle | None = None
        self._poller: asyncio.Task | None = None
        self._last_submit_text = ""
        self._last_submit_at = 0.0

    def emit(self, event: object) -> None:
        self.store.reduce(event)
        if self.on_event is not None:
            self.on_event()

    def emit_snapshot(self) -> None:
        if self.runtime is not None:
            self.runtime.emit_snapshot()

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
        now = time.monotonic()
        if stripped == self._last_submit_text and now - self._last_submit_at < 1.0:
            return  # ponytail: mechanical double-Enter, one send only
        self._last_submit_text = stripped
        self._last_submit_at = now
        self.emit(UserSubmitted(session_id=self.runtime.session_id, content=stripped))
        await self.runtime.send_text(stripped)

    def get_raw_history(self) -> list[dict[str, Any]]:
        if self.runtime is None:
            return []
        return self.runtime.get_raw_history()

    def export_transcript(self, path: Path | None = None) -> Path:
        target = path or default_export_path(self.workspace)
        return write_transcript_markdown(
            target, self.store.state.transcript, self.store.state.session_id
        )

    def toggle_pause(self) -> bool | None:
        """Flip heartbeat.enabled in config.yaml. Returns new state, None if no config."""
        config_path = self.workspace / "config.yaml"
        if not config_path.exists():
            self.emit(LogEvent(level="WARNING", channel="heartbeat", message="No config.yaml, cannot toggle heartbeat."))
            return None
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        heartbeat = raw.setdefault("heartbeat", {})
        if not isinstance(heartbeat, dict):
            return None
        enabled = not bool(heartbeat.get("enabled", False))
        heartbeat["enabled"] = enabled
        config_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        current = asdict(self.store.state.heartbeat)
        current["enabled"] = enabled
        self.emit(HeartbeatSnapshot(**current))
        self.emit(
            LogEvent(
                level="INFO",
                channel="heartbeat",
                message=f"Heartbeat {'enabled' if enabled else 'paused'}.",
            )
        )
        return enabled
