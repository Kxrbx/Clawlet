"""Stream usage capture tests with mocked wire bytes (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clawlet.agent.identity import Identity
from clawlet.agent.loop import AgentLoop
from clawlet.bus.queue import MessageBus
from clawlet.config import SQLiteConfig, StorageConfig
from clawlet.providers.lmstudio import LMStudioProvider
from clawlet.providers.ollama import OllamaProvider
from clawlet.providers.openai import OpenAIProvider
from clawlet.providers.openai_compat import OpenAICompatibleProvider
from clawlet.providers.openrouter import OpenRouterProvider


class FakeStreamResponse:
    def __init__(self, body: bytes):
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        for line in self.body.decode().splitlines():
            yield line


class FakeClient:
    is_closed = False

    def __init__(self, body: bytes):
        self.body = body
        self.requests: list[dict] = []

    def stream(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return FakeStreamResponse(self.body)


class _TestCompatProvider(OpenAICompatibleProvider):
    BASE_URL = "https://example.test/v1"
    PROVIDER_NAME = "test-compat"
    ENV_VAR_HINT = "TEST_COMPAT_API_KEY"
    CONFIG_PATH_HINT = "provider.test_compat.api_key"
    DEFAULT_MODELS = ["test-model"]
    FALLBACK_MODEL = "test-model"


def _sse(*chunks: dict) -> bytes:
    lines = [f"data: {json.dumps(c)}" for c in chunks] + ["data: [DONE]"]
    return "\n".join(lines).encode()


async def _collect(provider, **kwargs):
    return [c async for c in provider.stream(
        [{"role": "user", "content": "hi"}], model="m", **kwargs
    )]


@pytest.mark.unit
async def test_openai_stream_captures_usage():
    body = _sse(
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
    )
    provider = OpenAIProvider(api_key="x")
    client = FakeClient(body)
    provider._client = client  # noqa: SLF001 - seam under test
    assert "".join(await _collect(provider)) == "Hello"
    assert provider.last_stream_usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert client.requests[0]["json"]["stream_options"] == {"include_usage": True}


@pytest.mark.unit
async def test_openai_stream_preserves_caller_stream_options():
    provider = OpenAIProvider(api_key="x")
    client = FakeClient(_sse({"choices": [{"delta": {"content": "x"}}]}))
    provider._client = client  # noqa: SLF001 - seam under test
    await _collect(provider, stream_options={"include_usage": False})
    assert client.requests[0]["json"]["stream_options"] == {"include_usage": False}
    assert provider.last_stream_usage == {}


@pytest.mark.unit
async def test_openrouter_stream_captures_usage():
    body = _sse(
        {"choices": [{"delta": {"content": "Hi"}}]},
        {"choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}},
    )
    provider = OpenRouterProvider(api_key="x")
    client = FakeClient(body)
    provider._client = client  # noqa: SLF001 - seam under test
    assert "".join(await _collect(provider)) == "Hi"
    assert provider.last_stream_usage == {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}
    assert client.requests[0]["json"]["stream_options"] == {"include_usage": True}


@pytest.mark.unit
async def test_openai_compat_stream_captures_usage():
    body = _sse(
        {"choices": [{"delta": {"content": "Yo"}}]},
        {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}},
    )
    provider = _TestCompatProvider(api_key="x")
    client = FakeClient(body)
    provider._client = client  # noqa: SLF001 - seam under test
    assert "".join(await _collect(provider)) == "Yo"
    assert provider.last_stream_usage == {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
    assert client.requests[0]["json"]["stream_options"] == {"include_usage": True}


@pytest.mark.unit
async def test_ollama_stream_captures_usage():
    body = "\n".join([
        json.dumps({"message": {"content": "Hi"}, "done": False}),
        json.dumps({"done": True, "prompt_eval_count": 7, "eval_count": 3}),
    ]).encode()
    provider = OllamaProvider()
    client = FakeClient(body)
    provider._client = client  # noqa: SLF001 - seam under test
    assert "".join(await _collect(provider)) == "Hi"
    assert provider.last_stream_usage == {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}


@pytest.mark.unit
async def test_lmstudio_stream_resets_usage_without_stream_options():
    body = _sse({"choices": [{"delta": {"content": "local"}}]})
    provider = LMStudioProvider()
    provider.last_stream_usage = {"prompt_tokens": 99, "completion_tokens": 99, "total_tokens": 198}
    client = FakeClient(body)
    provider._client = client  # noqa: SLF001 - seam under test
    assert "".join(await _collect(provider)) == "local"
    assert provider.last_stream_usage == {}
    assert "stream_options" not in client.requests[0]["json"]


class _StreamUsageProvider:
    name = "stream-usage"

    def __init__(self) -> None:
        self.last_stream_usage = {"prompt_tokens": 42, "completion_tokens": 8, "total_tokens": 50}

    def get_default_model(self) -> str:
        return "mock"

    async def complete(self, *args, **kwargs):
        raise AssertionError("streaming callback must use provider.stream()")

    async def stream(self, *args, **kwargs):
        yield "Hello"
        self.last_stream_usage = {"prompt_tokens": 42, "completion_tokens": 8, "total_tokens": 50}

    async def close(self) -> None:
        return None


@pytest.mark.unit
async def test_loop_stream_forwards_usage_to_callback(tmp_workspace: Path):
    provider = _StreamUsageProvider()
    received: list[str] = []
    reported: list[int] = []
    agent = AgentLoop(
        bus=MessageBus(),
        workspace=tmp_workspace,
        identity=Identity(),
        provider=provider,
        storage_config=StorageConfig(sqlite=SQLiteConfig(path=str(tmp_workspace / "loop.db"))),
        stream_callback=lambda chunk, seq: received.append(chunk),
    )
    agent.set_usage_callback(reported.append)

    response = await agent._call_provider_with_retry([], enable_tools=False)

    assert response.content == "Hello"
    assert response.usage == {"prompt_tokens": 42, "completion_tokens": 8, "total_tokens": 50}
    assert reported == [42]
    assert agent._context_used_tokens == 42

    await agent.close()
