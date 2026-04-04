import asyncio
from unittest.mock import patch

from clawlet.providers.base import HTTPClientManager, LLMResponse


def test_llm_response_tool_calls_uses_distinct_lists():
    first = LLMResponse(content="one", model="test", usage={})
    second = LLMResponse(content="two", model="test", usage={})

    first.tool_calls.append({"id": "call-1"})

    assert first.tool_calls == [{"id": "call-1"}]
    assert second.tool_calls == []


def test_http_client_manager_recreates_lock_for_new_event_loop():
    HTTPClientManager.reset()
    manager = HTTPClientManager()

    class DummyAsyncClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.is_closed = False

        async def aclose(self):
            self.is_closed = True

    async def capture_lock_identity() -> tuple[int, int]:
        lock = manager._lock
        loop = asyncio.get_running_loop()
        client = await manager.get_client()
        await client.aclose()
        manager._client = None
        return id(lock), id(loop)

    with patch("clawlet.providers.base.httpx.AsyncClient", DummyAsyncClient):
        first_lock_id, first_loop_id = asyncio.run(capture_lock_identity())
        second_lock_id, second_loop_id = asyncio.run(capture_lock_identity())

    assert first_loop_id != second_loop_id
    assert first_lock_id != second_lock_id

    HTTPClientManager.reset()
