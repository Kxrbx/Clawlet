"""
OpenRouter provider implementation.
"""

import asyncio
from typing import Optional, AsyncIterator, List
import httpx
from loguru import logger

from clawlet.providers.base import BaseProvider, LLMResponse
from clawlet.utils.security import mask_secrets


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "anthropic/claude-sonnet-4",
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4-turbo",
    "meta-llama/llama-3.3-70b-instruct",
]

# Placeholder API key used to detect unset configuration
_API_KEY_PLACEHOLDER = "your_api_key_here"


class OpenRouterProvider(BaseProvider):
    """OpenRouter API provider."""
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(
        self,
        api_key: str,
        default_model: str = "anthropic/claude-sonnet-4",
        base_url: Optional[str] = None,
    ):
        # Strip whitespace/newlines from API key
        api_key = api_key.strip() if api_key else ""
        
        if not api_key or api_key == _API_KEY_PLACEHOLDER:
            raise ValueError(
                "OpenRouter API key is required. Set it via:\n"
                "  1. Environment variable: export OPENROUTER_API_KEY=your_key\n"
                "  2. Or in ~/.clawlet/config.yaml under provider.openrouter.api_key"
            )
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url or self.BASE_URL
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"OpenRouter provider initialized with model={default_model}")
    
    @property
    def name(self) -> str:
        return "openrouter"
    
    def get_default_model(self) -> str:
        return self.default_model
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/Kxrbx/Clawlet",
                    "X-Title": "Clawlet",
                },
                timeout=120.0,
            )
        return self._client
    
    async def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """Complete a chat conversation."""
        model = model or self.default_model
        client = await self._get_client()
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        logger.info(f"OpenRouter request: model={model}, messages={len(messages)}")
        
        try:
            # Log headers with secrets masked
            logger.debug(f"OpenRouter request headers: {mask_secrets(str(client.headers))}")
            logger.debug(f"Sending request to OpenRouter API...")
            response = await client.post("/chat/completions", json=payload)
            logger.debug(f"OpenRouter response received: status={response.status_code}")
            response.raise_for_status()
            
            data = response.json()

            # OpenRouter can return non-standard payloads for some providers/models.
            # Handle common alternatives and return clear errors for operator diagnosis.
            if isinstance(data, dict) and "error" in data:
                error_payload = data.get("error")
                if isinstance(error_payload, dict):
                    error_message = (
                        error_payload.get("message")
                        or error_payload.get("type")
                        or str(error_payload)
                    )
                else:
                    error_message = str(error_payload)
                raise RuntimeError(f"OpenRouter API error payload: {error_message}")

            choices = data.get("choices") if isinstance(data, dict) else None
            choice0 = choices[0] if isinstance(choices, list) and choices else {}
            message = choice0.get("message") if isinstance(choice0, dict) else {}
            tool_calls_response = message.get("tool_calls") if isinstance(message, dict) else None

            content = ""
            if isinstance(message, dict):
                msg_content = message.get("content")
                if isinstance(msg_content, str):
                    content = msg_content
                elif isinstance(msg_content, list):
                    # Some providers emit structured content blocks.
                    text_parts: list[str] = []
                    for item in msg_content:
                        if isinstance(item, dict) and isinstance(item.get("text"), str):
                            text_parts.append(item["text"])
                    content = "".join(text_parts)

            if not content and isinstance(choice0, dict):
                # Legacy completion-compatible responses sometimes use `text`.
                content = choice0.get("text") or ""

            if not content and isinstance(data, dict):
                # Compatibility with response-style payloads.
                output = data.get("output")
                if isinstance(output, list):
                    text_parts: list[str] = []
                    for item in output:
                        if not isinstance(item, dict):
                            continue
                        for c in item.get("content", []) if isinstance(item.get("content"), list) else []:
                            if isinstance(c, dict) and isinstance(c.get("text"), str):
                                text_parts.append(c["text"])
                    content = "".join(text_parts)

            usage = data.get("usage", {}) if isinstance(data, dict) else {}
            finish_reason = (
                choice0.get("finish_reason", "stop")
                if isinstance(choice0, dict)
                else "stop"
            )

            if not content and not tool_calls_response:
                keys = list(data.keys()) if isinstance(data, dict) else [type(data).__name__]
                body_preview = mask_secrets(response.text)
                if len(body_preview) > 500:
                    body_preview = body_preview[:500] + "... [truncated]"
                raise RuntimeError(
                    f"OpenRouter response missing parseable content. keys={keys}, body={body_preview}"
                )
            
            logger.info(f"OpenRouter response: {len(content)} chars, {usage.get('total_tokens', 0)} tokens")
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason,
                tool_calls=tool_calls_response,
            )
            
        except httpx.HTTPStatusError as e:
            error_text = mask_secrets(e.response.text)
            if len(error_text) > 500:
                error_text = error_text[:500] + "... [truncated]"
            logger.error(f"OpenRouter HTTP error: {e.response.status_code} - {error_text}")
            raise
        except Exception as e:
            logger.error(f"OpenRouter error: {e}")
            raise
    
    async def stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a chat completion."""
        model = model or self.default_model
        client = await self._get_client()
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs
        }
        
        logger.debug(f"OpenRouter stream request: model={model}")
        
        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            import json
                            data = json.loads(data_str)
                            
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                
                                if content:
                                    yield content
                                    
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"OpenRouter stream error: {e}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def list_models(self, force_refresh: bool = False) -> List[dict]:
        """List all available models from OpenRouter.
        
        Returns a list of model objects with id, name, and other metadata.
        Results are cached and updated daily.
        """
        from clawlet.providers.models_cache import get_models_cache
        
        cache = get_models_cache()
        return await cache.get_openrouter_models(force_refresh=force_refresh)
    
    async def get_popular_models(self, limit: int = 10) -> List[str]:
        """Get a list of popular model IDs."""
        models = await self.list_models()
        
        # Define popular model patterns
        popular_patterns = [
            "anthropic/claude",
            "openai/gpt-4",
            "openai/gpt-4o",
            "meta-llama/llama",
            "google/gemini",
            "mistral/mistral",
        ]
        
        popular = []
        for model in models:
            model_id = model.get("id", "")
            if any(pattern in model_id.lower() for pattern in popular_patterns):
                popular.append(model_id)
            if len(popular) >= limit:
                break
        
        return popular if popular else DEFAULT_MODELS[:limit]
