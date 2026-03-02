"""Context engine cache benchmark and smokechecks."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from clawlet.context import ContextEngine


@dataclass(slots=True)
class ContextCacheBenchmarkReport:
    passed: bool
    cold_ms: float
    warm_ms: float
    speedup_ratio: float
    details: list[str]


def run_context_cache_benchmark(workspace: Path) -> ContextCacheBenchmarkReport:
    scenario_workspace = workspace / ".clawlet-bench-context"
    _ensure_context_fixture(scenario_workspace)
    engine = ContextEngine(
        workspace=scenario_workspace,
        cache_dir=workspace / ".clawlet-bench-context-cache",
    )
    query = "deterministic runtime replay lane scheduler policy"

    t0 = time.perf_counter()
    first = engine.get_pack(query=query, max_files=5, char_budget=2800)
    cold_ms = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    second = engine.get_pack(query=query, max_files=5, char_budget=2800)
    warm_ms = (time.perf_counter() - t1) * 1000.0

    details: list[str] = []
    if second.cache_hit is not True:
        details.append("warm lookup did not return cache_hit=true")
    if warm_ms > cold_ms * 1.5:
        details.append(
            f"warm lookup not sufficiently faster (cold={cold_ms:.1f}ms warm={warm_ms:.1f}ms)"
        )
    if not first.snippets and not second.snippets:
        details.append("no snippets were retrieved for context benchmark query")

    ratio = cold_ms / max(1.0, warm_ms)
    return ContextCacheBenchmarkReport(
        passed=len(details) == 0,
        cold_ms=cold_ms,
        warm_ms=warm_ms,
        speedup_ratio=ratio,
        details=details,
    )


def run_context_cache_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    report = run_context_cache_benchmark(workdir)
    return report.passed, list(report.details)


def write_context_cache_report(path: Path, report: ContextCacheBenchmarkReport) -> None:
    import json

    payload = {"report": asdict(report)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _ensure_context_fixture(workspace: Path) -> None:
    fixture_dir = workspace / "context-benchmark-fixture"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "runtime_notes.md": (
            "Deterministic runtime replay details.\n"
            "Tool lane scheduler controls parallel and serial execution.\n"
            "Policy defaults map read_only to parallel and writes to serial.\n"
        ),
        "tools.py": (
            "class LaneScheduler:\n"
            "    def plan(self):\n"
            "        return 'parallel:read_only'\n"
        ),
        "README.md": "Context cache benchmark fixture for Clawlet.\n",
    }
    for i in range(30):
        files[f"module_{i}.py"] = (
            "def deterministic_runtime_replay_lane_scheduler_policy():\n"
            f"    return 'module-{i}'\n"
        )
    for rel, content in files.items():
        target = fixture_dir / rel
        if not target.exists():
            target.write_text(content, encoding="utf-8")
