from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from clawlet.tui.models import BrainState, HeartbeatState
from clawlet.tui.theme import MUTED, SAKURA


class StatusBar(Static):
    """One-line status rail: provider, state, context use, heartbeat."""

    def update_state(self, brain: BrainState, heartbeat: HeartbeatState) -> None:
        total = max(1, brain.context_max_tokens)
        used = max(0, brain.context_used_tokens)
        pct = int((used / total) * 100)
        out = Text()
        out.append(f"{brain.provider or 'n/a'}/{brain.model or 'n/a'}", style=SAKURA)
        out.append(f" · {brain.status}", style="bold")
        out.append(f" · ctx {pct}%", style=MUTED)
        out.append(f" · hb {'on' if heartbeat.enabled else 'off'}", style=MUTED)
        out.append(f" · last: {heartbeat.last_task[:40]}", style=MUTED)
        self.update(out)
