"""
Agent module - Core agent logic and loop.

Lazy-loaded: importing ``clawlet.agent`` must stay side-effect free so
``clawlet.config`` (imported by several agent submodules) never hits a
partial-initialization cycle.
"""

from importlib import import_module

__all__ = [
    "AgentLoop",
    "Identity",
    "IdentityLoader",
    "MemoryManager",
    "Workspace",
    "WorkspaceStatus",
    # v2 orchestration (Hermes-style always-delegate)
    "Orchestrator",
]

_LAZY_IMPORTS = {
    "AgentLoop": ("clawlet.agent.loop", "AgentLoop"),
    "Identity": ("clawlet.agent.identity", "Identity"),
    "IdentityLoader": ("clawlet.agent.identity", "IdentityLoader"),
    "MemoryManager": ("clawlet.agent.memory", "MemoryManager"),
    "Workspace": ("clawlet.agent.workspace", "Workspace"),
    "WorkspaceStatus": ("clawlet.agent.workspace", "WorkspaceStatus"),
    "Orchestrator": ("clawlet.agent.orchestrator", "Orchestrator"),
}


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'clawlet.agent' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
