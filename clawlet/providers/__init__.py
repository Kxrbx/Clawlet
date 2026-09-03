"""
Providers module - LLM backends.

Provider classes live in their own modules (e.g.
``clawlet.providers.openai.OpenAIProvider``); construct them via
:func:`clawlet.agent.provider_factory.build_provider`, the single
construction path shared by CLI, orchestrator and dashboard.
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
