from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from clawlet.agent.identity import Identity
from clawlet.agent.loop import AgentLoop
from clawlet.bus.queue import MessageBus
from clawlet.config import SQLiteConfig, StorageConfig
from clawlet.exceptions import CircuitBreakerOpen
from clawlet.providers.base import LLMResponse


class _FlakyProvider:
    name = "flaky"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = True

    def get_default_model(self) -> str:
        return "mock"

    async def complete(self, *args, **kwargs):
        self.calls += 1
        if self.fail:
            request = httpx.Request("POST", "https://example.test")
            raise httpx.RequestError("boom", request=request)
        return LLMResponse(content="ok", model="mock", usage={})

    async def close(self) -> None:
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_loop_uses_provider_circuit_breaker(tmp_workspace: Path, monkeypatch: pytest.MonkeyPatch):
    provider = _FlakyProvider()
    agent = AgentLoop(
        bus=MessageBus(),
        workspace=tmp_workspace,
        identity=Identity(),
        provider=provider,
        storage_config=StorageConfig(sqlite=SQLiteConfig(path=str(tmp_workspace / "loop.db"))),
    )

    async def _fast_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("clawlet.agent.loop.asyncio.sleep", _fast_sleep)

    with pytest.raises(httpx.RequestError):
        await agent._call_provider_with_retry([], enable_tools=False)

    with pytest.raises(CircuitBreakerOpen):
        await agent._call_provider_with_retry([], enable_tools=False)

    assert agent._provider_circuit_breaker.state == agent._provider_circuit_breaker.OPEN

    agent._provider_circuit_breaker.recovery_timeout = 0.0
    provider.fail = False

    response = await agent._call_provider_with_retry([], enable_tools=False)

    assert response.content == "ok"
    assert agent._provider_circuit_breaker.state == agent._provider_circuit_breaker.CLOSED

    await agent.close()
