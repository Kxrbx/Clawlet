"""
Anthropic provider implementation.
"""

import os
from typing import Optional, AsyncIterator, List
import httpx
from loguru import logger

from clawlet.providers.base import BaseProvider, LLMResponse


# Default models list (fallback when API is unavailable)
ANTHROPIC_MODELS = [
    "claude-sonnet-5-20260203",
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-20250519",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
]

# Placeholder API key used to detect unset configuration
_API_KEY_PLACEHOLDER = "your_api_key_here"

# Default Anthropic API version
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseProvider):
    """Anthropic API provider."""
    
    BASE_URL = "https://api.anthropic.com/v1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "claude-sonnet-5-20260203",
        base_url: Optional[str] = None,
        api_version: str = ANTHROPIC_VERSION,
    ):
        """
        Initialize the Anthropic provider.
        
        Args:
            api_key: Anthropic API key. If not provided, reads from ANTHROPIC_API_KEY env var.
            default_model: Default model to use.
            base_url: Custom base URL for the API.
            api_version: Anthropic API version header.
        """
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        
        # Strip whitespace/newlines from API key
        api_key = api_key.strip() if api_key else ""
        
        if not api_key or api_key == _API_KEY_PLACEHOLDER:
            raise ValueError(
                "Anthropic API key is required. Set it via:\n"
                "  1. Environment variable: export ANTHROPIC_API_KEY=your_key\n"
                "  2. Or in ~/.clawlet/config.yaml under provider.anthropic.api_key"
            )
        
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url or self.BASE_URL
        self.api_version = api_version
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"Anthropic provider initialized with model={default_model}")
    
    @property
    def name(self) -> str:
        return "anthropic"
    
    def get_default_model(self) -> str:
        return self.default_model
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": self.api_version,
                    "anthropic-client": "clawlet",
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
        """Complete a chat conversation using Anthropic's Messages API."""
        model = model or self.default_model
        client = await self._get_client()
        
        # Anthropic uses a different message format
        # Convert OpenAI-style messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Anthropic only supports 'user' and 'assistant' roles
            if role in ("user", "assistant"):
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })
        
        payload = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        logger.info(f"Anthropic request: model={model}, messages={len(messages)}")
        
        try:
            logger.debug(f"Sending request to Anthropic API...")
            response = await client.post("/messages", json=payload)
            logger.debug(f"Anthropic response received: status={response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            
            content = data["content"][0]["text"]
            usage = data.get("usage", {})
            stop_reason = data.get("stop_reason", "end_turn")
            
            # Map Anthropic stop reasons to OpenAI-style reasons
            finish_reason = "stop"
            if stop_reason == "max_tokens":
                finish_reason = "length"
            
            logger.info(f"Anthropic response: {len(content)} chars")
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason,
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Anthropic HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Anthropic error: {e}")
            raise
    
    async def stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a chat completion using Anthropic's Messages API."""
        model = model or self.default_model
        client = await self._get_client()
        
        # Convert messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role in ("user", "assistant"):
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })
        
        payload = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs
        }
        
        logger.debug(f"Anthropic stream request: model={model}")
        
        try:
            async with client.stream("POST", "/messages", json=payload) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            import json
                            data = json.loads(data_str)
                            
                            # Handle Anthropic streaming format
                            if "type" in data:
                                if data["type"] == "content_block_delta":
                                    delta = data.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        content = delta.get("text", "")
                                        if content:
                                            yield content
                                            
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Anthropic stream error: {e}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def list_models(self, force_refresh: bool = False) -> List[dict]:
        """List all available models from Anthropic.
        
        Returns a list of model objects with id, name, and other metadata.
        """
        # Anthropic doesn't have a public models list API
        # Return known models as fallback
        return [{"id": m, "object": "model"} for m in ANTHROPIC_MODELS]
    
    async def get_popular_models(self, limit: int = 10) -> List[str]:
        """Get a list of popular model IDs."""
        return ANTHROPIC_MODELS[:limit]
