"""
Pytest fixtures and configuration.
"""

import sys
from pathlib import Path

# Add workspace to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
import tempfile
from clawlet.agent.loop import AgentLoop
from clawlet.agent.identity import IdentityLoader
from clawlet.bus.queue import MessageBus
from clawlet.providers.base import BaseProvider, LLMResponse
from clawlet.tools.registry import ToolRegistry
from clawlet.config import (
    Config,
    ProviderConfig,
    OpenRouterConfig,
    RuntimeReplaySettings,
    RuntimeSettings,
    SQLiteConfig,
    StorageConfig,
)


class DummyProvider(BaseProvider):
    """A simple provider for testing."""
    def __init__(self, responses=None):
        self.responses = responses or ["Test response"]
        self.index = 0
    
    @property
    def name(self) -> str:
        return "dummy"
    
    def get_default_model(self) -> str:
        return "dummy-model"
    
    async def complete(self, messages, model=None, temperature=0.7, max_tokens=4096, **kwargs):
        response = self.responses[self.index % len(self.responses)]
        self.index += 1
        return LLMResponse(content=response, model=model or "dummy", usage={}, finish_reason="stop")
    
    async def stream(self, messages, model=None, temperature=0.7, max_tokens=4096, **kwargs):
        yield "Test"
    
    async def close(self):
        pass


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with required files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "SOUL.md").write_text("# SOUL\nName: TestAgent\nVibe: Test")
        (workspace / "USER.md").write_text("# USER\nName: Human")
        (workspace / "MEMORY.md").write_text("# MEMORY\nInitial")
        (workspace / "HEARTBEAT.md").write_text("# HEARTBEAT\nTasks:\n- Test")
        yield workspace


@pytest.fixture
def dummy_config(temp_workspace):
    """Create a Config object with SQLite storage."""
    sqlite_cfg = SQLiteConfig(path=str(temp_workspace / "clawlet.db"))
    runtime_cfg = RuntimeSettings(
        replay=RuntimeReplaySettings(
            enabled=True,
            directory=str(temp_workspace / ".runtime"),
            retention_days=7,
            redact_tool_outputs=False,
        )
    )
    provider_cfg = ProviderConfig(
        primary="openrouter",
        openrouter=OpenRouterConfig(api_key="dummy-key-for-tests", model="dummy-model")
    )
    storage_cfg = StorageConfig(backend="sqlite", sqlite=sqlite_cfg)
    config = Config(provider=provider_cfg, storage=storage_cfg, runtime=runtime_cfg)
    config.config_path = temp_workspace / "config.yaml"
    return config


@pytest.fixture
def dummy_provider():
    """Create a DummyProvider."""
    return DummyProvider(responses=["Hello!", "How can I help?", "Goodbye!"])


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def agent_loop(temp_workspace, dummy_config, dummy_provider, event_loop):
    """Create an AgentLoop instance for testing."""
    bus = MessageBus()
    identity_loader = IdentityLoader(temp_workspace)
    identity = identity_loader.load_all()
    tools = ToolRegistry()
    
    agent = AgentLoop(
        bus=bus,
        workspace=temp_workspace,
        identity=identity,
        provider=dummy_provider,
        tools=tools,
        model="dummy-model",
        storage_config=dummy_config.storage,
    )
    
    # Initialize storage
    event_loop.run_until_complete(agent._initialize_storage())
    
    yield agent
    
    # Cleanup
    try:
        event_loop.run_until_complete(agent.close())
    except RuntimeError:
        pass

