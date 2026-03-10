import json

import pytest

from clawlet.providers.openrouter import OpenRouterProvider


class _MockResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _MockClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.headers = {"Authorization": "Bearer test-key"}
        self.is_closed = False

    async def post(self, path: str, json: dict) -> _MockResponse:
        assert path == "/chat/completions"
        assert "messages" in json
        return _MockResponse(self.payload)


@pytest.mark.asyncio
async def test_openrouter_complete_accepts_tool_only_response():
    provider = OpenRouterProvider(api_key="test-key")
    provider._client = _MockClient(
        {
            "id": "resp_1",
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": "{\"path\":\"README.md\"}",
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"total_tokens": 42},
        }
    )

    response = await provider.complete(messages=[{"role": "user", "content": "Read README"}])

    assert response.content == ""
    assert response.finish_reason == "tool_calls"
    assert response.tool_calls[0]["function"]["name"] == "read_file"


@pytest.mark.asyncio
async def test_openrouter_complete_accepts_whitespace_only_message_content():
    provider = OpenRouterProvider(api_key="test-key")
    provider._client = _MockClient(
        {
            "id": "resp_2",
            "choices": [
                {
                    "message": {"content": "\n \n"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 7},
        }
    )

    response = await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    assert response.content == ""
    assert response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_openrouter_complete_raises_for_missing_message_shape():
    provider = OpenRouterProvider(api_key="test-key")
    provider._client = _MockClient(
        {
            "id": "resp_3",
            "choices": [{"finish_reason": "stop"}],
            "usage": {"total_tokens": 0},
        }
    )

    with pytest.raises(RuntimeError, match="missing parseable content"):
        await provider.complete(messages=[{"role": "user", "content": "Hi"}])
