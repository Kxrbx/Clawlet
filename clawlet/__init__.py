"""
clawlet - A lightweight AI agent framework with identity awareness.
"""

__version__ = "0.1.0"
__author__ = "Clawlet Team"

from importlib import import_module

__all__ = [
    # Core
    "IdentityLoader",
    "AgentLoop", 
    "MemoryManager",
    # Config
    "Config",
    "load_config",
    # Health
    "HealthChecker",
    "quick_health_check",
    # Rate limiting
    "RateLimiter",
    "RateLimit",
    # Exceptions
    "ClawletError",
    "ProviderError",
    "ProviderConnectionError",
    "ProviderAuthError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "CircuitBreakerOpen",
    "StorageError",
    "ChannelError",
    "ConfigError",
    "AgentError",
    # Meta
    "__version__",
]


_LAZY_IMPORTS = {
    "IdentityLoader": ("clawlet.agent.identity", "IdentityLoader"),
    "AgentLoop": ("clawlet.agent.loop", "AgentLoop"),
    "MemoryManager": ("clawlet.agent.memory", "MemoryManager"),
    "Config": ("clawlet.config", "Config"),
    "load_config": ("clawlet.config", "load_config"),
    "HealthChecker": ("clawlet.health", "HealthChecker"),
    "quick_health_check": ("clawlet.health", "quick_health_check"),
    "RateLimiter": ("clawlet.rate_limit", "RateLimiter"),
    "RateLimit": ("clawlet.rate_limit", "RateLimit"),
    "ClawletError": ("clawlet.exceptions", "ClawletError"),
    "ProviderError": ("clawlet.exceptions", "ProviderError"),
    "ProviderConnectionError": ("clawlet.exceptions", "ProviderConnectionError"),
    "ProviderAuthError": ("clawlet.exceptions", "ProviderAuthError"),
    "ProviderRateLimitError": ("clawlet.exceptions", "ProviderRateLimitError"),
    "ProviderResponseError": ("clawlet.exceptions", "ProviderResponseError"),
    "CircuitBreakerOpen": ("clawlet.exceptions", "CircuitBreakerOpen"),
    "StorageError": ("clawlet.exceptions", "StorageError"),
    "ChannelError": ("clawlet.exceptions", "ChannelError"),
    "ConfigError": ("clawlet.exceptions", "ConfigError"),
    "AgentError": ("clawlet.exceptions", "AgentError"),
}


def __getattr__(name: str):
    """Lazy-load heavy modules so lightweight commands start faster."""
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'clawlet' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
