"""Benchmarking utilities (local run + matched corpus only)."""

from importlib import import_module

__all__ = [
    "BenchmarkSummary",
    "check_gates",
    "run_local_runtime_benchmark",
    "write_report",
    "check_corpus_gates",
    "compare_corpus_to_baseline",
    "format_publishable_corpus_report",
    "load_corpus_benchmark_report",
    "run_matched_corpus",
    "run_determinism_trials",
    "write_corpus_report",
    "write_publishable_corpus_report",
]

_LAZY_IMPORTS = {
    "BenchmarkSummary": ("clawlet.benchmarks.runner", "BenchmarkSummary"),
    "check_gates": ("clawlet.benchmarks.runner", "check_gates"),
    "run_local_runtime_benchmark": ("clawlet.benchmarks.runner", "run_local_runtime_benchmark"),
    "write_report": ("clawlet.benchmarks.runner", "write_report"),
    "check_corpus_gates": ("clawlet.benchmarks.corpus", "check_corpus_gates"),
    "compare_corpus_to_baseline": ("clawlet.benchmarks.corpus", "compare_corpus_to_baseline"),
    "format_publishable_corpus_report": ("clawlet.benchmarks.corpus", "format_publishable_corpus_report"),
    "load_corpus_benchmark_report": ("clawlet.benchmarks.corpus", "load_corpus_benchmark_report"),
    "run_matched_corpus": ("clawlet.benchmarks.corpus", "run_matched_corpus"),
    "run_determinism_trials": ("clawlet.benchmarks.determinism", "run_determinism_trials"),
    "write_corpus_report": ("clawlet.benchmarks.corpus", "write_corpus_report"),
    "write_publishable_corpus_report": ("clawlet.benchmarks.corpus", "write_publishable_corpus_report"),
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
