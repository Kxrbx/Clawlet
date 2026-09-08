"""Main chat screen: transcript, agent activity, status rail, input."""

from __future__ import annotations

from datetime import datetime, timezone

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, ProgressBar, Static

from clawlet.tui.models import TuiState
from clawlet.tui.widgets.chat_panel import ChatPanel
from clawlet.tui.widgets.heartbeat_panel import HeartbeatPanel
from clawlet.tui.widgets.status_bar import StatusBar
from clawlet.tui.widgets.thinking_trace import ThinkingTrace

SLASH_COMMANDS: tuple[tuple[str, str], ...] = (
    ("quit", "Quit"),
    ("force", "Run heartbeat tasks now"),
    ("pause", "Pause/resume heartbeat"),
    ("heartbeat", "Show heartbeat snapshot"),
    ("replay", "Open replay viewer"),
    ("sessions", "Browse past sessions"),
    ("context", "Show raw context"),
    ("model", "Switch provider/model"),
    ("export", "Export transcript"),
    ("help", "Show this help"),
)


def complete_slash(value: str, names: list[str]) -> str | None:
    """Complete a slash fragment to the longest common match. None = leave it."""
    if not value.startswith("/") or " " in value.strip():
        return None
    frag = value[1:]
    matches = sorted({name for name in names if name.startswith(frag)})
    if not matches:
        return None
    prefix = matches[0]
    for other in matches[1:]:
        while not other.startswith(prefix):
            prefix = prefix[:-1]
    return f"/{prefix} " if len(prefix) > len(frag) else None


def match_slash(value: str, commands: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Filter slash commands by fragment. Empty fragment lists all."""
    if not value.startswith("/"):
        return []
    frag = value[1:].split(None, 1)[0] if value[1:].strip() else ""
    return [(name, desc) for name, desc in commands if name.startswith(frag)]


class SlashInput(Input):
    """Command input with Tab completion + arrow selection for slash commands."""

    def on_key(self, event: events.Key) -> None:
        if not self.value.startswith("/"):
            return  # untouched: default focus nav and editing preserved
        if event.key == "tab":
            completed = complete_slash(self.value, [name for name, _ in SLASH_COMMANDS])
            if completed is not None:
                self.value = completed
                event.prevent_default()
                event.stop()
        elif event.key in ("up", "down"):
            move = getattr(self.screen, "move_slash_selection", None)
            if move is not None and move(1 if event.key == "down" else -1):
                event.prevent_default()
                event.stop()
        # otherwise: fall through so unhandled keys keep default behavior


class MainScreen(Screen):
    _slash_matches: list[tuple[str, str]] = []
    _slash_index: int = 0

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("f", "force", "Force heartbeat"),
        Binding("p", "pause", "Pause/resume heartbeat"),
        Binding("i", "inspect", "Inspect heartbeat"),
        Binding("r", "replay", "Replay"),
        Binding("s", "sessions", "Sessions"),
        Binding("c", "context", "Raw context"),
        Binding("e", "export", "Export"),
        Binding("slash", "focus_input", "Input", key_display="/"),
        Binding("pageup", "scroll_chat_up", "Chat up", show=False),
        Binding("pagedown", "scroll_chat_down", "Chat down", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._last_draft_text: str | None = None
        self._last_chat_fp: tuple[int, object] = (-1, None)

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="chat-scroll"):
            yield ChatPanel(id="chat-panel")
        with VerticalScroll(id="draft-bubble"):
            yield Static("", id="draft-text")
        yield ThinkingTrace()
        yield ProgressBar(id="context-meter", total=128000, show_percentage=True)
        yield StatusBar(id="status-bar")
        yield HeartbeatPanel()
        with Vertical(id="input-bar"):
            yield SlashInput(placeholder=">>> Ask Clawlet anything...  (/ for commands)", id="command-input")
            with VerticalScroll(id="slash-scroll"):
                yield Static("", id="slash-hint")
        yield Footer()

    def refresh_from_store(self, state: TuiState) -> None:
        self.query_one(StatusBar).update_state(state.brain, state.heartbeat)
        self.query_one(HeartbeatPanel).update_state(state.heartbeat)
        self._update_context_meter(state)
        self._update_trace(state)
        self._update_draft(state)
        self._request_chat_sync()

    def _update_context_meter(self, state: TuiState) -> None:
        meter = self.query_one("#context-meter", ProgressBar)
        used = state.brain.context_used_tokens
        meter.display = used > 0
        if used > 0:
            meter.update(progress=used, total=max(1, state.brain.context_max_tokens))

    def _update_trace(self, state: TuiState, now: datetime | None = None) -> None:
        self.query_one(ThinkingTrace).update_trace(
            state.thinking_steps,
            state.thinking_started_at,
            state.thinking_done_at,
            active=state.brain.status == "RUNNING",
            now=now,
        )

    def _update_draft(self, state: TuiState) -> None:
        bubble = self.query_one("#draft-bubble", VerticalScroll)
        text = self.query_one("#draft-text", Static)
        draft = state.draft
        if draft is None or not draft.text:
            bubble.display = False
            self._last_draft_text = None
            return
        rendered = f"drafting…  {draft.text}"
        if rendered != self._last_draft_text:
            text.update(rendered)
            self._last_draft_text = rendered
        bubble.display = True
        bubble.scroll_end(animate=False)

    def _request_chat_sync(self) -> None:
        state = self.app.controller.store.state
        transcript = list(state.transcript)
        fp = (len(transcript), transcript[-1] if transcript else None)
        if fp[0] == self._last_chat_fp[0] and fp[1] is self._last_chat_fp[1]:
            return  # ponytail: streaming refreshes only move the draft bubble
        self._last_chat_fp = fp
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        stick = scroll.scroll_y >= scroll.max_scroll_y - 2

        async def _sync_and_stick() -> None:
            await self.query_one(ChatPanel).sync_entries(transcript)
            if stick:
                scroll.scroll_end(animate=False)

        # ponytail: no exclusive=True — cancelling a sync between mount() and
        # dict registration orphans duplicates; the panel lock serializes instead
        self.run_worker(_sync_and_stick())

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "command-input":
            return
        self._slash_matches = match_slash(event.value, list(SLASH_COMMANDS))
        self._slash_index = 0
        self._render_slash_hint()

    def _render_slash_hint(self) -> None:
        scroll = self.query_one("#slash-scroll", VerticalScroll)
        hint = self.query_one("#slash-hint", Static)
        if not self.query_one("#command-input", SlashInput).value.startswith("/"):
            scroll.display = False
            return
        lines = [
            f"{'❯' if i == self._slash_index else ' '} /{name} — {desc}"
            for i, (name, desc) in enumerate(self._slash_matches)
        ]
        hint.update("\n".join(lines) or "No match (Tab: nothing to complete)")
        scroll.display = True
        scroll.scroll_to(y=self._slash_index, animate=False)

    def move_slash_selection(self, delta: int) -> bool:
        """Move the highlighted slash suggestion (wrap-around). False = nothing to move."""
        if not self._slash_matches:
            return False
        self._slash_index = (self._slash_index + delta) % len(self._slash_matches)
        self._render_slash_hint()
        return True

    def _accept_slash_selection(self, input: SlashInput, value: str) -> bool:
        """Fill the input with the highlighted suggestion. True = accepted, don't submit."""
        if not value.startswith("/") or " " in value.strip():
            return False
        names = [name for name, _ in self._slash_matches]
        if not names or value[1:] in names:
            return False  # exact command or no match: normal submit path
        input.value = f"/{names[self._slash_index % len(names)]} "
        return True

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "command-input":
            value = event.value.strip()
            if not value:
                return
            if self._accept_slash_selection(event.input, value):
                return
            event.input.value = ""
            self.run_worker(
                self.app.handle_slash_command(value)
                if value.startswith("/")
                else self.app.controller.submit(value),
                exclusive=True,
            )

    def on_mount(self) -> None:
        self.query_one("#command-input", Input).focus()
        self.set_interval(0.25, self._tick_activity)

    def _tick_activity(self) -> None:
        """Animate the trace spinner + elapsed time while the agent works."""
        state = self.app.controller.store.state
        if state.brain.status == "RUNNING" or state.thinking_steps:
            self._update_trace(state, now=datetime.now(timezone.utc))

    def action_quit(self) -> None:
        self.app.exit()

    def action_help(self) -> None:
        self.app.notify_help()

    def action_force(self) -> None:
        self.run_worker(self.app.controller.submit("Run the current heartbeat tasks now and summarize the result."))

    def action_pause(self) -> None:
        self.run_worker(self.app.toggle_pause())

    def action_inspect(self) -> None:
        self.app.controller.emit_snapshot()
        self.app.refresh_ui()

    def action_replay(self) -> None:
        from clawlet.tui.screens.replay import ReplayScreen

        self.app.push_screen(ReplayScreen())

    def action_sessions(self) -> None:
        from clawlet.tui.screens.sessions import SessionsScreen

        self.app.push_screen(SessionsScreen())

    def action_context(self) -> None:
        from clawlet.tui.screens.raw_context import RawContextScreen

        self.app.push_screen(RawContextScreen())

    def action_export(self) -> None:
        self.app.export_transcript()

    def action_focus_input(self) -> None:
        self.query_one("#command-input", Input).focus()

    def action_scroll_chat_up(self) -> None:
        self.query_one("#chat-scroll", VerticalScroll).scroll_page_up()

    def action_scroll_chat_down(self) -> None:
        self.query_one("#chat-scroll", VerticalScroll).scroll_page_down()