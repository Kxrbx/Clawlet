"""
Tests for custom exceptions.
"""

import pytest

from clawlet.exceptions import (
    ClawletError,
    ProviderError,
    ProviderConnectionError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    StorageError,
    StorageConnectionError,
    ChannelError,
    ChannelConnectionError,
    ChannelAuthError,
    ConfigError,
    ConfigValidationError,
    AgentError,
    ToolExecutionError,
    MaxIterationsError,
)


class TestProviderErrors:
    """Test provider exception classes."""
    
    def test_provider_connection_error(self):
        """Test provider connection error."""
        error = ProviderConnectionError("ollama", "http://localhost:11434")
        
        assert "Cannot connect to ollama" in str(error)
        assert error.details["provider"] == "ollama"
        assert error.details["url"] == "http://localhost:11434"
    
    def test_provider_auth_error(self):
        """Test provider auth error."""
        error = ProviderAuthError("openrouter", "Invalid API key")
        
        assert "openrouter" in str(error)
        assert "Invalid API key" in str(error)
    
    def test_provider_rate_limit_error(self):
        """Test rate limit error."""
        error = ProviderRateLimitError("openrouter", retry_after=60)
        
        assert "rate limit" in str(error).lower()
        assert error.retry_after == 60
        assert "60 seconds" in str(error)
    
    def test_provider_rate_limit_no_retry_after(self):
        """Test rate limit error without retry_after."""
        error = ProviderRateLimitError("openrouter")
        
        assert "rate limit" in str(error).lower()
        assert "Retry after" not in str(error)
    
    def test_provider_response_error(self):
        """Test provider response error."""
        error = ProviderResponseError("openrouter", 429, "Too many requests")
        
        assert "429" in str(error)
        assert "Too many requests" in str(error)


class TestStorageErrors:
    """Test storage exception classes."""
    
    def test_storage_connection_error(self):
        """Test storage connection error."""
        error = StorageConnectionError("postgres", "Connection refused")
        
        assert "Cannot connect to postgres" in str(error)
        assert "Connection refused" in str(error)


class TestChannelErrors:
    """Test channel exception classes."""
    
    def test_channel_connection_error(self):
        """Test channel connection error."""
        error = ChannelConnectionError("telegram", "Network timeout")
        
        assert "Cannot connect to telegram" in str(error)
    
    def test_channel_auth_error(self):
        """Test channel auth error."""
        error = ChannelAuthError("discord")
        
        assert "discord" in str(error)
        assert "authentication failed" in str(error).lower()


class TestConfigErrors:
    """Test config exception classes."""
    
    def test_config_validation_error(self):
        """Test config validation error."""
        error = ConfigValidationError("api_key", "cannot be empty")
        
        assert "api_key" in str(error)
        assert "cannot be empty" in str(error)


class TestAgentErrors:
    """Test agent exception classes."""
    
    def test_tool_execution_error(self):
        """Test tool execution error."""
        error = ToolExecutionError("shell", "Command not found")
        
        assert "shell" in str(error)
        assert "Command not found" in str(error)
    
    def test_max_iterations_error(self):
        """Test max iterations error."""
        error = MaxIterationsError(10)
        
        assert "10" in str(error)
        assert "maximum iterations" in str(error).lower()


class TestExceptionHierarchy:
    """Test exception inheritance."""
    
    def test_all_inherit_from_base(self):
        """Test that all exceptions inherit from ClawletError."""
        errors = [
            ProviderConnectionError("test", "url"),
            ProviderAuthError("test"),
            StorageConnectionError("test", "msg"),
            ChannelConnectionError("test", "msg"),
            ConfigValidationError("field", "msg"),
            ToolExecutionError("tool", "msg"),
        ]
        
        for error in errors:
            assert isinstance(error, ClawletError)
            assert isinstance(error, Exception)
    
    def test_can_catch_base(self):
        """Test that catching ClawletError catches all custom errors."""
        errors_to_raise = [
            ProviderConnectionError("test", "url"),
            StorageConnectionError("test", "msg"),
            ChannelConnectionError("test", "msg"),
        ]
        
        for error in errors_to_raise:
            try:
                raise error
            except ClawletError as e:
                assert e is error
