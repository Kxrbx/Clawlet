"""
OpenRouter provider implementation.
"""

import asyncio
from typing import Optional, AsyncIterator, List
import httpx
from loguru import logger

from clawlet.providers.base import BaseProvider, LLMResponse


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
            logger.debug(f"Sending request to OpenRouter API...")
            response = await client.post("/chat/completions", json=payload)
            logger.debug(f"OpenRouter response received: status={response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            finish_reason = data["choices"][0].get("finish_reason", "stop")
            
            logger.info(f"OpenRouter response: {len(content)} chars, {usage.get('total_tokens', 0)} tokens")
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason,
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP error: {e.response.status_code} - {e.response.text}")
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
