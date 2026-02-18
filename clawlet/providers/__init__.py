"""
Providers module - LLM backends.

Available providers:
- OpenRouterProvider: OpenRouter API (multi-model)
- OllamaProvider: Local Ollama server
- LMStudioProvider: Local LM Studio (OpenAI-compatible)
- OpenAIProvider: OpenAI API (GPT models)
- AnthropicProvider: Anthropic API (Claude models)
- MiniMaxProvider: MiniMax API
- MoonshotProvider: Moonshot AI (Kimi)
- GoogleProvider: Google Gemini API
- QwenProvider: Qwen (Alibaba)
- ZAIProvider: Z.AI GLM
- CopilotProvider: GitHub Copilot
- VercelProvider: Vercel AI Gateway
- OpenCodeZenProvider: OpenCode Zen
- XiaomiProvider: Xiaomi
- SyntheticProvider: Synthetic AI
- VeniceProvider: Venice AI
"""

from clawlet.providers.base import BaseProvider, LLMResponse, HTTPClientConfig, HTTPClientManager, get_http_client_manager

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

def create_openai_provider(api_key: str, default_model: str = "gpt-5", organization: str = None):
    """Create an OpenAI provider instance."""
    from clawlet.providers.openai import OpenAIProvider
    return OpenAIProvider(api_key=api_key, default_model=default_model, organization=organization)

def create_anthropic_provider(api_key: str, default_model: str = "claude-sonnet-5-20260203"):
    """Create an Anthropic provider instance."""
    from clawlet.providers.anthropic import AnthropicProvider
    return AnthropicProvider(api_key=api_key, default_model=default_model)

def create_minimax_provider(api_key: str, default_model: str = "abab7-preview"):
    """Create a MiniMax provider instance."""
    from clawlet.providers.minimax import MiniMaxProvider
    return MiniMaxProvider(api_key=api_key, default_model=default_model)

def create_moonshot_provider(api_key: str, default_model: str = "kimi-k2.5"):
    """Create a Moonshot AI provider instance."""
    from clawlet.providers.moonshot import MoonshotProvider
    return MoonshotProvider(api_key=api_key, default_model=default_model)

def create_google_provider(api_key: str, default_model: str = "gemini-4-pro"):
    """Create a Google Gemini provider instance."""
    from clawlet.providers.google import GoogleProvider
    return GoogleProvider(api_key=api_key, default_model=default_model)

def create_qwen_provider(api_key: str, default_model: str = "qwen4"):
    """Create a Qwen provider instance."""
    from clawlet.providers.qwen import QwenProvider
    return QwenProvider(api_key=api_key, default_model=default_model)

def create_zai_provider(api_key: str, default_model: str = "glm-5"):
    """Create a Z.AI GLM provider instance."""
    from clawlet.providers.zai import ZAIProvider
    return ZAIProvider(api_key=api_key, default_model=default_model)

def create_copilot_provider(access_token: str, default_model: str = "gpt-4.2"):
    """Create a GitHub Copilot provider instance."""
    from clawlet.providers.copilot import CopilotProvider
    return CopilotProvider(access_token=access_token, default_model=default_model)

def create_vercel_provider(api_key: str, default_model: str = "openai/gpt-5"):
    """Create a Vercel AI Gateway provider instance."""
    from clawlet.providers.vercel import VercelProvider
    return VercelProvider(api_key=api_key, default_model=default_model)

def create_opencode_zen_provider(api_key: str, default_model: str = "zen-3.0"):
    """Create an OpenCode Zen provider instance."""
    from clawlet.providers.opencode_zen import OpenCodeZenProvider
    return OpenCodeZenProvider(api_key=api_key, default_model=default_model)

def create_xiaomi_provider(api_key: str, default_model: str = "mi-agent-2"):
    """Create a Xiaomi provider instance."""
    from clawlet.providers.xiaomi import XiaomiProvider
    return XiaomiProvider(api_key=api_key, default_model=default_model)

def create_synthetic_provider(api_key: str, default_model: str = "synthetic-llm-2"):
    """Create a Synthetic AI provider instance."""
    from clawlet.providers.synthetic import SyntheticProvider
    return SyntheticProvider(api_key=api_key, default_model=default_model)

def create_venice_provider(api_key: str, default_model: str = "venice-llama-4"):
    """Create a Venice AI provider instance."""
    from clawlet.providers.venice import VeniceProvider
    return VeniceProvider(api_key=api_key, default_model=default_model)

__all__ = [
    "BaseProvider",
    "LLMResponse",
    "HTTPClientConfig",
    "HTTPClientManager",
    "get_http_client_manager",
    "create_openrouter_provider",
    "create_ollama_provider",
    "create_lmstudio_provider",
    "create_openai_provider",
    "create_anthropic_provider",
    "create_minimax_provider",
    "create_moonshot_provider",
    "create_google_provider",
    "create_qwen_provider",
    "create_zai_provider",
    "create_copilot_provider",
    "create_vercel_provider",
    "create_opencode_zen_provider",
    "create_xiaomi_provider",
    "create_synthetic_provider",
    "create_venice_provider",
]
