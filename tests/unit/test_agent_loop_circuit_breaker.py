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


class _StreamingProvider:
    name = "streaming"

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks

    def get_default_model(self) -> str:
        return "mock"

    async def complete(self, *args, **kwargs):
        raise AssertionError("streaming callback must use provider.stream()")

    async def stream(self, *args, **kwargs):
        for chunk in self.chunks:
            yield chunk

    async def close(self) -> None:
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_callback_forwards_deltas_with_seq(tmp_workspace: Path):
    provider = _StreamingProvider(chunks=["Hel", "lo ", "world"])
    received: list[tuple[str, int]] = []
    agent = AgentLoop(
        bus=MessageBus(),
        workspace=tmp_workspace,
        identity=Identity(),
        provider=provider,
        storage_config=StorageConfig(sqlite=SQLiteConfig(path=str(tmp_workspace / "loop.db"))),
        stream_callback=lambda chunk, seq: received.append((chunk, seq)),
    )

    response = await agent._call_provider_with_retry([], enable_tools=False)

    assert response.content == "Hello world"
    assert received == [("Hel", 1), ("lo ", 1), ("world", 1)]
    assert agent._stream_call_seq == 1

    # A second call bumps the sequence so consumers can drop stale deltas.
    await agent._call_provider_with_retry([], enable_tools=False)
    assert agent._stream_call_seq == 2

    await agent.close()


class _UsageReportingProvider:
    name = "usage"

    def __init__(self, usage: dict) -> None:
        self.usage = usage

    def get_default_model(self) -> str:
        return "mock"

    async def complete(self, *args, **kwargs):
        return LLMResponse(content="ok", model="mock", usage=self.usage)

    async def close(self) -> None:
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_usage_callback_tracks_latest_prompt_tokens(tmp_workspace: Path):
    # prompt_tokens already includes conversation history, so the meter must
    # show the latest call's value — never a running sum (double-counts).
    provider = _UsageReportingProvider(usage={"prompt_tokens": 100, "completion_tokens": 50})
    reported: list[int] = []
    agent = AgentLoop(
        bus=MessageBus(),
        workspace=tmp_workspace,
        identity=Identity(),
        provider=provider,
        storage_config=StorageConfig(sqlite=SQLiteConfig(path=str(tmp_workspace / "loop.db"))),
    )
    agent.set_usage_callback(reported.append)

    await agent._call_provider_with_retry([], enable_tools=False)
    await agent._call_provider_with_retry([], enable_tools=False)

    assert reported == [100, 100]  # growing conversation would raise the number
    assert agent._context_used_tokens == 100

    await agent.close()
