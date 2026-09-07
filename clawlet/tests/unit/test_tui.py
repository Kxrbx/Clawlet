"""Pilot + unit tests for the reworked TUI (Textual skills: run_test/pilot)."""

from __future__ import annotations

from pathlib import Path

import pytest

from clawlet.tui.app import ClawletTuiApp
from clawlet.tui.controller import TuiController
from clawlet.tui.events import ApprovalRequest, RuntimeStatus, UserSubmitted
from clawlet.tui.export import write_transcript_markdown
from clawlet.tui.modals.approval import ApprovalModal
from clawlet.tui.screens.main import MainScreen, SlashInput, complete_slash, match_slash
from clawlet.tui.screens.replay import ReplayScreen, load_replay_lines


@pytest.fixture
def tui_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in ("SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"):
        (workspace / name).write_text(f"# {name}\n", encoding="utf-8")
    (workspace / "config.yaml").write_text("provider:\n  primary: ollama\n", encoding="utf-8")
    return workspace


def test_export_writes_markdown(tui_workspace: Path, tmp_path: Path) -> None:
    controller = TuiController(tui_workspace)
    controller.emit(UserSubmitted(session_id="local", content="hello"))
    target = write_transcript_markdown(
        tmp_path / "t.md", controller.store.state.transcript, "local"
    )
    text = target.read_text(encoding="utf-8")
    assert "hello" in text and "local" in text


def test_toggle_pause_flips_config(tui_workspace: Path) -> None:
    controller = TuiController(tui_workspace)
    assert controller.toggle_pause() is True
    assert controller.toggle_pause() is False


def test_load_replay_lines_empty(tui_workspace: Path) -> None:
    assert load_replay_lines(tui_workspace, "missing-run") == [
        "No events recorded for run_id=missing-run"
    ]


NAMES = ["quit", "force", "pause", "heartbeat", "replay", "context", "export", "help"]


def test_complete_slash_common_prefix() -> None:
    assert complete_slash("/pa", NAMES) == "/pause "
    assert complete_slash("/q", NAMES) == "/quit "
    assert complete_slash("/pause", NAMES) is None  # exact: leave it
    assert complete_slash("/zzz", NAMES) is None
    assert complete_slash("/", NAMES) is None  # ambiguous: suggestions only
    assert complete_slash("hello", NAMES) is None
    assert complete_slash("/replay abc", NAMES) is None


COMMANDS = [(n, n) for n in NAMES]


def test_match_slash_filters() -> None:
    assert [n for n, _ in match_slash("/pa", COMMANDS)] == ["pause"]
    assert len(match_slash("/", COMMANDS)) == len(NAMES)
    assert match_slash("hello", COMMANDS) == []
    assert match_slash("/zzz", COMMANDS) == []


def test_tui_routes_loguru_to_file(tui_workspace: Path, capfd) -> None:
    import sys

    from loguru import logger

    from clawlet.tui.app import _route_logs_to_file

    _route_logs_to_file(tui_workspace)
    try:
        logger.info("tui-log-probe")
        assert capfd.readouterr().err == ""  # stderr stays quiet, Textual keeps a clean screen
        assert "tui-log-probe" in (tui_workspace / "clawlet.log").read_text(encoding="utf-8")
    finally:
        logger.remove()
        logger.add(sys.stderr)


async def test_submit_ignores_mechanical_double_send(tui_workspace: Path) -> None:
    from types import SimpleNamespace

    controller = TuiController(tui_workspace)
    sent: list[str] = []

    async def _send(text: str) -> None:
        sent.append(text)

    controller.runtime = SimpleNamespace(session_id="local", send_text=_send)
    await controller.submit("hello")
    await controller.submit("hello")
    assert sent == ["hello"]
    assert sum(1 for e in controller.store.state.transcript if e.kind == "user") == 1
    controller._last_submit_at -= 2.0
    await controller.submit("hello")
    assert sent == ["hello", "hello"]


async def test_main_screen_mounts(tui_workspace: Path) -> None:
    from clawlet.tui.widgets.chat_panel import ChatPanel
    from clawlet.tui.widgets.status_bar import StatusBar

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        assert app.screen.query_one("#command-input")
        assert app.screen.query_one("#status-bar", StatusBar)
        assert "session=local" in app.sub_title
        await app.handle_slash_command("/nope-unknown")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


async def test_thinking_indicator_shows_while_running(tui_workspace: Path) -> None:
    from clawlet.tui.widgets.thinking_trace import ThinkingTrace

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        trace = app.screen.query_one(ThinkingTrace)
        assert not trace.display
        app.controller.emit(RuntimeStatus(status="RUNNING"))
        await pilot.pause()
        await pilot.pause()
        assert trace.display
        assert "Thinking" in str(trace.title)
        app.controller.emit(RuntimeStatus(status="IDLE"))
        await pilot.pause()
        await pilot.pause()
        assert not trace.display


async def test_chat_scrolls_large_conversation(tui_workspace: Path) -> None:
    from textual.containers import VerticalScroll

    from clawlet.tui.events import UserSubmitted
    from clawlet.tui.widgets.chat_panel import ChatPanel

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        chat = app.screen.query_one(ChatPanel)
        for i in range(60):
            app.controller.store.reduce(UserSubmitted(session_id="local", content=f"msg {i}"))
        await chat.sync_entries(list(app.controller.store.state.transcript))
        await pilot.pause()
        scroll = app.screen.query_one("#chat-scroll", VerticalScroll)
        assert scroll.max_scroll_y > 0
        scroll.scroll_to(y=0, animate=False)
        await pilot.pause()
        assert scroll.scroll_y == 0
        app.controller.emit(UserSubmitted(session_id="local", content="new one"))
        await pilot.pause()
        await pilot.pause()
        assert scroll.scroll_y == 0  # reading position preserved, not yanked


def test_assistant_group_marks_task_kind() -> None:
    from rich.console import Console

    from clawlet.tui.models import TranscriptEntry
    from clawlet.tui.widgets.chat_panel import _assistant_group

    group = _assistant_group(
        TranscriptEntry(
            kind="assistant",
            title="Clawlet",
            body="**bold** and `code`",
            metadata={"task_kind": "code"},
        )
    )
    console = Console(record=True, width=100)
    console.print(group)
    text = console.export_text()
    assert "bold" in text and "task: code" in text


def test_tool_entry_collapses_by_status() -> None:
    from textual.widgets import Collapsible

    from clawlet.tui.models import TranscriptEntry
    from clawlet.tui.widgets.chat_panel import ChatPanel

    panel = ChatPanel()
    ok = panel._build_entry(
        TranscriptEntry(kind="tool", title="🛠 TOOL CALL · shell", body="done", status="SUCCESS")
    )
    failed = panel._build_entry(
        TranscriptEntry(kind="tool", title="🛠 TOOL CALL · shell", body="boom", status="FAILED")
    )
    assert isinstance(ok, Collapsible) and ok.collapsed is True
    assert isinstance(failed, Collapsible) and failed.collapsed is False


async def test_approval_modal_cancel_flow(tui_workspace: Path) -> None:
    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.controller.emit(
            ApprovalRequest(
                session_id="local",
                reason="unsafe",
                token="123456",
                tool_name="shell",
                arguments={"command": "echo hi"},
            )
        )
        await pilot.pause()
        assert isinstance(app.screen, ApprovalModal)
        await pilot.click("#approve-no")
        await pilot.pause()
        assert app.controller.store.state.pending_approval is None
        assert isinstance(app.screen, MainScreen)


async def test_slash_hint_and_tab_complete(tui_workspace: Path) -> None:
    from textual.containers import VerticalScroll
    from textual.widgets import Static

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        inp = app.screen.query_one("#command-input", SlashInput)
        inp.focus()
        await pilot.pause()
        for key in ("/", "p", "a"):
            await pilot.press(key)
        await pilot.pause()
        assert app.screen.query_one("#slash-scroll", VerticalScroll).display
        hint = app.screen.query_one("#slash-hint", Static)
        assert "/pause" in str(hint.render())
        await pilot.press("tab")
        await pilot.pause()
        assert inp.value == "/pause "


async def test_slash_arrow_select_and_enter(tui_workspace: Path) -> None:
    from textual.containers import VerticalScroll
    from textual.widgets import Static

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        inp = app.screen.query_one("#command-input", SlashInput)
        inp.focus()
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        hint = app.screen.query_one("#slash-hint", Static)
        assert app.screen.query_one("#slash-scroll", VerticalScroll).display
        assert "❯ /quit" in str(hint.render())
        await pilot.press("down")
        await pilot.pause()
        assert "❯ /force" in str(hint.render())
        await pilot.press("enter")
        await pilot.pause()
        assert inp.value == "/force "


async def test_slash_menu_scrolls_to_selection(tui_workspace: Path) -> None:
    from textual.containers import VerticalScroll

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        inp = app.screen.query_one("#command-input", SlashInput)
        inp.focus()
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        scroll = app.screen.query_one("#slash-scroll", VerticalScroll)
        scroll.styles.max_height = 3
        await pilot.pause()
        assert scroll.max_scroll_y > 0
        for _ in range(7):
            await pilot.press("down")
        await pilot.pause()
        assert scroll.scroll_y > 0


async def test_command_palette_opens_replay(tui_workspace: Path) -> None:
    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        for key in ("r", "e", "p", "l", "a", "y"):
            await pilot.press(key)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ReplayScreen)


async def test_command_palette_opens_sessions(tui_workspace: Path) -> None:
    from clawlet.tui.screens.sessions import SessionsScreen

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        for key in ("s", "e", "s", "s"):
            await pilot.press(key)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, SessionsScreen)


async def _seed_session_db(db_path: Path) -> None:
    import aiosqlite

    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,"
            " metadata TEXT NOT NULL DEFAULT '{}', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            ("sess-1", "user", "hello world"),
        )
        await db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            ("sess-1", "assistant", "hi there"),
        )
        await db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            ("sess-2", "user", "other topic"),
        )
        await db.commit()


async def test_list_and_read_session_helpers(tmp_path: Path) -> None:
    from clawlet.tui.screens.sessions import list_recent_sessions, read_session_messages

    db_path = tmp_path / "test.db"
    await _seed_session_db(db_path)
    rows = await list_recent_sessions(db_path)
    assert {r[0]: r[1] for r in rows} == {"sess-1": 2, "sess-2": 1}
    msgs = await read_session_messages(db_path, "sess-1")
    assert [m[0] for m in msgs] == ["user", "assistant"]
    assert "hello" in msgs[0][1]


async def test_sessions_screen_mounts(tui_workspace: Path) -> None:
    from clawlet.tui.screens.sessions import SessionsScreen

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.push_screen(SessionsScreen())
        await pilot.pause()
        assert isinstance(app.screen, SessionsScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


async def test_tool_morph_remounts_single_widget(tui_workspace: Path) -> None:
    from textual.widgets import Collapsible

    from clawlet.tui.events import ToolLifecycle
    from clawlet.tui.widgets.chat_panel import ChatPanel

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        chat = app.screen.query_one(ChatPanel)
        app.controller.emit(ToolLifecycle(session_id="local", tool_name="shell", status="RUNNING", summary="go"))
        await pilot.pause()
        await pilot.pause()
        app.controller.emit(ToolLifecycle(session_id="local", tool_name="shell", status="SUCCESS", summary="done"))
        await pilot.pause()
        await pilot.pause()
        tools = chat.query(Collapsible)
        assert len(tools) == 1
        assert "shell" in str(tools[0].title)
        assert "status-success" in tools[0].classes


async def test_concurrent_sync_stays_consistent(tui_workspace: Path) -> None:
    import asyncio

    from clawlet.tui.models import TranscriptEntry
    from clawlet.tui.widgets.chat_panel import ChatPanel

    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        chat = app.screen.query_one(ChatPanel)
        first = TranscriptEntry(kind="user", title="You", body="one")
        second = TranscriptEntry(kind="user", title="You", body="two")
        await asyncio.gather(
            chat.sync_entries([first]),
            chat.sync_entries([first, second]),
        )
        await pilot.pause()
        assert len(chat._widgets) == 2
        assert len(chat.query("*")) >= 2


async def test_replay_screen_mounts(tui_workspace: Path) -> None:
    app = ClawletTuiApp(workspace=tui_workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.push_screen(ReplayScreen())
        await pilot.pause()
        assert isinstance(app.screen, ReplayScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
