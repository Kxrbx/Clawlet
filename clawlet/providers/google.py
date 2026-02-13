"""
Google provider implementation.
"""

import os
from typing import Optional, AsyncIterator, List
import httpx
from loguru import logger

from clawlet.providers.base import BaseProvider, LLMResponse


# Default models list (fallback when API is unavailable)
GOOGLE_MODELS = [
    "gemini-4-pro",
    "gemini-4-flash",
    "gemini-3-5-pro",
    "gemini-3-5-flash",
    "gemini-3-pro",
    "gemini-3-flash",
    "gemini-2-5-pro-exp",
    "gemini-2-5-flash-exp",
]

# Placeholder API key used to detect unset configuration
_API_KEY_PLACEHOLDER = "your_api_key_here"


class GoogleProvider(BaseProvider):
    """Google Generative AI provider."""
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gemini-4-pro",
        base_url: Optional[str] = None,
    ):
        """
        Initialize the Google provider.
        
        Args:
            api_key: Google API key. If not provided, reads from GOOGLE_API_KEY env var.
            default_model: Default model to use.
            base_url: Custom base URL for the API.
        """
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.environ.get("GOOGLE_API_KEY", "")
        
        # Strip whitespace/newlines from API key
        api_key = api_key.strip() if api_key else ""
        
        if not api_key or api_key == _API_KEY_PLACEHOLDER:
            raise ValueError(
                "Google API key is required. Set it via:\n"
                "  1. Environment variable: export GOOGLE_API_KEY=your_key\n"
                "  2. Or in ~/.clawlet/config.yaml under provider.google.api_key"
            )
        
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url or self.BASE_URL
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"Google provider initialized with model={default_model}")
    
    @property
    def name(self) -> str:
        return "google"
    
    def get_default_model(self) -> str:
        return self.default_model
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Content-Type": "application/json",
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
        """Complete a chat conversation using Google's Generative Language API."""
        model = model or self.default_model
        client = await self._get_client()
        
        # Convert OpenAI-style messages to Google format
        # Google uses a single content field with parts
        contents = []
        current_content = {"parts": [], "role": ""}
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Map OpenAI roles to Google roles
            google_role = "user"
            if role == "assistant":
                google_role = "model"
            elif role == "system":
                # Google doesn't have a system role, prepend to first user message
                continue
            
            # Start new content if role changes
            if current_content["role"] and current_content["role"] != google_role:
                contents.append(current_content)
                current_content = {"parts": [], "role": google_role}
            else:
                current_content["role"] = google_role
            
            current_content["parts"].append({"text": content})
        
        # Append last content
        if current_content["parts"]:
            contents.append(current_content)
        
        # Build the payload for Google's REST API
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                **kwargs.get("generation_config", {})
            },
            **kwargs
        }
        
        logger.info(f"Google request: model={model}, messages={len(messages)}")
        
        try:
            logger.debug(f"Sending request to Google API...")
            response = await client.post(f"/models/{model}:generateContent", json=payload, params={"key": self.api_key})
            logger.debug(f"Google response received: status={response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            
            # Extract content from Google's response format
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("No response from Google API")
            
            content = candidates[0]["content"]["parts"][0]["text"]
            
            # Extract usage info if available
            usage = {}
            if "usageMetadata" in data:
                usage_metadata = data["usageMetadata"]
                usage = {
                    "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
                    "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
                    "total_tokens": usage_metadata.get("totalTokenCount", 0),
                }
            
            finish_reason = candidates[0].get("finishReason", "STOP")
            # Map Google finish reasons to OpenAI-style reasons
            google_finish_to_openai = {
                "STOP": "stop",
                "MAX_TOKENS": "length",
                "SAFETY": "content_filter",
                "RECITATION": "content_filter",
                "OTHER": "stop",
            }
            finish_reason = google_finish_to_openai.get(finish_reason, "stop")
            
            logger.info(f"Google response: {len(content)} chars")
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason,
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Google HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Google error: {e}")
            raise
    
    async def stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a chat completion using Google's Generative Language API."""
        model = model or self.default_model
        client = await self._get_client()
        
        # Convert messages to Google format
        contents = []
        current_content = {"parts": [], "role": ""}
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            google_role = "user"
            if role == "assistant":
                google_role = "model"
            elif role == "system":
                continue
            
            if current_content["role"] and current_content["role"] != google_role:
                contents.append(current_content)
                current_content = {"parts": [], "role": google_role}
            else:
                current_content["role"] = google_role
            
            current_content["parts"].append({"text": content})
        
        if current_content["parts"]:
            contents.append(current_content)
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "stream": True,
                **kwargs.get("generation_config", {})
            },
            **kwargs
        }
        
        logger.debug(f"Google stream request: model={model}")
        
        try:
            async with client.stream("POST", f"/models/{model}:streamGenerateContent", json=payload, params={"key": self.api_key}) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    try:
                        import json
                        data = json.loads(line)
                        
                        # Handle Google streaming format
                        if "candidates" in data and len(data["candidates"]) > 0:
                            content_parts = data["candidates"][0]["content"]["parts"]
                            for part in content_parts:
                                if "text" in part:
                                    yield part["text"]
                                    
                    except json.JSONDecodeError:
                        continue
                            
        except Exception as e:
            logger.error(f"Google stream error: {e}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def list_models(self, force_refresh: bool = False) -> List[dict]:
        """List all available models from Google.
        
        Returns a list of model objects with id, name, and other metadata.
        """
        client = await self._get_client()
        
        try:
            response = await client.get("/models", params={"key": self.api_key})
            response.raise_for_status()
            
            data = response.json()
            models = data.get("models", [])
            
            return models
            
        except Exception as e:
            logger.error(f"Failed to list Google models: {e}")
            # Return default models as fallback
            return [{"name": f"models/{m}", "displayName": m} for m in GOOGLE_MODELS]
    
    async def get_popular_models(self, limit: int = 10) -> List[str]:
        """Get a list of popular model IDs."""
        return GOOGLE_MODELS[:limit]
