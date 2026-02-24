"""
Custom exceptions for Clawlet.
"""

from typing import Any, Optional


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


# Message bus errors

class RateLimitExceeded(ClawletError):
    """Rate limit exceeded for message bus operations."""
    
    def __init__(self, message: str, retry_after: float = None):
        self.retry_after = retry_after
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, details)


# Validation errors

class ValidationError(ClawletError):
    """Validation failed for input data."""
    
    def __init__(self, field: str, message: str, is_critical: bool = True):
        """
        Initialize validation error.
        
        Args:
            field: The field that failed validation
            message: Description of the validation failure
            is_critical: If True, this is a critical error that should raise an exception.
                        If False, it's a warning that should be logged but not block execution.
        """
        self.field = field
        self.is_critical = is_critical
        super().__init__(
            f"Validation failed for '{field}': {message}",
            {"field": field, "is_critical": is_critical}
        )


# Validation helper functions

def validate_not_empty(value: Any, field_name: str, is_critical: bool = True) -> tuple[bool, str]:
    """
    Validate that a value is not empty (None or empty string).
    
    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        is_critical: Whether this is a critical validation
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        return False, f"{field_name} cannot be None"
    if isinstance(value, str) and not value.strip():
        return False, f"{field_name} cannot be empty"
    return True, ""


def validate_string_length(
    value: str, 
    field_name: str, 
    min_length: int = 0, 
    max_length: Optional[int] = None,
    is_critical: bool = True
) -> tuple[bool, str]:
    """
    Validate string length.
    
    Args:
        value: The string value to validate
        field_name: Name of the field for error messages
        min_length: Minimum allowed length
        max_length: Maximum allowed length (None for no limit)
        is_critical: Whether this is a critical validation
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        return False, f"{field_name} cannot be None"
    
    length = len(value)
    
    if length < min_length:
        return False, f"{field_name} must be at least {min_length} characters"
    
    if max_length is not None and length > max_length:
        return False, f"{field_name} must be at most {max_length} characters"
    
    return True, ""


def validate_type(value: Any, expected_type: type, field_name: str, is_critical: bool = True) -> tuple[bool, str]:
    """
    Validate that a value is of the expected type.
    
    Args:
        value: The value to validate
        expected_type: The expected type
        field_name: Name of the field for error messages
        is_critical: Whether this is a critical validation
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(value, expected_type):
        return False, f"{field_name} must be of type {expected_type.__name__}, got {type(value).__name__}"
    return True, ""


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a string to prevent injection attacks.
    
    Args:
        value: The string to sanitize
        max_length: Maximum length to truncate to (None for no limit)
        
    Returns:
        Sanitized string
    """
    if value is None:
        return ""
    
    # Remove null bytes and other control characters
    sanitized = "".join(char for char in value if ord(char) >= 32 or char in "\n\r\t")
    
    # Truncate if needed
    if max_length is not None and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.strip()
