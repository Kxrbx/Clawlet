"""
Providers module - LLM backends.

Provider classes live in their own modules (e.g.
``clawlet.providers.openai.OpenAIProvider``); construct them via
:func:`clawlet.agent.provider_factory.build_provider`, the single
construction path shared by CLI and orchestrator.
"""

from clawlet.providers.base import (
    BaseProvider,
    HTTPClientConfig,
    HTTPClientManager,
    LLMResponse,
    get_http_client_manager,
)

__all__ = [
    "BaseProvider",
    "HTTPClientConfig",
    "HTTPClientManager",
    "LLMResponse",
    "get_http_client_manager",
]
