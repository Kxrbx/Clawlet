from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import pytest

from clawlet.agent.message_builder import MessageBuilder
from clawlet.agent.outbound_publisher import OutboundPublisher
from clawlet.agent.heartbeat_reporter import HeartbeatReporter
from clawlet.agent.history_trimmer import HistoryTrimmer
from clawlet.agent.recovery_checkpoint import RecoveryCheckpointService
from clawlet.agent.run_lifecycle import RunLifecycle
from clawlet.agent.run_prelude import RunPrelude
from clawlet.agent.response_policy import ResponsePolicy
from clawlet.runtime import build_runtime_services
from clawlet.runtime.policy import RuntimePolicyEngine
from clawlet.agent.approval_service import ApprovalService


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_runtime_modules_do_not_hardcode_global_workspace_paths():
    protected_files = [
        REPO_ROOT / "clawlet" / "channels" / "telegram.py",
        REPO_ROOT / "clawlet" / "cli" / "runtime_ui.py",
        REPO_ROOT / "clawlet" / "dashboard" / "api.py",
        REPO_ROOT / "clawlet" / "health.py",
        REPO_ROOT / "clawlet" / "providers" / "models_cache.py",
        REPO_ROOT / "clawlet" / "skills" / "__init__.py",
        REPO_ROOT / "clawlet" / "skills" / "registry.py",
        REPO_ROOT / "clawlet" / "tools" / "skills.py",
    ]

    forbidden_literals = ['Path.home() / ".clawlet"', "~/.clawlet"]
    for path in protected_files:
        text = path.read_text(encoding="utf-8")
        for literal in forbidden_literals:
            assert literal not in text, f"{path} still contains forbidden workspace literal: {literal}"


def test_channels_do_not_use_generic_outbound_consumer():
    channels_dir = REPO_ROOT / "clawlet" / "channels"
    for path in channels_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "consume_outbound(" not in text, f"{path} should use consume_outbound_for(channel)"


def test_skill_registry_no_longer_stores_private_tool_registry_state():
    text = (REPO_ROOT / "clawlet" / "skills" / "registry.py").read_text(encoding="utf-8")
    assert "_tool_registry =" not in text
    assert "tool_registry or self._tool_registry" not in text


def test_telegram_channel_delegates_callbacks_and_ui_helpers():
    telegram_py = (REPO_ROOT / "clawlet" / "channels" / "telegram.py").read_text(encoding="utf-8")
    assert "dispatch_callback_query" in telegram_py
    assert "default_reply_keyboard" in telegram_py
    assert "main_menu_markup" in telegram_py
    assert "settings_menu_markup" in telegram_py


def test_agent_loop_delegates_turn_execution():
    loop_py = (REPO_ROOT / "clawlet" / "agent" / "loop.py").read_text(encoding="utf-8")
    assert "TurnExecutor" in loop_py
    assert "HeartbeatTurnHandler" in loop_py
    assert "self._turn_executor.execute(" in loop_py


def test_cli_entrypoint_no_longer_inlines_agent_and_heartbeat_command_wiring():
    cli_init = (REPO_ROOT / "clawlet" / "cli" / "__init__.py").read_text(encoding="utf-8")
    forbidden = [
        "run_agent_command",
        "run_agent_restart_command",
        "run_agent_stop_command",
        "run_chat_command",
        "run_logs_command",
        "run_heartbeat_status_command",
        "run_heartbeat_last_command",
        "run_heartbeat_set_enabled_command",
        "run_replay_command",
        "run_recovery_list",
        "run_recovery_show",
        "run_recovery_resume_payload",
        "run_recovery_cleanup",
        "run_plugin_init",
        "run_plugin_test",
        "run_plugin_conformance",
        "run_plugin_matrix",
        "run_plugin_publish",
        "run_sessions_command",
        "run_cron_add_command",
        "run_cron_edit_command",
        "run_cron_list_command",
        "run_cron_remove_command",
        "run_cron_run_now_command",
        "run_cron_runs_command",
        "run_cron_set_enabled_command",
        "run_benchmark_run",
        "run_benchmark_compare",
        "run_benchmark_competitive_report",
        "run_benchmark_coding_loop",
        "run_benchmark_corpus",
        "run_benchmark_context_cache",
        "run_benchmark_lanes",
        "run_benchmark_publish_report",
        "run_benchmark_release_gate",
        "run_benchmark_remote_health",
        "run_benchmark_remote_parity",
    ]
    for token in forbidden:
        assert token not in cli_init


def test_runtime_services_assemble_workspace_scoped_memory_skills_and_tools(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "SOUL.md").write_text("# soul\n", encoding="utf-8")
    (workspace / "USER.md").write_text("# user\n", encoding="utf-8")
    (workspace / "MEMORY.md").write_text("# memory\n", encoding="utf-8")
    (workspace / "HEARTBEAT.md").write_text("# heartbeat\n", encoding="utf-8")

    services = build_runtime_services(workspace)

    assert services.memory_manager.workspace == workspace.resolve()
    assert services.skill_runtime.registry._workspace == workspace.resolve()
    assert services.tools.get("install_skill") is not None
    assert services.tools.get("list_skills") is not None
    assert services.tools.get("search_memory") is not None
    assert services.tools.get("notes_create_note") is not None


def test_runtime_policy_engine_owns_confirmation_heuristics():
    policy = RuntimePolicyEngine()

    assert policy.confirmation_reason("shell", {"command": "git reset --hard"}, approved=False)
    assert policy.confirmation_reason("write_file", {"path": "config.yaml"}, approved=False)
    assert policy.confirmation_reason("read_file", {"path": "README.md"}, approved=False) == ""


@pytest.mark.asyncio
async def test_approval_service_handles_confirm_and_cancel_flow():
    service = ApprovalService()

    class _ToolCall:
        name = "shell"
        id = "tc-1"
        arguments = {"command": "echo hi"}

    service.set("telegram:1", "123456", _ToolCall())
    captured = []

    class _Result:
        success = True
        output = "done"
        error = ""

    async def _execute(tc):
        captured.append(("execute", tc.name))
        return _Result()

    def _render(result):
        return result.output

    def _append(rendered, tc):
        captured.append(("append", rendered, tc.id))

    reply = await service.maybe_handle_confirmation_reply(
        convo_key="telegram:1",
        user_message="confirm 123456",
        execute_tool=_execute,
        render_tool_result=_render,
        append_tool_message=_append,
    )

    assert "Confirmed and executed" in reply
    assert captured == [("execute", "shell"), ("append", "done", "tc-1")]
    assert service.get("telegram:1") is None


@pytest.mark.asyncio
async def test_approval_service_cancel_clears_pending():
    service = ApprovalService()

    class _ToolCall:
        name = "edit_file"
        id = "tc-2"
        arguments = {"path": "x.txt"}

    service.set("cli:local", "654321", _ToolCall())
    reply = await service.maybe_handle_confirmation_reply(
        convo_key="cli:local",
        user_message="cancel",
        execute_tool=lambda tc: None,
        render_tool_result=lambda result: "",
        append_tool_message=lambda rendered, tc: None,
    )

    assert reply == "Cancelled the pending action."
    assert service.get("cli:local") is None


def test_message_builder_adds_context_and_skips_invalid_tool_messages():
    class _Identity:
        def build_system_prompt(self, tools, workspace_path):
            return f"prompt:{workspace_path}"

    class _Tools:
        def all_tools(self):
            return []

    class _ContextEngine:
        def render_for_prompt(self, query, max_files, char_budget):
            return f"context:{query}"

    class _Memory:
        def __init__(self):
            self.calls = []

        def get_context(self, max_entries, query):
            self.calls.append((max_entries, query))
            return f"memory:{query}:{max_entries}"

    class _HeartbeatState:
        def build_prompt_summary(self):
            return "heartbeat:summary"

    class _Msg:
        def __init__(self, role, content, metadata=None, tool_call_id=None):
            self.role = role
            self.content = content
            self.metadata = metadata or {}
            self._tool_call_id = tool_call_id

        def to_dict(self):
            data = {"role": self.role, "content": self.content}
            if self._tool_call_id:
                data["tool_call_id"] = self._tool_call_id
            return data

    memory = _Memory()
    builder = MessageBuilder(
        identity=_Identity(),
        tools=_Tools(),
        workspace=Path("/tmp/ws"),
        context_engine=_ContextEngine(),
        memory=memory,
        heartbeat_state=_HeartbeatState(),
        context_window=10,
        heartbeat_action_policy="hb:policy",
        logger=type("L", (), {"debug": lambda *a, **k: None, "warning": lambda *a, **k: None})(),
    )
    history = [
        _Msg("system", "summary", metadata={"summary": True}),
        _Msg("user", "hello"),
        _Msg("tool", "bad tool"),
        _Msg("tool", "good tool", tool_call_id="tc-1"),
    ]

    messages = builder.build_messages(history, query_hint="hello")
    contents = [msg.get("content", "") for msg in messages]

    assert "prompt:/tmp/ws" in contents
    assert "context:hello" in contents
    assert "memory:hello:10" in contents
    assert "good tool" in contents
    assert "bad tool" not in contents
    assert contents.count("summary") == 1
    assert memory.calls == [(10, "hello")]


@pytest.mark.asyncio
async def test_outbound_publisher_suppresses_and_records_outreach():
    published = []
    outreach = []

    class _Bus:
        async def publish_outbound(self, response):
            published.append(response.content)

    class _Runtime:
        outbound_publish_retries = 1
        outbound_publish_backoff_seconds = 0.0

    class _Policy:
        def should_suppress_outbound(self, response):
            return response.content == "HEARTBEAT_OK"

    class _HeartbeatState:
        def record_outreach(self, now, response_text):
            outreach.append(response_text)

    class _Response:
        def __init__(self, channel, content, metadata=None):
            self.channel = channel
            self.chat_id = "1"
            self.content = content
            self.metadata = metadata or {}

    class _Metrics:
        def __init__(self):
            self.count = 0

        def inc_heartbeat_acks_suppressed(self):
            self.count += 1

    metrics = _Metrics()
    publisher = OutboundPublisher(
        bus=_Bus(),
        runtime_config=_Runtime(),
        response_policy=_Policy(),
        heartbeat_state=_HeartbeatState(),
        logger=type("L", (), {"info": lambda *a, **k: None, "error": lambda *a, **k: None})(),
        metrics_factory=lambda: metrics,
        classify_error_text=lambda text: type("F", (), {"code": "x"})(),
        failure_payload=lambda failure: {"kind": "x"},
        emit_runtime_event=lambda event, session_id, payload: None,
        event_channel_failed="channel_failed",
        now_fn=lambda: "now",
    )

    suppressed = await publisher.publish(
        _Response("telegram", "HEARTBEAT_OK", metadata={"heartbeat": True}),
        session_id="s1",
    )
    delivered = await publisher.publish(
        _Response("telegram", "HEARTBEAT_ACTION_TAKEN - done", metadata={"heartbeat": True}),
        session_id="s1",
        run_id="s1-run",
    )

    assert suppressed is True
    assert delivered is True
    assert metrics.count == 1
    assert published == ["HEARTBEAT_ACTION_TAKEN - done"]
    assert outreach == ["HEARTBEAT_ACTION_TAKEN - done"]


@pytest.mark.asyncio
async def test_outbound_publisher_stamps_runtime_delivery_metadata():
    published = []

    class _Bus:
        async def publish_outbound(self, response):
            published.append(dict(response.metadata or {}))

    class _Runtime:
        outbound_publish_retries = 0
        outbound_publish_backoff_seconds = 0.0

    class _Policy:
        def should_suppress_outbound(self, response):
            return False

    class _HeartbeatState:
        def record_outreach(self, now, response_text):
            return None

    class _Response:
        def __init__(self):
            self.channel = "telegram"
            self.chat_id = "1"
            self.content = "hello"
            self.metadata = {}

    publisher = OutboundPublisher(
        bus=_Bus(),
        runtime_config=_Runtime(),
        response_policy=_Policy(),
        heartbeat_state=_HeartbeatState(),
        logger=type("L", (), {"info": lambda *a, **k: None, "error": lambda *a, **k: None})(),
        metrics_factory=lambda: type("M", (), {"inc_heartbeat_acks_suppressed": lambda *a, **k: None})(),
        classify_error_text=lambda text: type("F", (), {"code": "x"})(),
        failure_payload=lambda failure: {"kind": "x"},
        emit_runtime_event=lambda event, session_id, payload: None,
        event_channel_failed="channel_failed",
        now_fn=lambda: "now",
    )

    response = _Response()
    delivered = await publisher.publish(response, session_id="session-1", run_id="run-1")

    assert delivered is True
    assert published == [{"_session_id": "session-1", "_run_id": "run-1"}]


def test_heartbeat_reporter_records_route_and_check_types():
    captured = {}

    class _HeartbeatState:
        def record_cycle_result(self, **kwargs):
            captured.update(kwargs)

    reporter = HeartbeatReporter(
        heartbeat_state=_HeartbeatState(),
        now_fn=lambda: "now",
    )
    reporter.record_result(
        response_text="HEARTBEAT_OK",
        channel="telegram",
        chat_id="123",
        heartbeat_metadata={"heartbeat_check_types": ["notifications"]},
        mapped_tool_names=["http_request"],
        blockers=[],
    )

    assert captured["response_text"] == "HEARTBEAT_OK"
    assert captured["route"] == {"channel": "telegram", "chat_id": "123"}
    assert captured["check_types"] == ["notifications"]
    assert captured["tool_names"] == ["http_request"]


def test_heartbeat_reporter_uses_tick_timestamp_when_present():
    captured = {}

    class _HeartbeatState:
        def record_cycle_result(self, **kwargs):
            captured.update(kwargs)

    reporter = HeartbeatReporter(
        heartbeat_state=_HeartbeatState(),
        now_fn=lambda: datetime(2026, 3, 18, 1, 0, tzinfo=timezone.utc),
    )
    reporter.record_result(
        response_text="HEARTBEAT_OK",
        channel="telegram",
        chat_id="123",
        heartbeat_metadata={
            "heartbeat_check_types": ["notifications"],
            "heartbeat_tick_at": "2026-03-18T00:26:07.312297+00:00",
        },
        mapped_tool_names=["http_request"],
        blockers=[],
    )

    assert captured["now"] == datetime(2026, 3, 18, 0, 26, 7, 312297, tzinfo=timezone.utc)


def test_response_policy_rejects_unusable_heartbeat_action_summary():
    policy = ResponsePolicy(
        continuation_split=__import__("re").compile(r"$^"),
        looks_like_incomplete_followthrough=lambda text, n: False,
        sanitize_template_placeholders=lambda text: text,
        looks_like_blocker_response=lambda text: False,
    )

    text, is_error = policy.canonicalize_heartbeat_outcome(
        response_text="HEARTBEAT_ACTION_TAKEN - {",
        is_error=False,
        tool_names=["http_request"],
        blockers=[],
        action_summaries=["{"],
    )

    assert is_error is True
    assert text.startswith("HEARTBEAT_BLOCKED - ")


def test_response_policy_accepts_heartbeat_ok_with_detail_suffix():
    policy = ResponsePolicy(
        continuation_split=__import__("re").compile(r"$^"),
        looks_like_incomplete_followthrough=lambda text, n: False,
        sanitize_template_placeholders=lambda text: text,
        looks_like_blocker_response=lambda text: False,
    )

    text, is_error = policy.canonicalize_heartbeat_outcome(
        response_text="HEARTBEAT_OK - Checked Moltbook, all good! 🦞",
        is_error=False,
        tool_names=["http_request"],
        blockers=[],
        action_summaries=[],
    )

    assert text == "HEARTBEAT_OK"
    assert is_error is False


def test_response_policy_recovers_heartbeat_ok_from_blocked_prefix_when_clean():
    policy = ResponsePolicy(
        continuation_split=__import__("re").compile(r"$^"),
        looks_like_incomplete_followthrough=lambda text, n: False,
        sanitize_template_placeholders=lambda text: text,
        looks_like_blocker_response=lambda text: False,
    )

    text, is_error = policy.canonicalize_heartbeat_outcome(
        response_text="HEARTBEAT_BLOCKED - HEARTBEAT_OK - Checked Moltbook, all good! 🦞",
        is_error=False,
        tool_names=["http_request"],
        blockers=[],
        action_summaries=[],
    )

    assert text == "HEARTBEAT_OK"
    assert is_error is False


def test_response_policy_marks_provider_instability_as_degraded():
    policy = ResponsePolicy(
        continuation_split=__import__("re").compile(r"$^"),
        looks_like_incomplete_followthrough=lambda text, n: False,
        sanitize_template_placeholders=lambda text: text,
        looks_like_blocker_response=lambda text: False,
    )

    text, is_error = policy.canonicalize_heartbeat_outcome(
        response_text="HEARTBEAT_OK",
        is_error=False,
        tool_names=[],
        blockers=[],
        action_summaries=[],
        provider_failures=["provider_rate_limited"],
    )

    assert text.startswith("HEARTBEAT_DEGRADED - ")
    assert is_error is False


def test_message_builder_strips_placeholder_auth_profile_in_tool_history():
    builder = MessageBuilder(
        identity=type("I", (), {"build_system_prompt": lambda self, **kwargs: "system"})(),
        tools=type("T", (), {"all_tools": lambda self: []})(),
        workspace="/root/.clawlet",
        context_engine=type("C", (), {"render_for_prompt": lambda self, **kwargs: ""})(),
        memory=type("M", (), {"get_context": lambda self, **kwargs: ""})(),
        heartbeat_state=type("H", (), {"build_prompt_summary": lambda self: ""})(),
        context_window=20,
        heartbeat_action_policy="policy",
        logger=type("L", (), {"debug": lambda self, *a, **k: None, "warning": lambda self, *a, **k: None})(),
    )

    msg = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "http_request",
                    "arguments": '{"method":"GET","url":"https://api.example.com/v1/home","auth_profile":"the live value"}',
                },
            }
        ],
    }

    sanitized = builder._sanitize_message_for_provider(msg)
    assert '"auth_profile"' not in sanitized["tool_calls"][0]["function"]["arguments"]


def test_message_builder_strips_placeholder_http_headers_and_fields_in_tool_history():
    builder = MessageBuilder(
        identity=type("I", (), {"build_system_prompt": lambda self, **kwargs: "system"})(),
        tools=type("T", (), {"all_tools": lambda self: []})(),
        workspace="/root/.clawlet",
        context_engine=type("C", (), {"render_for_prompt": lambda self, **kwargs: ""})(),
        memory=type("M", (), {"get_context": lambda self, **kwargs: ""})(),
        heartbeat_state=type("H", (), {"build_prompt_summary": lambda self: ""})(),
        context_window=20,
        heartbeat_action_policy="policy",
        logger=type("L", (), {"debug": lambda self, *a, **k: None, "warning": lambda self, *a, **k: None})(),
    )

    msg = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "http_request",
                    "arguments": (
                        '{"method":"POST","url":"https://api.example.com/v1/action",'
                        '"headers":{"Authorization":"Bearer the live value"},'
                        '"json_body":{"token":"the live value","note":"keep me"}}'
                    ),
                },
            }
        ],
    }

    sanitized = builder._sanitize_message_for_provider(msg)
    arguments = sanitized["tool_calls"][0]["function"]["arguments"]
    assert "Authorization" not in arguments
    assert '"token"' not in arguments
    assert '"note": "keep me"' in arguments


def test_history_trimmer_compresses_overflow_into_summary():
    class _Msg:
        def __init__(self, role, content, metadata=None):
            self.role = role
            self.content = content
            self.metadata = metadata or {}

    history = [
        _Msg("user", "one"),
        _Msg("assistant", "two"),
        _Msg("user", "three"),
        _Msg("assistant", "four"),
    ]
    trimmer = HistoryTrimmer(
        max_history=3,
        logger=type("L", (), {"debug": lambda *a, **k: None})(),
    )
    trimmer.trim(history)

    assert len(history) == 4 - 1
    assert history[0].role == "system"
    assert history[0].metadata.get("summary") is True
    assert "Conversation summary (compressed)" in history[0].content


def test_history_trimmer_preserves_prior_summary_across_multiple_trims():
    class _Msg:
        def __init__(self, role, content, metadata=None):
            self.role = role
            self.content = content
            self.metadata = metadata or {}

    history = [
        _Msg("system", "Conversation summary (compressed):\nuser: earliest\nassistant: earliest-reply", metadata={"summary": True}),
        _Msg("user", "two"),
        _Msg("assistant", "three"),
        _Msg("user", "four"),
        _Msg("assistant", "five"),
    ]
    trimmer = HistoryTrimmer(
        max_history=4,
        logger=type("L", (), {"debug": lambda *a, **k: None})(),
    )
    trimmer.trim(history)

    assert history[0].metadata.get("summary") is True
    assert "user: earliest" in history[0].content
    assert "assistant: earliest-reply" in history[0].content


def test_recovery_checkpoint_service_saves_and_completes():
    saved = {}
    completed = []

    class _Manager:
        def save(self, checkpoint):
            saved["checkpoint"] = checkpoint

        def mark_completed(self, run_id):
            completed.append(run_id)

    class _Msg:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    service = RecoveryCheckpointService(recovery_manager=_Manager())
    service.save(
        run_id="run-1",
        session_id="sess-1",
        channel="telegram",
        chat_id="123",
        stage="iteration",
        iteration=2,
        history=[_Msg("assistant", "hi"), _Msg("user", "do it")],
        user_id="u1",
        user_name="name",
        tool_stats={"calls_requested": 3},
        pending_confirmation={"token": "111111"},
        notes="note",
    )
    service.complete("run-1")

    checkpoint = saved["checkpoint"]
    assert checkpoint.run_id == "run-1"
    assert checkpoint.user_message == "do it"
    assert checkpoint.pending_confirmation == {"token": "111111"}
    assert completed == ["run-1"]


def test_run_lifecycle_emits_start_completion_and_metadata():
    events = []
    checkpoints = []

    class _Metrics:
        def __init__(self):
            self.messages = 0
            self.errors = 0

        def inc_messages(self):
            self.messages += 1

        def inc_errors(self):
            self.errors += 1

    metrics = _Metrics()
    lifecycle = RunLifecycle(
        emit_runtime_event=lambda event, session_id, payload: events.append((event, session_id, payload)),
        save_checkpoint=lambda **kwargs: checkpoints.append(("save", kwargs)),
        complete_checkpoint=lambda: checkpoints.append(("complete", None)),
        metrics_factory=lambda: metrics,
        event_run_started="run_started",
        event_run_completed="run_completed",
        event_scheduled_run_started="scheduled_started",
        event_scheduled_run_completed="scheduled_completed",
        event_scheduled_run_failed="scheduled_failed",
        sched_payload_job_id="job_id",
        sched_payload_run_id="run_id",
        sched_payload_session_target="session_target",
        sched_payload_wake_mode="wake_mode",
    )

    lifecycle.start_run(
        run_id="run-1",
        session_id="sess-1",
        channel="telegram",
        chat_id="123",
        engine="codex",
        engine_resolved="openrouter",
        source="heartbeat",
        is_heartbeat=True,
        message_preview="hello world",
        metadata={"recovery_run_id": "old-run", "recovery_resume": True},
        scheduled_payload={"job_id": "heartbeat"},
    )
    lifecycle.complete_run(
        run_id="run-1",
        session_id="sess-1",
        iterations=2,
        is_error=False,
        response_text="done",
        scheduled_payload={"job_id": "heartbeat"},
        extra_payload={"tool_stats": {"calls_requested": 1}},
    )
    metadata = lifecycle.build_outbound_metadata(
        source="heartbeat",
        is_heartbeat=True,
        heartbeat_ack_max_chars=24,
        scheduled_payload={
            "job_id": "heartbeat",
            "run_id": "sched-1",
            "session_target": "main",
            "wake_mode": "next_heartbeat",
        },
        extra={"x": "y"},
    )

    assert checkpoints[0][0] == "save"
    assert checkpoints[-1][0] == "complete"
    assert metrics.messages == 1
    assert metrics.errors == 0
    assert events[0][0] == "run_started"
    assert events[1][0] == "scheduled_started"
    assert events[2][0] == "run_completed"
    assert events[2][2]["tool_stats"] == {"calls_requested": 1}
    assert events[3][0] == "scheduled_completed"
    assert metadata["job_id"] == "heartbeat"
    assert metadata["run_id"] == "sched-1"
    assert metadata["x"] == "y"


@pytest.mark.asyncio
async def test_run_prelude_normalizes_input_and_short_circuits_confirmation():
    lifecycle_calls = []
    persisted = []

    class _Lifecycle:
        def start_run(self, **kwargs):
            lifecycle_calls.append(("start", kwargs))

        def complete_short_run(self, **kwargs):
            lifecycle_calls.append(("complete", kwargs))

    class _Message:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    async def _maybe_confirm(**kwargs):
        return "confirmed"

    async def _maybe_install(user_message, history):
        return None

    prelude = RunPrelude(
        run_lifecycle=_Lifecycle(),
        maybe_handle_confirmation_reply=_maybe_confirm,
        maybe_handle_direct_skill_install=_maybe_install,
        queue_persist=lambda session_id, role, content, metadata=None: persisted.append((role, content)),
        logger=type("L", (), {"warning": lambda *a, **k: None, "info": lambda *a, **k: None})(),
        message_cls=_Message,
    )

    result = await prelude.prepare(
        run_id="run-1",
        session_id="sess-1",
        channel="telegram",
        chat_id="123",
        user_message="x" * 12000,
        metadata={},
        source="user",
        is_heartbeat=False,
        scheduled_payload=None,
        heartbeat_ack_max_chars=24,
        history=[],
        convo_key="telegram:123",
        is_internal_autonomous=False,
        engine="codex",
        engine_resolved="openrouter",
    )

    assert len(result.user_message) == 10000
    assert result.short_response == "confirmed"
    assert persisted == []
    assert lifecycle_calls[0][0] == "start"
    assert lifecycle_calls[1][0] == "complete"
