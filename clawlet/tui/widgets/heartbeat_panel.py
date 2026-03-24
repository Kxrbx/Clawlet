from __future__ import annotations

from textual.widgets import Static

from clawlet.tui.models import HeartbeatState


class HeartbeatPanel(Static):
    def update_state(self, state: HeartbeatState) -> None:
        pulse_secs = state.interval_minutes * 60
        filled = min(20, max(1 if pulse_secs else 0, int((pulse_secs % 3600) / 180)))
        bar = "█" * filled + "░" * max(0, 20 - filled)
        timeline = "\n".join(state.next_runs[:6])
        self.update(
            "\n".join(
                [
                    "[bold #7C3AED]2. HEARTBEAT / CRON[/bold #7C3AED]",
                    "",
                    "Timeline",
                    timeline or "No scheduled tasks",
                    "",
                    "Pulse",
                    f"[{bar}] {state.pulse_label}",
                    "",
                    f"Last Task    {state.last_task}",
                    f"Active Crons {state.active_crons}",
                    f"Quiet Hours  {state.quiet_hours}",
                    "",
                    "[bold][F][/bold]orce Run | [bold][P][/bold]ause | [bold][I][/bold]nspect",
                ]
            )
        )
