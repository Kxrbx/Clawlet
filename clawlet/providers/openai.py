"""
OpenAI provider implementation.
"""

import os
from typing import Optional, AsyncIterator, List
import httpx
from loguru import logger

from clawlet.providers.base import BaseProvider, LLMResponse


# Default models list (fallback when API is unavailable)
OPENAI_MODELS = [
    "gpt-5",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "o3",
    "o1",
    "o1-mini",
    "o3-mini",
]

# Placeholder API key used to detect unset configuration
_API_KEY_PLACEHOLDER = "your_api_key_here"


class OpenAIProvider(BaseProvider):
    """OpenAI API provider."""
    
    BASE_URL = "https://api.openai.com/v1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gpt-5",
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        use_oauth: bool = False,
    ):
        """
        Initialize the OpenAI provider.
        
        Args:
            api_key: OpenAI API key. If not provided, reads from OPENAI_API_KEY env var.
            default_model: Default model to use.
            base_url: Custom base URL for the API.
            organization: OpenAI organization ID (optional).
            use_oauth: Whether to use OAuth flow instead of API key.
        """
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY", "")
        
        # Strip whitespace/newlines from API key
        api_key = api_key.strip() if api_key else ""
        
        if not api_key or api_key == _API_KEY_PLACEHOLDER:
            raise ValueError(
                "OpenAI API key is required. Set it via:\n"
                "  1. Environment variable: export OPENAI_API_KEY=your_key\n"
                "  2. Or in ~/.clawlet/config.yaml under provider.openai.api_key"
            )
        
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url or self.BASE_URL
        self.organization = organization
        self.use_oauth = use_oauth
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"OpenAI provider initialized with model={default_model}, oauth={use_oauth}")
    
    @property
    def name(self) -> str:
        return "openai"
    
    def get_default_model(self) -> str:
        return self.default_model
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            # Add organization header if provided
            if self.organization:
                headers["OpenAI-Organization"] = self.organization
            
            # Add OAuth header if using OAuth flow
            if self.use_oauth:
                headers["OpenAI-Client"] = "clawlet"
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
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
        
        logger.info(f"OpenAI request: model={model}, messages={len(messages)}")
        
        try:
            logger.debug(f"Sending request to OpenAI API...")
            response = await client.post("/chat/completions", json=payload)
            logger.debug(f"OpenAI response received: status={response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            finish_reason = data["choices"][0].get("finish_reason", "stop")
            
            logger.info(f"OpenAI response: {len(content)} chars, {usage.get('total_tokens', 0)} tokens")
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason,
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
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
        
        logger.debug(f"OpenAI stream request: model={model}")
        
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
            logger.error(f"OpenAI stream error: {e}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def list_models(self, force_refresh: bool = False) -> List[dict]:
        """List all available models from OpenAI.
        
        Returns a list of model objects with id, name, and other metadata.
        """
        client = await self._get_client()
        
        try:
            response = await client.get("/models")
            response.raise_for_status()
            
            data = response.json()
            models = data.get("data", [])
            
            # Filter to only chat completion models
            chat_models = [
                model for model in models
                if model.get("id", "").startswith(("gpt-", "o"))
            ]
            
            return chat_models
            
        except Exception as e:
            logger.error(f"Failed to list OpenAI models: {e}")
            # Return default models as fallback
            return [{"id": m, "object": "model"} for m in OPENAI_MODELS]
    
    async def get_popular_models(self, limit: int = 10) -> List[str]:
        """Get a list of popular model IDs."""
        return OPENAI_MODELS[:limit]
