"""
Provider interfaces and implementations for LLM backends.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator, Dict, Any
from dataclasses import dataclass, field
import httpx
from loguru import logger


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    usage: dict
    finish_reason: str = "stop"
    tool_calls: list = None  # List of tool calls from the model


@dataclass
class HTTPClientConfig:
    """Configuration for the shared HTTP client."""
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 30.0
    timeout: float = 120.0
    default_headers: Dict[str, str] = field(default_factory=dict)


class HTTPClientManager:
    """
    Shared HTTP client manager with connection pooling.
    
    This singleton manager maintains a single httpx.AsyncClient instance
    that is reused across all providers for better connection reuse and
    reduced overhead.
    """
    
    _instance: Optional["HTTPClientManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()
    
    def __new__(cls, config: Optional[HTTPClientConfig] = None) -> "HTTPClientManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config: Optional[HTTPClientConfig] = None):
        if self._initialized:
            return
        
        self._config = config or HTTPClientConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = True
        logger.debug(
            f"HTTPClientManager initialized: max_connections={self._config.max_connections}, "
            f"max_keepalive={self._config.max_keepalive_connections}"
        )
    
    @property
    def config(self) -> HTTPClientConfig:
        """Get the client configuration."""
        return self._config
    
    async def get_client(self) -> httpx.AsyncClient:
        """
        Get or create the shared HTTP client.
        
        The client is created lazily on first use and reused for all
        subsequent requests.
        """
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_connections=self._config.max_connections,
                max_keepalive_connections=self._config.max_keepalive_connections,
                keepalive_expiry=self._config.keepalive_expiry,
            )
            
            timeout = httpx.Timeout(
                connect=30.0,
                read=self._config.timeout,
                write=30.0,
                pool=60.0,
            )
            
            self._client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                headers=dict(self._config.default_headers),
                http2=True,  # Enable HTTP/2 for better multiplexing
            )
            logger.debug("Shared HTTP client created with connection pooling")
        
        return self._client
    
    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.debug("Shared HTTP client closed")
    
    @classmethod
    async def shutdown(cls) -> None:
        """Shutdown the manager and close the client."""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None
            logger.info("HTTPClientManager shutdown complete")
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None


def get_http_client_manager(
    config: Optional[HTTPClientConfig] = None
) -> HTTPClientManager:
    """Get the global HTTP client manager instance."""
    return HTTPClientManager(config)


class BaseProvider(ABC):
    """Base class for LLM providers."""
    
    def __init__(self):
        self._http_manager: Optional[HTTPClientManager] = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """Complete a chat conversation."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a chat completion."""
        pass
    
    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        pass
    
    async def close(self) -> None:
        """
        Close the provider and release resources.
        
        Override this method in subclasses to implement provider-specific
        cleanup. The base implementation closes the HTTP manager if this
        provider owns it.
        """
        pass
    
    def _get_http_client(
        self,
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.AsyncClient:
        """
        Get a scoped HTTP client for this provider.
        
        This creates a client that uses the shared connection pool but
        has its own base URL and headers.
        
        Args:
            base_url: Base URL for requests (None for relative URLs)
            headers: Additional headers to merge with defaults
            
        Returns:
            An httpx.AsyncClient configured for this provider
        """
        manager = get_http_client_manager()
        
        # Get limits from the shared client if it exists
        limits = None
        if manager._client is not None:
            limits = manager._client._limits
        
        client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            limits=limits,
            timeout=httpx.Timeout(120.0),
            http2=True,
        )
        return client
