from clawlet.tui.events import (
    ApprovalRequest,
    AssistantMessage,
    BrainStateUpdate,
    HeartbeatSnapshot,
    ToolLifecycle,
    UserSubmitted,
)
from clawlet.tui.state import TuiStore


def test_tui_store_reduces_core_events():
    store = TuiStore('/tmp/ws')
    store.reduce(UserSubmitted(session_id='local', content='hello'))
    store.reduce(AssistantMessage(session_id='local', content='hi there'))
    store.reduce(ToolLifecycle(session_id='local', tool_name='file_manager', status='SUCCESS', summary='Read file', arguments={'path': 'README.md'}))
    store.reduce(ApprovalRequest(session_id='local', reason='unsafe', token='abc123', tool_name='shell', arguments={'command': 'rm -rf .'}))
    store.reduce(BrainStateUpdate(session_id='local', provider='openai', model='gpt', status='RUNNING', context_used_tokens=1024, context_max_tokens=4096, memory=[('project_root', '/tmp/ws')], tools=[('shell', 'ACTIVE')]))
    store.reduce(HeartbeatSnapshot(enabled=True, interval_minutes=30, quiet_hours='Disabled', pulse_label='12m 45s', last_task='sync', active_crons=1))

    state = store.state
    assert state.session_id == 'local'
    assert len(state.transcript) == 4
    assert state.pending_approval is not None
    assert state.brain.provider == 'openai'
    assert state.heartbeat.enabled is True
    assert not hasattr(state, 'logs')


def _tool(name, status, summary):
    return ToolLifecycle(session_id='local', tool_name=name, status=status, summary=summary)


def test_tool_same_title_morphs_in_place():
    from clawlet.tui.state import TuiStore

    store = TuiStore('/tmp/ws')
    store.reduce(_tool('shell', 'RUNNING', 'Executing tool.'))
    store.reduce(_tool('shell', 'RUNNING', 'Executing tool.'))
    assert len(store.state.transcript) == 1
    store.reduce(_tool('shell', 'SUCCESS', 'listed 4 files'))
    assert len(store.state.transcript) == 1
    assert store.state.transcript[0].status == 'SUCCESS'
    assert store.state.transcript[0].body == 'listed 4 files'
    store.reduce(_tool('shell', 'RUNNING', 'Executing tool.'))
    assert len(store.state.transcript) == 2  # new call after terminal state


def test_exact_duplicate_messages_skipped():
    from clawlet.tui.state import TuiStore

    store = TuiStore('/tmp/ws')
    store.reduce(UserSubmitted(session_id='local', content='hi'))
    store.reduce(UserSubmitted(session_id='local', content='hi'))
    store.reduce(AssistantMessage(session_id='local', content='hello'))
    store.reduce(AssistantMessage(session_id='local', content='hello'))
    store.reduce(AssistantMessage(session_id='local', content='different'))
    assert [e.body for e in store.state.transcript] == ['hi', 'hello', 'different']


def test_activity_steps_build_trace_with_statuses():
    from clawlet.tui.events import ActivityStep
    from clawlet.tui.state import TuiStore

    store = TuiStore('/tmp/ws')
    store.reduce(UserSubmitted(session_id='local', content='hello'))
    store.reduce(ActivityStep(event_type='started', text='Starting work on your request.'))
    store.reduce(ActivityStep(event_type='provider_started', text='Thinking about the next step.'))
    store.reduce(ActivityStep(event_type='tool_started', text='Running `shell`.', detail='shell'))
    store.reduce(ActivityStep(event_type='tool_completed', text='Completed `shell`.', detail='shell'))
    store.reduce(ActivityStep(event_type='tool_failed', text='`boom` failed.', detail='boom'))

    steps = store.state.thinking_steps
    assert [s.event_type for s in steps] == [
        'started', 'provider_started', 'tool_started', 'tool_completed', 'tool_failed',
    ]
    assert [s.text for s in steps] == [
        'Starting work on your request.',
        'Thinking about the next step.',
        'Running `shell`.',
        'Completed `shell`.',
        '`boom` failed.',
    ]
    assert [s.detail for s in steps] == ['', '', 'shell', 'shell', 'boom']
    assert store.state.thinking_started_at is not None
    assert store.state.thinking_done_at is None


def test_consecutive_identical_steps_deduped():
    from clawlet.tui.events import ActivityStep
    from clawlet.tui.state import TuiStore

    store = TuiStore('/tmp/ws')
    store.reduce(ActivityStep(event_type='provider_started', text='Thinking about the next step.'))
    store.reduce(ActivityStep(event_type='provider_started', text='Thinking about the next step.'))
    assert len(store.state.thinking_steps) == 1


def test_new_user_turn_resets_activity():
    from clawlet.tui.events import ActivityStep, AssistantDelta
    from clawlet.tui.state import TuiStore

    store = TuiStore('/tmp/ws')
    store.reduce(ActivityStep(event_type='provider_started', text='Thinking about the next step.'))
    store.reduce(AssistantDelta(text='hello ', seq=1))
    store.reduce(AssistantDelta(text='world', seq=1))
    assert store.state.draft is not None
    assert store.state.draft.text == 'hello world'

    store.reduce(UserSubmitted(session_id='local', content='next turn'))
    assert store.state.draft is None
    assert store.state.thinking_steps == []


def test_draft_delta_lifecycle_and_stale_seq():
    from clawlet.tui.events import AssistantDelta, ToolLifecycle
    from clawlet.tui.state import TuiStore

    store = TuiStore('/tmp/ws')
    # call 1 streams, then a tool runs -> draft dropped
    store.reduce(AssistantDelta(text='Narration ', seq=1))
    store.reduce(ToolLifecycle(session_id='local', tool_name='shell', status='RUNNING', summary='Executing tool.'))
    assert store.state.draft is None
    # stale deltas from call 1 must NOT reopen the draft
    store.reduce(AssistantDelta(text='Narration ', seq=1))
    assert store.state.draft is None
    # call 2 supersedes
    store.reduce(AssistantDelta(text='Final ', seq=2))
    store.reduce(AssistantDelta(text='answer', seq=2))
    assert store.state.draft is not None
    assert store.state.draft.text == 'Final answer'
    assert store.state.draft.seq == 2
    # the canonical message lands -> draft clears, done timestamp set
    store.reduce(AssistantMessage(session_id='local', content='Final answer'))
    assert store.state.draft is None
    assert store.state.thinking_done_at is not None


def test_provider_started_discards_stale_draft():
    from clawlet.tui.events import ActivityStep, AssistantDelta
    from clawlet.tui.state import TuiStore

    store = TuiStore('/tmp/ws')
    store.reduce(AssistantDelta(text='suppressed narration', seq=1))
    store.reduce(ActivityStep(event_type='provider_started', text='Thinking about the next step.'))
    assert store.state.draft is None


def test_usage_update_merges_without_clobbering_brain():
    from clawlet.tui.events import BrainStateUpdate, UsageUpdate
    from clawlet.tui.state import TuiStore

    store = TuiStore('/tmp/ws')
    store.reduce(BrainStateUpdate(session_id='local', provider='openai', model='gpt', status='RUNNING', context_max_tokens=128000, memory=[], tools=[]))
    store.reduce(UsageUpdate(context_used_tokens=4096))
    assert store.state.brain.provider == 'openai'
    assert store.state.brain.status == 'RUNNING'
    assert store.state.brain.context_used_tokens == 4096


def test_heartbeat_tasks_passthrough():
    from clawlet.tui.events import HeartbeatSnapshot
    from clawlet.tui.state import TuiStore

    store = TuiStore('/tmp/ws')
    store.reduce(HeartbeatSnapshot(enabled=True, interval_minutes=30, tasks=[('sync', 'every 30m', 'scheduled')]))
    assert store.state.heartbeat.tasks == [('sync', 'every 30m', 'scheduled')]
    assert store.state.heartbeat.enabled is True


def test_heartbeat_task_rows_no_fabricated_times(tmp_path):
    """Fallback rows carry real interval metadata, never invented clock times."""
    from types import SimpleNamespace

    from clawlet.tui.runtime_adapter import _heartbeat_task_rows

    (tmp_path / 'HEARTBEAT.md').write_text(
        '# Periodic Tasks\n\n- Sync notes with git\n- Prune stale memory\n',
        encoding='utf-8',
    )
    config = SimpleNamespace(
        heartbeat=SimpleNamespace(
            enabled=True,
            interval_minutes=30,
            quiet_hours_start=0,
            quiet_hours_end=0,
        )
    )
    rows = _heartbeat_task_rows(tmp_path, config)
    assert rows
    assert rows[0][1] == 'every 30m'
    assert rows[0][2] == 'scheduled'
    assert not any('00:30' in meta for _, meta, _ in rows)


def test_heartbeat_task_rows_disabled_is_paused(tmp_path):
    from types import SimpleNamespace

    from clawlet.tui.runtime_adapter import _heartbeat_task_rows

    (tmp_path / 'HEARTBEAT.md').write_text('- Sync notes with git\n', encoding='utf-8')
    config = SimpleNamespace(
        heartbeat=SimpleNamespace(
            enabled=False,
            interval_minutes=0,
            quiet_hours_start=0,
            quiet_hours_end=0,
        )
    )
    rows = _heartbeat_task_rows(tmp_path, config)
    assert rows[0][2] == 'paused'
    assert rows[0][1] == 'manual'
