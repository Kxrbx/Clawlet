"""
clawlet - A lightweight AI agent framework with identity awareness.
"""

__version__ = "0.1.0"
__author__ = "Clawlet Team"

from clawlet.agent.identity import IdentityLoader
from clawlet.agent.loop import AgentLoop
from clawlet.agent.memory import MemoryManager

__all__ = [
    "IdentityLoader",
    "AgentLoop", 
    "MemoryManager",
    "__version__",
]
