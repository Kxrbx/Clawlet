"""
clawlet - A lightweight AI agent framework with identity awareness.
"""

__version__ = "0.1.0"
__author__ = "Clawlet Team"

from clawlet.agent.identity import IdentityLoader
from clawlet.agent.loop import AgentLoop
from clawlet.agent.memory import MemoryManager
from clawlet.config import Config, load_config
from clawlet.health import HealthChecker, quick_health_check
from clawlet.rate_limit import RateLimiter, RateLimit
from clawlet.exceptions import (
    ClawletError,
    ProviderError,
    ProviderConnectionError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    CircuitBreakerOpen,
    StorageError,
    ChannelError,
    ConfigError,
    AgentError,
)

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
