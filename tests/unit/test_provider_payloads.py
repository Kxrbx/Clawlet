"""Offline payload tests for Anthropic/Google providers (no network).

Verifies OpenAI-format tools/tool_choice translation, no-tools behavior,
and system-role mapping for both complete() and stream().
"""

import asyncio

from clawlet.providers.anthropic import AnthropicProvider
from clawlet.providers.google import GoogleProvider

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
            },
        },
    }
]

SYSTEM_MESSAGES = [
    {"role": "system", "content": "sys-one"},
    {"role": "system", "content": "sys-two"},
    {"role": "user", "content": "hi"},
]


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


class FakeAnthropicResponse:
    status_code = 200
    text = "ok"

    def raise_for_status(self):
        pass

    def json(self):
        return {"content": [{"text": "ok"}], "usage": {}, "stop_reason": "end_turn"}


class FakeAnthropicClient:
    is_closed = False

    def __init__(self, body: bytes):
        self.body = body
        self.requests: list[dict] = []

    async def post(self, url, **kwargs):
        self.requests.append({"url": url, **kwargs})
        return FakeAnthropicResponse()

    def stream(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return FakeStreamResponse(self.body)


class FakeGoogleResponse:
    status_code = 200
    text = "ok"

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "candidates": [
                {"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}
            ]
        }


class FakeGoogleClient:
    is_closed = False

    def __init__(self, body: bytes):
        self.body = body
        self.requests: list[dict] = []

    async def post(self, url, **kwargs):
        self.requests.append({"url": url, **kwargs})
        return FakeGoogleResponse()

    def stream(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return FakeStreamResponse(self.body)


ANTH_STREAM_BODY = (
    b'data: {"type": "content_block_delta", '
    b'"delta": {"type": "text_delta", "text": "hi"}}\n'
)
GOOGLE_STREAM_BODY = (
    b'data: {"candidates": [{"content": {"parts": [{"text": "hi"}], '
    b'"role": "model"}}]}\n'
)


def _anth_complete(payload_kwargs=None):
    provider = AnthropicProvider(api_key="x")
    client = FakeAnthropicClient(ANTH_STREAM_BODY)
    provider._client = client  # noqa: SLF001 - seam under test

    async def run():
        return await provider.complete(
            [{"role": "user", "content": "hi"}],
            model="m",
            **(payload_kwargs or {}),
        )

    asyncio.run(run())
    return client.requests[0]["json"]


def _anth_stream(payload_kwargs=None):
    provider = AnthropicProvider(api_key="x")
    client = FakeAnthropicClient(ANTH_STREAM_BODY)
    provider._client = client  # noqa: SLF001 - seam under test

    async def collect():
        return [c async for c in provider.stream(
            [{"role": "user", "content": "hi"}],
            model="m",
            **(payload_kwargs or {}),
        )]

    asyncio.run(collect())
    return client.requests[0]["json"]


def _google_complete(messages, payload_kwargs=None):
    provider = GoogleProvider(api_key="x")
    client = FakeGoogleClient(GOOGLE_STREAM_BODY)
    provider._client = client  # noqa: SLF001 - seam under test

    async def run():
        return await provider.complete(messages, model="m", **(payload_kwargs or {}))

    asyncio.run(run())
    return client.requests[0]["json"]


def _google_stream(messages, payload_kwargs=None):
    provider = GoogleProvider(api_key="x")
    client = FakeGoogleClient(GOOGLE_STREAM_BODY)
    provider._client = client  # noqa: SLF001 - seam under test

    async def collect():
        return [c async for c in provider.stream(messages, model="m", **(payload_kwargs or {}))]

    asyncio.run(collect())
    return client.requests[0]["json"]


def test_anthropic_complete_tools_translated():
    payload = _anth_complete({"tools": OPENAI_TOOLS, "tool_choice": "auto"})
    assert payload["tools"] == [
        {"name": "get_weather", "description": "Get weather",
         "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}}}
    ]
    assert payload["tool_choice"] == {"type": "auto"}


def test_anthropic_stream_tools_translated():
    payload = _anth_stream({"tools": OPENAI_TOOLS, "tool_choice": "auto"})
    assert payload["tools"] == [
        {"name": "get_weather", "description": "Get weather",
         "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}}}
    ]
    assert payload["tool_choice"] == {"type": "auto"}


def test_anthropic_complete_no_tools_adds_no_keys():
    payload = _anth_complete()
    assert "tools" not in payload
    assert "tool_choice" not in payload


def test_anthropic_stream_no_tools_adds_no_keys():
    payload = _anth_stream()
    assert "tools" not in payload
    assert "tool_choice" not in payload


def _anth_system_payload(complete: bool):
    provider = AnthropicProvider(api_key="x")
    client = FakeAnthropicClient(ANTH_STREAM_BODY)
    provider._client = client  # noqa: SLF001 - seam under test

    async def run():
        if complete:
            await provider.complete(list(SYSTEM_MESSAGES), model="m")
        else:
            [c async for c in provider.stream(list(SYSTEM_MESSAGES), model="m")]

    asyncio.run(run())
    return client.requests[0]["json"]


def test_anthropic_complete_system_mapped():
    payload = _anth_system_payload(complete=True)
    assert payload["system"] == "sys-one\n\nsys-two"
    assert all(m.get("role") != "system" for m in payload["messages"])
    assert payload["messages"] == [{"role": "user", "content": "hi"}]


def test_anthropic_stream_system_mapped():
    payload = _anth_system_payload(complete=False)
    assert payload["system"] == "sys-one\n\nsys-two"
    assert all(m.get("role") != "system" for m in payload["messages"])
    assert payload["messages"] == [{"role": "user", "content": "hi"}]


def test_google_complete_tools_translated():
    payload = _google_complete(
        [{"role": "user", "content": "hi"}],
        {"tools": OPENAI_TOOLS, "tool_choice": "auto"},
    )
    assert payload["tools"] == [{
        "functionDeclarations": [{
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
        }]
    }]
    assert payload["toolConfig"] == {"functionCallingConfig": {"mode": "AUTO"}}


def test_google_stream_tools_translated():
    payload = _google_stream(
        [{"role": "user", "content": "hi"}],
        {"tools": OPENAI_TOOLS, "tool_choice": "auto"},
    )
    assert payload["tools"] == [{
        "functionDeclarations": [{
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
        }]
    }]
    assert payload["toolConfig"] == {"functionCallingConfig": {"mode": "AUTO"}}


def test_google_complete_no_tools_adds_no_keys():
    payload = _google_complete([{"role": "user", "content": "hi"}])
    assert "tools" not in payload
    assert "toolConfig" not in payload


def test_google_stream_no_tools_adds_no_keys():
    payload = _google_stream([{"role": "user", "content": "hi"}])
    assert "tools" not in payload
    assert "toolConfig" not in payload


def test_google_complete_system_mapped():
    payload = _google_complete(list(SYSTEM_MESSAGES))
    assert payload["systemInstruction"] == {"parts": [{"text": "sys-one\n\nsys-two"}]}
    texts = [p.get("text", "") for c in payload["contents"] for p in c.get("parts", [])]
    assert "sys-one" not in texts and "sys-two" not in texts


def test_google_stream_system_mapped():
    payload = _google_stream(list(SYSTEM_MESSAGES))
    assert payload["systemInstruction"] == {"parts": [{"text": "sys-one\n\nsys-two"}]}
    texts = [p.get("text", "") for c in payload["contents"] for p in c.get("parts", [])]
    assert "sys-one" not in texts and "sys-two" not in texts
