"""Streaming parser tests with mocked wire bytes (no network).

Covers the Google streamGenerateContent formats: plain JSON array
(default) and SSE (alt=sse).
"""

import asyncio

import pytest

from clawlet.providers.google import GoogleProvider

ARRAY_BODY = (
    b'[{"candidates": [{"content": {"parts": [{"text": "Hello"}], '
    b'"role": "model"}}]}, {"candidates": [{"content": {"parts": '
    b'[{"text": " world"}], "role": "model"}}]}]'
)

SSE_BODY = (
    b'data: {"candidates": [{"content": {"parts": [{"text": "Hello"}], '
    b'"role": "model"}}]}\n'
    b'\n'
    b'data: {"candidates": [{"content": {"parts": [{"text": " world"}], '
    b'"role": "model"}}]}\n'
    b'\n'
)


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


def run_stream(body: bytes):
    provider = GoogleProvider(api_key="x")
    client = FakeClient(body)
    provider._client = client  # noqa: SLF001 - seam under test

    async def collect():
        return [c async for c in provider.stream(
            [{"role": "user", "content": "hi"}], model="gemini-4-pro"
        )]

    return asyncio.run(collect()), client.requests


def test_google_stream_yields_both_chunks():
    chunks, requests = run_stream(SSE_BODY)
    assert "".join(chunks) == "Hello world"
    assert requests[0]["params"].get("alt") == "sse"


def test_google_stream_sends_no_bogus_generation_params():
    _, requests = run_stream(SSE_BODY)
    generation_config = requests[0]["json"]["generationConfig"]
    assert "stream" not in generation_config
