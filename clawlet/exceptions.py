"""
Custom exceptions for Clawlet.
"""

from typing import Optional


class ClawletError(Exception):
    """Base exception for all Clawlet errors."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# Provider errors

class ProviderError(ClawletError):
    """Base error for provider issues."""
    pass


class ProviderConnectionError(ProviderError):
    """Cannot connect to provider."""
    
    def __init__(self, provider: str, url: str, details: Optional[dict] = None):
        super().__init__(
            f"Cannot connect to {provider} at {url}. Is the service running?",
            {"provider": provider, "url": url, **(details or {})}
        )


class ProviderAuthError(ProviderError):
    """Authentication failed with provider."""
    
    def __init__(self, provider: str, message: str = "Authentication failed"):
        super().__init__(
            f"{provider}: {message}. Check your API key.",
            {"provider": provider}
        )


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded."""
    
    def __init__(self, provider: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = f"{provider} rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds."
        super().__init__(message, {"provider": provider, "retry_after": retry_after})


class ProviderResponseError(ProviderError):
    """Invalid response from provider."""
    
    def __init__(self, provider: str, status_code: int, message: str):
        super().__init__(
            f"{provider} returned error {status_code}: {message}",
            {"provider": provider, "status_code": status_code}
        )


# Storage errors

class StorageError(ClawletError):
    """Base error for storage issues."""
    pass


class StorageConnectionError(StorageError):
    """Cannot connect to storage backend."""
    
    def __init__(self, backend: str, message: str):
        super().__init__(
            f"Cannot connect to {backend}: {message}",
            {"backend": backend}
        )


class StorageQueryError(StorageError):
    """Query execution failed."""
    
    def __init__(self, query: str, error: str):
        super().__init__(
            f"Query failed: {error}",
            {"query": query[:100]}  # Truncate for safety
        )


# Channel errors

class ChannelError(ClawletError):
    """Base error for channel issues."""
    pass


class ChannelConnectionError(ChannelError):
    """Cannot connect to channel."""
    
    def __init__(self, channel: str, message: str):
        super().__init__(
            f"Cannot connect to {channel}: {message}",
            {"channel": channel}
        )


class ChannelAuthError(ChannelError):
    """Channel authentication failed."""
    
    def __init__(self, channel: str):
        super().__init__(
            f"{channel} authentication failed. Check your token.",
            {"channel": channel}
        )


# Config errors

class ConfigError(ClawletError):
    """Configuration error."""
    pass


class ConfigValidationError(ConfigError):
    """Config validation failed."""
    
    def __init__(self, field: str, message: str):
        super().__init__(
            f"Config validation failed for '{field}': {message}",
            {"field": field}
        )


# Agent errors

class AgentError(ClawletError):
    """Base error for agent issues."""
    pass


class AgentLoopError(AgentError):
    """Agent loop execution failed."""
    
    def __init__(self, message: str, iteration: Optional[int] = None):
        super().__init__(
            message,
            {"iteration": iteration}
        )


class ToolExecutionError(AgentError):
    """Tool execution failed."""
    
    def __init__(self, tool_name: str, error: str):
        super().__init__(
            f"Tool '{tool_name}' failed: {error}",
            {"tool": tool_name}
        )


class MaxIterationsError(AgentError):
    """Maximum iterations exceeded."""
    
    def __init__(self, max_iterations: int):
        super().__init__(
            f"Agent exceeded maximum iterations ({max_iterations})",
            {"max_iterations": max_iterations}
        )


# Circuit breaker errors

class CircuitBreakerOpen(ClawletError):
    """Circuit breaker is open, requests are blocked."""
    
    def __init__(self, message: str, retry_after: float = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, details)
