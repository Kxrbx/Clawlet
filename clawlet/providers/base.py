"""
Provider interfaces and implementations for LLM backends.
"""

from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    usage: dict
    finish_reason: str = "stop"


class BaseProvider(ABC):
    """Base class for LLM providers."""
    
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
