from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from clawlet.tui.models import BrainState, HeartbeatState
from clawlet.tui.theme import ERROR, MUTED, SAKURA, SUCCESS


class StatusBar(Static):
    """One-line status rail: state chip, provider/model, context, heartbeat."""

    def update_state(self, brain: BrainState, heartbeat: HeartbeatState) -> None:
        out = Text()
        status = brain.status or "IDLE"
        if status == "RUNNING":
            status_style = f"bold {SAKURA}"
        elif status == "FAILED":
            status_style = f"bold {ERROR}"
        else:
            status_style = f"bold {SUCCESS}" if status == "READY" else "bold"
        out.append(f"{brain.provider or 'n/a'}/{brain.model or 'n/a'}", style=SAKURA)
        out.append(f" · {status}", style=status_style)
        out.append(f" · hb {'on' if heartbeat.enabled else 'off'}", style=MUTED)
        if heartbeat.tasks:
            out.append(f" · {len(heartbeat.tasks)} task(s)", style=MUTED)
        if heartbeat.last_task:
            out.append(f" · last: {heartbeat.last_task[:36]}", style=MUTED)
        self.update(out)