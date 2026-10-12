"""Delegated turns retain persistence, context, approvals and live config."""

import asyncio
from types import SimpleNamespace

import pytest

from clawlet.agent.identity import Identity
from clawlet.agent.loop import AgentLoop
from clawlet.agent.models import ToolCall
from clawlet.agent.orchestrator import Orchestrator
from clawlet.agent.task_profiles import TaskProfile
from clawlet.bus.queue import InboundMessage, MessageBus, OutboundMessage
from clawlet.config import Config, SQLiteConfig, StorageConfig
from clawlet.tools.registry import ToolResult
from clawlet.tools.registry import ToolRegistry


@pytest.fixture
def parent(workspace, mock_provider, memory_manager):
    agent = AgentLoop(
        bus=MessageBus(),
        workspace=workspace,
        identity=Identity(),
        provider=mock_provider,
        memory_manager=memory_manager,
        storage_config=StorageConfig(
            sqlite=SQLiteConfig(path=str(workspace / "loop.db"))
        ),
    )
    agent.full_config = Config(provider={"primary": "ollama"})
    return agent


@pytest.fixture
def providers(monkeypatch):
    created = []

    def build(name, config, *, model=""):
        async def close():
            provider.closed = True

        provider = SimpleNamespace(
            name=name,
            model=model or getattr(config, name).model,
            closed=False,
            close=close,
        )
        provider.get_default_model = lambda: provider.model
        created.append(provider)
        return provider

    monkeypatch.setattr("clawlet.agent.provider_factory.build_provider", build)
    return created


async def drain(parent):
    if parent._persist_tasks:
        await asyncio.wait_for(asyncio.gather(*list(parent._persist_tasks)), 2)
    assert not parent._persist_tasks


async def test_delegated_persistence_and_followup_context(
    parent, providers, monkeypatch
):
    received = []

    async def core(child, msg, convo, run_ctx):
        received.append(msg)
        assert child.storage is parent.storage
        assert child._storage_ready is parent._storage_ready
        assert child._persist_tasks is parent._persist_tasks
        assert not convo.history  # Do not reload the full parent history.
        child._queue_persist(convo.session_id, "user", msg.content)
        child._queue_persist(convo.session_id, "assistant", "Use the blue design.")
        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content="Use the blue design."
        )

    monkeypatch.setattr(AgentLoop, "_process_message_core", core)
    await parent._initialize_storage()
    try:
        orch = Orchestrator(parent)
        msg = InboundMessage(
            channel="cli", chat_id="main", content="Suggest a design for my app"
        )
        first = await orch.process_message(msg)
        await drain(parent)
        stored = await parent.storage.get_messages(first.metadata["child_session_id"])
        assert [m.role for m in stored] == ["user", "assistant"]
        await orch.process_message(
            InboundMessage(channel="cli", chat_id="main", content="apply that change")
        )
        assert "Use the blue design." in received[1].content
        assert "Suggest a design for my app" in received[1].content
        assert "[Delegated task" in received[1].content
        assert msg.content == "Suggest a design for my app" and msg.metadata == {}
        await drain(parent)
        assert all(p.closed for p in providers)
        assert parent.storage.is_initialized()
        convo = await parent._get_conversation_state("cli", "main")
        assert [m.role for m in convo.history] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]
        assert len(await parent.storage.get_messages(convo.session_id)) == 4
    finally:
        await parent.close()


@pytest.mark.parametrize("reply", ["confirm 123456", "cancel", "confirm 999999"])
async def test_approval_reply_uses_parent_state(parent, providers, monkeypatch, reply):
    from clawlet.agent.run_orchestrator import RunOrchestrator

    async def core(child, msg, convo, run_ctx):
        assert child._approval_service is parent._approval_service
        child._approval_service.set(
            "cli:main", "123456", ToolCall("call-1", "shell", {"command": "echo ok"})
        )
        return OutboundMessage(
            channel="cli", chat_id="main", content="Approval required"
        )

    monkeypatch.setattr(
        parent, "_execute_tool", lambda *args, **kwargs: execute(*args, **kwargs)
    )
    executed = []

    async def execute(tc, *, approved):
        executed.append((tc.name, approved))
        return ToolResult(success=True, output="ok")

    await parent._initialize_storage()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(AgentLoop, "_process_message_core", core)
            await parent._process_message(
                InboundMessage(
                    channel="cli", chat_id="main", content="Run the shell command"
                )
            )
        out = await RunOrchestrator(parent).process_message(
            InboundMessage(channel="cli", chat_id="main", content=reply)
        )
        assert len(providers) == 1  # Confirmation never spawns a fresh filtered worker.
        assert executed == ([("shell", True)] if reply == "confirm 123456" else [])
        assert bool(parent.peek_pending_confirmation("cli", "main")) == (
            reply == "confirm 999999"
        )
        assert (
            "does not match"
            if reply == "confirm 999999"
            else "Cancelled" if reply == "cancel" else "Confirmed and executed"
        ) in out.content
        await drain(parent)
    finally:
        await parent.close()


@pytest.mark.parametrize(
    "failure", [RuntimeError("failed"), TimeoutError(), asyncio.CancelledError()]
)
async def test_child_provider_closed_on_failure(
    parent, providers, monkeypatch, failure
):
    async def core(*args):
        raise failure

    monkeypatch.setattr(AgentLoop, "_process_message_core", core)
    await parent._initialize_storage()
    try:
        orch = Orchestrator(parent)
        msg = InboundMessage(
            channel="cli", chat_id="main", content="Discuss the proposal"
        )
        if isinstance(failure, asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await orch.dispatch_single(msg, await orch.decide(msg.content))
        else:
            assert (
                await orch.dispatch_single(msg, await orch.decide(msg.content))
            ).error
        assert providers[0].closed
        assert parent.storage.is_initialized()
        await drain(parent)
    finally:
        await parent.close()


async def test_live_model_switch_reaches_next_child(parent, providers, monkeypatch):
    from clawlet.tui import runtime_adapter

    config = parent.full_config
    config.storage = StorageConfig(
        sqlite=SQLiteConfig(path=str(parent.storage.db_path))
    )
    captured = []

    def make_agent(**kwargs):
        agent = AgentLoop(**kwargs)
        captured.append(agent)
        return agent

    async def run(agent):
        await agent._initialize_storage()
        await asyncio.Event().wait()

    monkeypatch.setattr("clawlet.config.load_config", lambda workspace: config)
    monkeypatch.setattr(
        runtime_adapter,
        "_create_provider",
        lambda config, model: (parent.provider, parent.model),
    )
    monkeypatch.setattr(
        "clawlet.runtime.build_runtime_services",
        lambda *args: SimpleNamespace(
            tools=ToolRegistry(), memory_manager=parent.memory
        ),
    )
    monkeypatch.setattr(AgentLoop, "run", run)
    monkeypatch.setattr("clawlet.agent.loop.AgentLoop", make_agent)
    handle = await runtime_adapter.create_local_runtime(
        parent.workspace, None, lambda event: None
    )
    agent = captured[0]
    await asyncio.wait_for(agent._storage_ready.wait(), 2)
    try:
        await handle.switch_model("ollama", "new-model")
        assert config.provider.primary == "ollama"
        assert config.provider.ollama.model == "new-model"

        async def core(child, msg, convo, run_ctx):
            assert child.provider.name == "ollama"
            assert child.model == "new-model"
            return OutboundMessage(channel="cli", chat_id="main", content="Done")

        monkeypatch.setattr(AgentLoop, "_process_message_core", core)
        await agent._process_message(
            InboundMessage(
                channel="cli", chat_id="main", content="Discuss this proposal"
            )
        )
        config.task_profiles["code"] = TaskProfile(
            provider="anthropic", model="pinned-model"
        )
        profile, _ = Orchestrator(agent).resolve("code")
        assert (profile.provider, profile.model) == ("anthropic", "pinned-model")
        await drain(agent)
    finally:
        await handle.stop()
