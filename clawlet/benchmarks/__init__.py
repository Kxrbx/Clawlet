"""Benchmarking utilities."""

from importlib import import_module

__all__ = [
    "BenchmarkSummary",
    "EquivalenceResult",
    "check_gates",
    "run_determinism_smokecheck",
    "run_engine_equivalence_smokecheck",
    "run_event_schema_smokecheck",
    "run_failure_taxonomy_smokecheck",
    "run_replay_reexecution_smokecheck",
    "run_local_runtime_benchmark",
    "write_report",
]

_LAZY_IMPORTS = {
    "BenchmarkSummary": ("clawlet.benchmarks.runner", "BenchmarkSummary"),
    "EquivalenceResult": ("clawlet.benchmarks.equivalence", "EquivalenceResult"),
    "check_gates": ("clawlet.benchmarks.runner", "check_gates"),
    "run_determinism_smokecheck": ("clawlet.benchmarks.determinism", "run_determinism_smokecheck"),
    "run_engine_equivalence_smokecheck": ("clawlet.benchmarks.equivalence", "run_engine_equivalence_smokecheck"),
    "run_event_schema_smokecheck": ("clawlet.benchmarks.event_schema", "run_event_schema_smokecheck"),
    "run_failure_taxonomy_smokecheck": ("clawlet.benchmarks.failure_taxonomy", "run_failure_taxonomy_smokecheck"),
    "run_replay_reexecution_smokecheck": ("clawlet.benchmarks.replay_reexecution", "run_replay_reexecution_smokecheck"),
    "run_local_runtime_benchmark": ("clawlet.benchmarks.runner", "run_local_runtime_benchmark"),
    "write_report": ("clawlet.benchmarks.runner", "write_report"),
}


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'clawlet.benchmarks' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
