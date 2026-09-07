"""Heartbeat task rows (Beautiful UI TaskRows -> Textual, static schedule).

Compact rows for scheduled heartbeat tasks with honest status + metadata
(real next-run times when the scheduler provides them, the configured
interval otherwise). Never invents clock times.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Collapsible, Static

from clawlet.tui.models import HeartbeatState
from clawlet.tui.theme import MUTED, SAKURA, WARNING

_STATUS_GLYPH = {
    "scheduled": ("◷", SAKURA),
    "paused": ("○", WARNING),
    "idle": ("—", MUTED),
}


class HeartbeatPanel(Collapsible):
    """Collapsed heartbeat rail: task count in the title, rows on demand."""

    def __init__(self) -> None:
        super().__init__(
            Static("", id="hb-body"),
            title="Heartbeat",
            collapsed=True,
            id="heartbeat-panel",
        )

    def update_state(self, hb: HeartbeatState) -> None:
        rows: list[Text] = []
        for label, meta, status in hb.tasks:
            glyph, color = _STATUS_GLYPH.get(status, ("·", MUTED))
            line = Text()
            line.append(f"{glyph} {label}", style=color)
            if meta:
                line.append(f"  ·  {meta}", style=MUTED)
            rows.append(line)
        body = Text()
        for row in rows:
            body.append(row)
            body.append("\n")
        if body:
            body.rstrip()  # rich Text.rstrip() mutates in place, returns None
        self.query_one("#hb-body", Static).update(body or Text("No heartbeat tasks."))
        self.display = bool(hb.tasks)
        if not hb.tasks:
            return
        state = "on" if hb.enabled else "off"
        bits = [f"Heartbeat {state}"]
        if hb.interval_minutes:
            bits.append(f"every {hb.interval_minutes}m")
        bits.append(f"{len(hb.tasks)} task(s)")
        self.title = " · ".join(bits)