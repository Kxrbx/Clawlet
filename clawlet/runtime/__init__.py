"""Runtime package for deterministic execution and replay."""

from importlib import import_module

__all__ = [
    "EVENT_RUN_COMPLETED",
    "EVENT_RUN_STARTED",
    "EVENT_TOOL_COMPLETED",
    "EVENT_TOOL_FAILED",
    "EVENT_PROVIDER_FAILED",
    "EVENT_STORAGE_FAILED",
    "EVENT_CHANNEL_FAILED",
    "EVENT_TOOL_REQUESTED",
    "EVENT_TOOL_STARTED",
    "RuntimeEvent",
    "RuntimeEventStore",
    "DeterministicToolRuntime",
    "RuntimePolicyEngine",
    "RecoveryManager",
    "RunCheckpoint",
    "FailureInfo",
    "classify_error_text",
    "classify_exception",
    "EVENT_REQUIRED_PAYLOAD_FIELDS",
    "validate_event_payload",
    "validate_runtime_event",
    "ReplayReport",
    "ReplayReexecutionReport",
    "ReexecutionDetail",
    "ResumeEquivalenceReport",
    "replay_run",
    "reexecute_run",
    "verify_resume_equivalence",
    "ReliabilityReport",
    "build_reliability_report",
    "ToolCallEnvelope",
    "ToolExecutionMetadata",
]

_LAZY_IMPORTS = {
    "EVENT_RUN_COMPLETED": ("clawlet.runtime.events", "EVENT_RUN_COMPLETED"),
    "EVENT_RUN_STARTED": ("clawlet.runtime.events", "EVENT_RUN_STARTED"),
    "EVENT_TOOL_COMPLETED": ("clawlet.runtime.events", "EVENT_TOOL_COMPLETED"),
    "EVENT_TOOL_FAILED": ("clawlet.runtime.events", "EVENT_TOOL_FAILED"),
    "EVENT_PROVIDER_FAILED": ("clawlet.runtime.events", "EVENT_PROVIDER_FAILED"),
    "EVENT_STORAGE_FAILED": ("clawlet.runtime.events", "EVENT_STORAGE_FAILED"),
    "EVENT_CHANNEL_FAILED": ("clawlet.runtime.events", "EVENT_CHANNEL_FAILED"),
    "EVENT_TOOL_REQUESTED": ("clawlet.runtime.events", "EVENT_TOOL_REQUESTED"),
    "EVENT_TOOL_STARTED": ("clawlet.runtime.events", "EVENT_TOOL_STARTED"),
    "RuntimeEvent": ("clawlet.runtime.events", "RuntimeEvent"),
    "RuntimeEventStore": ("clawlet.runtime.events", "RuntimeEventStore"),
    "DeterministicToolRuntime": ("clawlet.runtime.executor", "DeterministicToolRuntime"),
    "RuntimePolicyEngine": ("clawlet.runtime.policy", "RuntimePolicyEngine"),
    "RecoveryManager": ("clawlet.runtime.recovery", "RecoveryManager"),
    "RunCheckpoint": ("clawlet.runtime.recovery", "RunCheckpoint"),
    "FailureInfo": ("clawlet.runtime.failures", "FailureInfo"),
    "classify_error_text": ("clawlet.runtime.failures", "classify_error_text"),
    "classify_exception": ("clawlet.runtime.failures", "classify_exception"),
    "EVENT_REQUIRED_PAYLOAD_FIELDS": ("clawlet.runtime.schema", "EVENT_REQUIRED_PAYLOAD_FIELDS"),
    "validate_event_payload": ("clawlet.runtime.schema", "validate_event_payload"),
    "validate_runtime_event": ("clawlet.runtime.schema", "validate_runtime_event"),
    "ReplayReport": ("clawlet.runtime.replay", "ReplayReport"),
    "ReplayReexecutionReport": ("clawlet.runtime.replay", "ReplayReexecutionReport"),
    "ReexecutionDetail": ("clawlet.runtime.replay", "ReexecutionDetail"),
    "ResumeEquivalenceReport": ("clawlet.runtime.replay", "ResumeEquivalenceReport"),
    "replay_run": ("clawlet.runtime.replay", "replay_run"),
    "reexecute_run": ("clawlet.runtime.replay", "reexecute_run"),
    "verify_resume_equivalence": ("clawlet.runtime.replay", "verify_resume_equivalence"),
    "ReliabilityReport": ("clawlet.runtime.reliability", "ReliabilityReport"),
    "build_reliability_report": ("clawlet.runtime.reliability", "build_reliability_report"),
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
