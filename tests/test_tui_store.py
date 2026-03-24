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
    assert state.logs
