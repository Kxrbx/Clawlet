"""Runtime package for deterministic execution and replay."""

from importlib import import_module

__all__ = [
    "EVENT_RUN_COMPLETED",
    "EVENT_RUN_STARTED",
    "EVENT_TOOL_COMPLETED",
    "EVENT_TOOL_FAILED",
    "EVENT_TOOL_REQUESTED",
    "EVENT_TOOL_STARTED",
    "RuntimeEvent",
    "RuntimeEventStore",
    "DeterministicToolRuntime",
    "RuntimePolicyEngine",
    "ToolCallEnvelope",
    "ToolExecutionMetadata",
]

_LAZY_IMPORTS = {
    "EVENT_RUN_COMPLETED": ("clawlet.runtime.events", "EVENT_RUN_COMPLETED"),
    "EVENT_RUN_STARTED": ("clawlet.runtime.events", "EVENT_RUN_STARTED"),
    "EVENT_TOOL_COMPLETED": ("clawlet.runtime.events", "EVENT_TOOL_COMPLETED"),
    "EVENT_TOOL_FAILED": ("clawlet.runtime.events", "EVENT_TOOL_FAILED"),
    "EVENT_TOOL_REQUESTED": ("clawlet.runtime.events", "EVENT_TOOL_REQUESTED"),
    "EVENT_TOOL_STARTED": ("clawlet.runtime.events", "EVENT_TOOL_STARTED"),
    "RuntimeEvent": ("clawlet.runtime.events", "RuntimeEvent"),
    "RuntimeEventStore": ("clawlet.runtime.events", "RuntimeEventStore"),
    "DeterministicToolRuntime": ("clawlet.runtime.executor", "DeterministicToolRuntime"),
    "RuntimePolicyEngine": ("clawlet.runtime.policy", "RuntimePolicyEngine"),
    "ToolCallEnvelope": ("clawlet.runtime.types", "ToolCallEnvelope"),
    "ToolExecutionMetadata": ("clawlet.runtime.types", "ToolExecutionMetadata"),
}


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'clawlet.runtime' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
