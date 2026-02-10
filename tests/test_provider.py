"""
Tests for provider base class and responses.
"""

import pytest

from clawlet.providers.base import LLMResponse


class TestLLMResponse:
    """Test LLM response model."""
    
    def test_create_response(self):
        """Test creating an LLM response."""
        response = LLMResponse(
            content="Hello, world!",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            finish_reason="stop",
        )
        
        assert response.content == "Hello, world!"
        assert response.model == "test-model"
        assert response.usage["prompt_tokens"] == 10
        assert response.finish_reason == "stop"
    
    def test_response_without_usage(self):
        """Test response without usage info."""
        response = LLMResponse(
            content="No usage",
            model="test-model",
        )
        
        assert response.content == "No usage"
        assert response.usage is None
    
    def test_to_dict(self):
        """Test converting response to dict."""
        response = LLMResponse(
            content="Test",
            model="test-model",
            usage={"total_tokens": 42},
        )
        
        data = response.to_dict()
        
        assert data["content"] == "Test"
        assert data["model"] == "test-model"
        assert data["usage"]["total_tokens"] == 42
