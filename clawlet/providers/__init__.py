"""
Providers module - LLM backends.

Available providers:
- OpenRouterProvider: OpenRouter API (multi-model)
- OllamaProvider: Local Ollama server
- LMStudioProvider: Local LM Studio (OpenAI-compatible)
"""

from clawlet.providers.base import BaseProvider, LLMResponse

# Lazy imports to avoid dependency issues
def get_openrouter():
    from clawlet.providers.openrouter import OpenRouterProvider
    return OpenRouterProvider

def get_ollama():
    from clawlet.providers.ollama import OllamaProvider
    return OllamaProvider

def get_lmstudio():
    from clawlet.providers.lmstudio import LMStudioProvider
    return LMStudioProvider

__all__ = [
    "BaseProvider",
    "LLMResponse",
    "get_openrouter",
    "get_ollama",
    "get_lmstudio",
]
