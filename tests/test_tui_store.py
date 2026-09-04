from clawlet.tui.events import ApprovalRequest, AssistantMessage, BrainStateUpdate, HeartbeatSnapshot, ToolLifecycle, UserSubmitted
from clawlet.tui.state import TuiStore


def test_tui_store_reduces_core_events():
    store = TuiStore('/tmp/ws')
    store.reduce(UserSubmitted(session_id='local', content='hello'))
    store.reduce(AssistantMessage(session_id='local', content='hi there'))
    store.reduce(ToolLifecycle(session_id='local', tool_name='file_manager', status='SUCCESS', summary='Read file', arguments={'path': 'README.md'}))
    store.reduce(ApprovalRequest(session_id='local', reason='unsafe', token='abc123', tool_name='shell', arguments={'command': 'rm -rf .'}))
    store.reduce(BrainStateUpdate(session_id='local', provider='openai', model='gpt', status='RUNNING', context_used_tokens=1024, context_max_tokens=4096, memory=[('project_root', '/tmp/ws')], tools=[('shell', 'ACTIVE')]))
    store.reduce(HeartbeatSnapshot(enabled=True, interval_minutes=30, quiet_hours='Disabled', next_runs=['00:10:00 [task] sync'], pulse_label='12m 45s', last_task='sync', active_crons=1))

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
