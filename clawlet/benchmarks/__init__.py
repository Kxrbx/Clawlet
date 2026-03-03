"""Benchmarking utilities."""

from importlib import import_module

__all__ = [
    "BenchmarkSummary",
    "EquivalenceResult",
    "check_gates",
    "check_corpus_gates",
    "compare_corpus_reports",
    "compare_corpus_to_baseline",
    "build_publishable_corpus_report_from_paths",
    "build_competitive_corpus_bundle",
    "format_publishable_corpus_report",
    "load_corpus_benchmark_report",
    "ReleaseGateReport",
    "run_release_gate",
    "run_release_gate_smokecheck",
    "write_release_gate_report",
    "run_determinism_smokecheck",
    "run_determinism_trials",
    "run_openclaw_matched_corpus",
    "run_corpus_compare_smokecheck",
    "run_openclaw_matched_corpus_smokecheck",
    "run_engine_equivalence_smokecheck",
    "run_event_schema_smokecheck",
    "run_failure_taxonomy_smokecheck",
    "run_replay_reexecution_smokecheck",
    "run_replay_retention_smokecheck",
    "run_remote_parity_smokecheck",
    "run_lane_contention_benchmark",
    "run_lane_contention_smokecheck",
    "write_lane_contention_report",
    "run_context_cache_benchmark",
    "run_context_cache_smokecheck",
    "write_context_cache_report",
    "run_coding_loop_benchmark",
    "run_coding_loop_smokecheck",
    "write_coding_loop_report",
    "run_local_runtime_benchmark",
    "write_report",
    "write_corpus_report",
    "write_publishable_corpus_report",
    "write_competitive_corpus_bundle",
]

_LAZY_IMPORTS = {
    "BenchmarkSummary": ("clawlet.benchmarks.runner", "BenchmarkSummary"),
    "EquivalenceResult": ("clawlet.benchmarks.equivalence", "EquivalenceResult"),
    "check_gates": ("clawlet.benchmarks.runner", "check_gates"),
    "check_corpus_gates": ("clawlet.benchmarks.corpus", "check_corpus_gates"),
    "compare_corpus_reports": ("clawlet.benchmarks.corpus", "compare_corpus_reports"),
    "compare_corpus_to_baseline": ("clawlet.benchmarks.corpus", "compare_corpus_to_baseline"),
    "build_publishable_corpus_report_from_paths": (
        "clawlet.benchmarks.corpus",
        "build_publishable_corpus_report_from_paths",
    ),
    "build_competitive_corpus_bundle": ("clawlet.benchmarks.corpus", "build_competitive_corpus_bundle"),
    "format_publishable_corpus_report": ("clawlet.benchmarks.corpus", "format_publishable_corpus_report"),
    "load_corpus_benchmark_report": ("clawlet.benchmarks.corpus", "load_corpus_benchmark_report"),
    "ReleaseGateReport": ("clawlet.benchmarks.release_gate", "ReleaseGateReport"),
    "run_release_gate": ("clawlet.benchmarks.release_gate", "run_release_gate"),
    "run_release_gate_smokecheck": ("clawlet.benchmarks.release_gate", "run_release_gate_smokecheck"),
    "write_release_gate_report": ("clawlet.benchmarks.release_gate", "write_release_gate_report"),
    "run_determinism_smokecheck": ("clawlet.benchmarks.determinism", "run_determinism_smokecheck"),
    "run_determinism_trials": ("clawlet.benchmarks.determinism", "run_determinism_trials"),
    "run_openclaw_matched_corpus": ("clawlet.benchmarks.corpus", "run_openclaw_matched_corpus"),
    "run_corpus_compare_smokecheck": ("clawlet.benchmarks.corpus", "run_corpus_compare_smokecheck"),
    "run_openclaw_matched_corpus_smokecheck": (
        "clawlet.benchmarks.corpus",
        "run_openclaw_matched_corpus_smokecheck",
    ),
    "run_engine_equivalence_smokecheck": ("clawlet.benchmarks.equivalence", "run_engine_equivalence_smokecheck"),
    "run_event_schema_smokecheck": ("clawlet.benchmarks.event_schema", "run_event_schema_smokecheck"),
    "run_failure_taxonomy_smokecheck": ("clawlet.benchmarks.failure_taxonomy", "run_failure_taxonomy_smokecheck"),
    "run_replay_reexecution_smokecheck": ("clawlet.benchmarks.replay_reexecution", "run_replay_reexecution_smokecheck"),
    "run_replay_retention_smokecheck": ("clawlet.benchmarks.replay_retention", "run_replay_retention_smokecheck"),
    "run_remote_parity_smokecheck": ("clawlet.benchmarks.remote_parity", "run_remote_parity_smokecheck"),
    "run_lane_contention_benchmark": ("clawlet.benchmarks.lanes", "run_lane_contention_benchmark"),
    "run_lane_contention_smokecheck": ("clawlet.benchmarks.lanes", "run_lane_contention_smokecheck"),
    "write_lane_contention_report": ("clawlet.benchmarks.lanes", "write_lane_contention_report"),
    "run_context_cache_benchmark": ("clawlet.benchmarks.context_cache", "run_context_cache_benchmark"),
    "run_context_cache_smokecheck": ("clawlet.benchmarks.context_cache", "run_context_cache_smokecheck"),
    "write_context_cache_report": ("clawlet.benchmarks.context_cache", "write_context_cache_report"),
    "run_coding_loop_benchmark": ("clawlet.benchmarks.coding_loop", "run_coding_loop_benchmark"),
    "run_coding_loop_smokecheck": ("clawlet.benchmarks.coding_loop", "run_coding_loop_smokecheck"),
    "write_coding_loop_report": ("clawlet.benchmarks.coding_loop", "write_coding_loop_report"),
    "run_local_runtime_benchmark": ("clawlet.benchmarks.runner", "run_local_runtime_benchmark"),
    "write_report": ("clawlet.benchmarks.runner", "write_report"),
    "write_corpus_report": ("clawlet.benchmarks.corpus", "write_corpus_report"),
    "write_publishable_corpus_report": ("clawlet.benchmarks.corpus", "write_publishable_corpus_report"),
    "write_competitive_corpus_bundle": ("clawlet.benchmarks.corpus", "write_competitive_corpus_bundle"),
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
