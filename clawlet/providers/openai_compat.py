"""Shared base for OpenAI-compatible chat-completions providers.

Ten of the sixteen providers (MiniMax, Moonshot, Qwen, Z.AI, Vercel,
OpenCode Zen, Xiaomi, Synthetic, Venice, + generic) were copy-pasted
~190-line implementations differing only by ``BASE_URL``,
``default_model`` and the provider name. They now share this base class;
each subclass only declares those three attributes plus its fallback
model list.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from loguru import logger

from clawlet.providers.base import BaseProvider, LLMResponse


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI ``/chat/completions`` compatible provider with Bearer auth."""

    #: e.g. "https://api.minimax.chat/v1"
    BASE_URL: str = ""
    #: machine name used in logs / errors, e.g. "minimax"
    PROVIDER_NAME: str = "openai-compatible"
    #: env var hint shown when the key is missing, e.g. "MINIMAX_API_KEY"
    ENV_VAR_HINT: str = ""
    #: config path hint, e.g. "provider.minimax.api_key"
    CONFIG_PATH_HINT: str = ""
    #: fallback model list for list_models()
    DEFAULT_MODELS: list[str] = []
    #: default model when none is configured
    FALLBACK_MODEL: str = "default-model"

    def __init__(
        self,
        api_key: str,
        default_model: str | None = None,
        base_url: str | None = None,
    ):
        api_key = api_key.strip() if api_key else ""
        if not api_key:
            raise ValueError(
                f"{self.PROVIDER_NAME} API key is required. Set it via:\n"
                f"  1. Environment variable: export {self.ENV_VAR_HINT or 'API_KEY'}=your_key\n"
                f"  2. Or in ~/.clawlet/config.yaml under {self.CONFIG_PATH_HINT or 'provider.api_key'}"
            )
        self.api_key = api_key
        self.default_model = default_model or self.FALLBACK_MODEL
        self.base_url = base_url or self.BASE_URL
        self._client: httpx.AsyncClient | None = None
        logger.info(
            f"{self.PROVIDER_NAME} provider initialized with model={self.default_model}"
        )

    @property
    def name(self) -> str:
        return self.PROVIDER_NAME

    def get_default_model(self) -> str:
        return self.default_model

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    async def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        model = model or self.default_model
        client = await self._get_client()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        logger.info(
            f"{self.PROVIDER_NAME} request: model={model}, messages={len(messages)}"
        )
        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            finish_reason = data["choices"][0].get("finish_reason", "stop")
            logger.info(f"{self.PROVIDER_NAME} response: {len(content)} chars")
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason,
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"{self.PROVIDER_NAME} HTTP error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME} error: {e}")
            raise

    async def stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        model = model or self.default_model
        client = await self._get_client()
        self.last_stream_usage = {}
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }
        if "stream_options" not in kwargs:
            payload["stream_options"] = {"include_usage": True}
        try:
            async with client.stream(
                "POST", "/chat/completions", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json as _json

                        data = _json.loads(data_str)
                    except ValueError:
                        continue
                    usage = data.get("usage")
                    if isinstance(usage, dict):
                        self.last_stream_usage = {
                            k: usage.get(k, 0)
                            for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                        }
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    content = (choices[0].get("delta") or {}).get("content", "")
                    if content:
                        yield content
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME} stream error: {e}")
            raise

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def list_models(self, force_refresh: bool = False) -> list[dict]:
        return [{"id": m, "name": m} for m in self.DEFAULT_MODELS]

    async def get_popular_models(self, limit: int = 10) -> list[str]:
        return list(self.DEFAULT_MODELS[:limit])
