"""
LM Studio provider for local LLM inference.
"""

import asyncio
import json
from typing import Optional, AsyncIterator

import httpx

from clawlet.providers.base import BaseProvider, LLMResponse
from loguru import logger


class LMStudioProvider(BaseProvider):
    """
    LM Studio provider for local LLM inference.
    
    LM Studio provides an OpenAI-compatible API for local models.
    Install: https://lmstudio.ai
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:1234",
        default_model: str = "local-model",
        timeout: float = 120.0,
    ):
        """
        Initialize LM Studio provider.
        
        Args:
            base_url: LM Studio API URL (default: localhost:1234)
            default_model: Model name (LM Studio ignores this, uses loaded model)
            timeout: Request timeout
        """
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"LMStudioProvider initialized: {base_url}")
    
    @property
    def name(self) -> str:
        return "lmstudio"
    
    def get_default_model(self) -> str:
        return self.default_model
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """
        Complete a chat conversation using LM Studio's OpenAI-compatible API.
        
        Args:
            messages: List of message dicts with role and content
            model: Model name (LM Studio uses whatever is loaded)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            LLMResponse with content and metadata
        """
        model = model or self.default_model
        client = await self._get_client()
        
        # OpenAI-compatible format
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        
        try:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # OpenAI response format
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            
            usage = data.get("usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            })
            
            logger.info(f"LM Studio response: {len(content)} chars")
            
            return LLMResponse(
                content=content,
                model=data.get("model", model),
                usage=usage,
                finish_reason=choice.get("finish_reason", "stop"),
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"LM Studio HTTP error: {e}")
            raise RuntimeError(f"LM Studio API error: {e.response.status_code}")
        except httpx.ConnectError:
            raise RuntimeError(f"Cannot connect to LM Studio at {self.base_url}. Is LM Studio running with the server enabled?")
        except Exception as e:
            logger.error(f"LM Studio error: {e}")
            raise
    
    async def stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream a chat completion from LM Studio.
        
        Yields content chunks as they arrive.
        """
        model = model or self.default_model
        client = await self._get_client()
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data: "):
                        continue
                    
                    data_str = line[6:]  # Remove "data: " prefix
                    
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"LM Studio streaming error: {e}")
            raise
    
    async def list_models(self) -> list[str]:
        """List available models (returns loaded model info)."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/v1/models")
            response.raise_for_status()
            
            data = response.json()
            return [model["id"] for model in data.get("data", [])]
            
        except Exception as e:
            logger.error(f"Error listing LM Studio models: {e}")
            return []
    
    async def get_loaded_model(self) -> Optional[str]:
        """Get the currently loaded model."""
        models = await self.list_models()
        return models[0] if models else None
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
