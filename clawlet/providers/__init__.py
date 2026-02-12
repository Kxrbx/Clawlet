"""
Providers module - LLM backends.

Available providers:
- OpenRouterProvider: OpenRouter API (multi-model)
- OllamaProvider: Local Ollama server
- LMStudioProvider: Local LM Studio (OpenAI-compatible)
"""

from clawlet.providers.base import BaseProvider, LLMResponse

# Factory functions for lazy loading
def create_openrouter_provider(api_key: str, default_model: str = "anthropic/claude-sonnet-4"):
    """Create an OpenRouter provider instance."""
    from clawlet.providers.openrouter import OpenRouterProvider
    return OpenRouterProvider(api_key=api_key, default_model=default_model)

def create_ollama_provider(base_url: str = "http://localhost:11434", default_model: str = "llama3.2"):
    """Create an Ollama provider instance."""
    from clawlet.providers.ollama import OllamaProvider
    return OllamaProvider(base_url=base_url, default_model=default_model)

def create_lmstudio_provider(base_url: str = "http://localhost:1234", default_model: str = "local-model"):
    """Create an LM Studio provider instance."""
    from clawlet.providers.lmstudio import LMStudioProvider
    return LMStudioProvider(base_url=base_url, default_model=default_model)

__all__ = [
    "BaseProvider",
    "LLMResponse",
    "create_openrouter_provider",
    "create_ollama_provider",
    "create_lmstudio_provider",
]
