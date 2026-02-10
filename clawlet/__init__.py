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

__all__ = [
    "IdentityLoader",
    "AgentLoop", 
    "MemoryManager",
    "Config",
    "load_config",
    "HealthChecker",
    "quick_health_check",
    "RateLimiter",
    "RateLimit",
    "__version__",
]
