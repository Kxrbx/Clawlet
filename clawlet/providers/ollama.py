"""
Ollama provider for local LLM inference.
"""

import asyncio
import json
from typing import Optional, AsyncIterator

import httpx

from clawlet.providers.base import BaseProvider, LLMResponse, get_http_client_manager
from loguru import logger


class OllamaProvider(BaseProvider):
    """
    Ollama provider for local LLM inference.
    
    Install: https://ollama.ai
    Models: ollama pull llama3.2, mistral, codellama, etc.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.2",
        timeout: float = 120.0,
    ):
        """
        Initialize Ollama provider.
        
        Args:
            base_url: Ollama API URL
            default_model: Default model to use
            timeout: Request timeout (Ollama can be slow)
        """
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"OllamaProvider initialized: {base_url}, model={default_model}")
    
    @property
    def name(self) -> str:
        return "ollama"
    
    def get_default_model(self) -> str:
        return self.default_model
    
    async def __aenter__(self) -> "OllamaProvider":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            # Use shared connection pool from HTTP client manager
            manager = get_http_client_manager()
            shared_limits = None
            if manager._client is not None:
                shared_limits = manager._client._limits
            
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=shared_limits,  # Use shared connection pool
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
        """
        Complete a chat conversation using Ollama chat API.
        
        Args:
            messages: List of message dicts with role and content
            model: Model name (e.g., "llama3.2", "mistral")
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            LLMResponse with content and metadata
        """
        model = model or self.default_model
        client = await self._get_client()
        
        # Ollama chat API format
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        try:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract response
            content = data.get("message", {}).get("content", "")
            
            # Extract usage (Ollama provides this)
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            }
            
            logger.info(f"Ollama response: {len(content)} chars from {model}")
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason="stop",
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e}")
            raise RuntimeError(f"Ollama API error: {e.response.status_code}")
        except httpx.ConnectError:
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
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
        Stream a chat completion from Ollama.
        
        Yields content chunks as they arrive.
        """
        model = model or self.default_model
        client = await self._get_client()
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    try:
                        data = json.loads(line)
                        if "message" in data:
                            content = data["message"].get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            raise
    
    async def list_models(self) -> list[str]:
        """List available models."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
            
        except Exception as e:
            logger.error(f"Error listing Ollama models: {e}")
            return []
    
    async def pull_model(self, model: str) -> bool:
        """Pull/download a model."""
        client = await self._get_client()
        
        try:
            response = await client.post(
                f"{self.base_url}/api/pull",
                json={"name": model},
            )
            response.raise_for_status()
            logger.info(f"Pulled Ollama model: {model}")
            return True
            
        except Exception as e:
            logger.error(f"Error pulling model {model}: {e}")
            return False
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
