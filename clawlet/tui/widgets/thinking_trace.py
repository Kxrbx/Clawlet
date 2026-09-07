"""Expandable thinking trace (Beautiful UI ThinkingState -> Textual).

Port of the thinking-state primitive: a collapsed summary by default, an
expandable step list on demand, spinner -> check glyphs, and an elapsed-time
title that is only ever computed from real timestamps.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from rich.text import Text
from textual.widgets import Collapsible, Static

from clawlet.tui.models import TraceStep
from clawlet.tui.theme import ERROR, MUTED, SAKURA, SUCCESS

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _elapsed_label(started_at: datetime | None, done_at: datetime | None, now: datetime) -> str:
    if started_at is None:
        return ""
    end = done_at or now
    seconds = max(0.0, (end - started_at).total_seconds())
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def _step_line(step: TraceStep) -> Text:
    if step.status == "DONE":
        glyph = "✓"
        color = SUCCESS
    elif step.status == "FAILED":
        glyph = "✗"
        color = ERROR
    else:
        glyph = "⠿"
        color = SAKURA
    line = Text()
    line.append(f"{glyph} ", style=f"bold {color}")
    line.append(step.text)
    if step.detail:
        line.append(f"  · {step.detail}", style=MUTED)
    return line


class ThinkingTrace(Collapsible):
    """Collapsed-by-default expandable trace of observable agent steps.

    Auto-expands as steps arrive; once the user toggles it manually,
    the widget respects that choice and never changes collapsed state again.
    """

    def __init__(self) -> None:
        super().__init__(
            Static("", id="trace-body"),
            title="Thinking",
            collapsed=True,
            id="thinking-trace",
        )
        self._last_steps: tuple[tuple[str, str, str], ...] | None = None
        self._user_toggled = False

    def update_trace(
        self,
        steps: list[TraceStep],
        started_at: datetime | None,
        done_at: datetime | None,
        active: bool,
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(UTC)
        show = bool(steps) or active
        self.display = show
        if not show:
            return

        steps_tuple = tuple((s.event_type, s.text, s.detail) for s in steps)
        if steps_tuple != self._last_steps:
            body = Text()
            for step in steps:
                body.append(_step_line(step))
                body.append("\n")
            if body:
                body.rstrip()  # rich Text.rstrip() mutates in place, returns None
            self.query_one("#trace-body", Static).update(body or Text(""))
            self._last_steps = steps_tuple

        # Auto-expand on the first visible activity/content; once the user
        # toggles collapsed manually, stop changing it for the rest of the
        # session so we never fight them.
        if not self._user_toggled and self.collapsed and (active or bool(steps)):
            self.collapsed = False

        if active:
            spinner = "" if getattr(self.app, "reduce_motion", False) else SPINNER[int(time.time() * 4) % len(SPINNER)]
            self.title = f"{spinner} Thinking… {_elapsed_label(started_at, None, now)}"
        elif done_at is not None:
            self.title = f"Thought for {_elapsed_label(started_at, done_at, now)}"
        else:
            self.title = "Thinking"

    def on_collapsible_expanded(self, _event) -> None:
        self._user_toggled = True

    def on_collapsible_collapsed(self, _event) -> None:
        self._user_toggled = True