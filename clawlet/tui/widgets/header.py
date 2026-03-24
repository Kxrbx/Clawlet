from __future__ import annotations

from datetime import datetime, timezone

from textual.reactive import reactive
from textual.widget import Widget


class HeaderWidget(Widget):
    clock_text = reactive("")
    pulse_on = reactive(True)
    provider = reactive("n/a")
    model = reactive("n/a")
    session_id = reactive("local")
    status = reactive("IDLE")

    def on_mount(self) -> None:
        self.set_interval(1, self._tick)
        self._tick()

    def _tick(self) -> None:
        self.clock_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.pulse_on = not self.pulse_on

    def render(self) -> str:
        paw = "🐾" if self.pulse_on else "🐾"
        left = f"Clawlet CLI agent [pulse] {paw}  {self.provider}/{self.model}  session={self.session_id}  state={self.status}"
        return f"{left}\n{self.clock_text.rjust(max(len(left), len(self.clock_text)))}"
