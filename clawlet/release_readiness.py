"""Consolidated release readiness orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(slots=True)
class ReleaseReadinessReport:
    workspace: str
    passed: bool
    release_gate_passed: bool
    migration_matrix_passed: bool
    plugin_matrix_passed: bool
    lane_scheduling_passed: bool
    context_cache_passed: bool
    coding_loop_passed: bool
    remote_health_passed: bool
    reasons: list[str]
    gate_breaches: list[str]
    breach_counts: dict[str, int]
    release_gate: dict[str, Any]
    migration_matrix: dict[str, Any]
    plugin_matrix: dict[str, Any]
    lane_scheduling: dict[str, Any]
    context_cache: dict[str, Any]
    coding_loop: dict[str, Any]
    remote_health: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "passed": self.passed,
            "release_gate_passed": self.release_gate_passed,
            "migration_matrix_passed": self.migration_matrix_passed,
            "plugin_matrix_passed": self.plugin_matrix_passed,
            "lane_scheduling_passed": self.lane_scheduling_passed,
            "context_cache_passed": self.context_cache_passed,
            "coding_loop_passed": self.coding_loop_passed,
            "remote_health_passed": self.remote_health_passed,
            "reasons": list(self.reasons),
            "gate_breaches": list(self.gate_breaches),
            "breach_counts": dict(self.breach_counts),
            "release_gate": dict(self.release_gate),
            "migration_matrix": dict(self.migration_matrix),
            "plugin_matrix": dict(self.plugin_matrix),
            "lane_scheduling": dict(self.lane_scheduling),
            "context_cache": dict(self.context_cache),
            "coding_loop": dict(self.coding_loop),
            "remote_health": dict(self.remote_health),
        }


def run_release_readiness(
    workspace: Path,
    *,
    benchmark_gates: Any,
    local_iterations: int = 25,
    corpus_iterations: int = 10,
    baseline_report: Path | None = None,
    target_improvement_pct: float = 35.0,
    require_comparison: bool = False,
    migration_root: Path | None = None,
    migration_pattern: str = "config.yaml",
    migration_max_workspaces: int = 200,
    plugin_dirs: Optional[list[Path]] = None,
    check_remote_health: bool = False,
    remote_endpoint: str = "",
    remote_api_key: str = "",
    remote_timeout_seconds: float = 60.0,
) -> ReleaseReadinessReport:
    from clawlet.benchmarks.release_gate import run_release_gate
    from clawlet.config_migration_matrix import run_migration_matrix
    from clawlet.plugins.matrix import run_plugin_conformance_matrix

    ws = workspace.resolve()
    reasons: list[str] = []

    rg = run_release_gate(
        workspace=ws,
        gates=benchmark_gates,
        local_iterations=local_iterations,
        corpus_iterations=corpus_iterations,
        baseline_report=baseline_report,
        target_improvement_pct=target_improvement_pct,
        require_comparison=require_comparison,
    )
    rg_dict = rg.to_dict()
    release_gate_passed = bool(rg.passed)
    if not release_gate_passed:
        reasons.extend([f"release_gate: {item}" for item in rg.reasons])

    matrix_root = (migration_root or ws).resolve()
    mm = run_migration_matrix(
        root=matrix_root,
        pattern=migration_pattern,
        max_workspaces=migration_max_workspaces,
    )
    migration_matrix_passed = mm.with_errors == 0
    if not migration_matrix_passed:
        reasons.append(
            f"migration_matrix: workspaces_with_errors={mm.with_errors} total_errors={mm.total_errors}"
        )

    pm = run_plugin_conformance_matrix(plugin_dirs or [ws / "plugins"])
    plugin_matrix_passed = bool(pm.passed)
    if not plugin_matrix_passed:
        reasons.append(
            f"plugin_matrix: directories_with_errors={pm.directories_with_errors} total_errors={pm.total_errors}"
        )

    lane_data = dict((rg_dict.get("lane_scheduling") or {}))
    lane_scheduling_passed = bool(lane_data.get("passed", False))

    context_data = dict((rg_dict.get("context_cache") or {}))
    context_cache_passed = bool(context_data.get("passed", False))

    coding_data = dict((rg_dict.get("coding_loop") or {}))
    coding_loop_passed = bool(coding_data.get("passed", False))

    remote_health_passed = True
    remote_health: dict[str, Any] = {"checked": False, "status": "skipped", "detail": ""}
    if check_remote_health:
        remote_health["checked"] = True
        if not remote_endpoint:
            remote_health_passed = False
            remote_health["status"] = "failed"
            remote_health["detail"] = "remote endpoint is empty"
            reasons.append("remote_health: remote endpoint is empty")
        else:
            try:
                from clawlet.runtime.remote import RemoteToolExecutor
                import asyncio

                client = RemoteToolExecutor(
                    endpoint=remote_endpoint,
                    api_key=remote_api_key,
                    timeout_seconds=remote_timeout_seconds,
                )
                ok, detail = asyncio.run(client.health())
                remote_health_passed = bool(ok)
                remote_health["status"] = "ok" if ok else "failed"
                remote_health["detail"] = detail
                if not ok:
                    reasons.append(f"remote_health: {detail}")
            except Exception as e:
                remote_health_passed = False
                remote_health["status"] = "failed"
                remote_health["detail"] = str(e)
                reasons.append(f"remote_health: {e}")

    passed = (
        release_gate_passed
        and migration_matrix_passed
        and plugin_matrix_passed
        and lane_scheduling_passed
        and context_cache_passed
        and coding_loop_passed
        and remote_health_passed
    )
    gate_breaches = list(rg_dict.get("gate_breaches") or [])
    if not gate_breaches:
        gate_breaches = _summarize_release_gate_reasons(list(rg_dict.get("reasons") or []), max_items=10)
    breach_counts = dict(rg_dict.get("breach_counts") or {})
    return ReleaseReadinessReport(
        workspace=str(ws),
        passed=passed,
        release_gate_passed=release_gate_passed,
        migration_matrix_passed=migration_matrix_passed,
        plugin_matrix_passed=plugin_matrix_passed,
        lane_scheduling_passed=lane_scheduling_passed,
        context_cache_passed=context_cache_passed,
        coding_loop_passed=coding_loop_passed,
        remote_health_passed=remote_health_passed,
        reasons=reasons,
        gate_breaches=gate_breaches,
        breach_counts=breach_counts,
        release_gate=rg_dict,
        migration_matrix=mm.to_dict(),
        plugin_matrix=pm.to_dict(),
        lane_scheduling=lane_data,
        context_cache=context_data,
        coding_loop=coding_data,
        remote_health=remote_health,
    )


def write_release_readiness_report(path: Path, report: ReleaseReadinessReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def summarize_gate_breaches(report: ReleaseReadinessReport, max_items: int = 10) -> list[str]:
    """Return compact release-gate breach lines grouped by subsystem."""
    gate_breaches = list((report.release_gate or {}).get("gate_breaches") or [])
    if gate_breaches:
        return gate_breaches[:max_items]
    reasons = list((report.release_gate or {}).get("reasons") or [])
    return _summarize_release_gate_reasons(reasons, max_items=max_items)


def _summarize_release_gate_reasons(reasons: list[str], max_items: int = 10) -> list[str]:
    """Return compact grouped release-gate reasons."""
    if not reasons:
        return []

    buckets = {
        "local": [],
        "corpus": [],
        "lane": [],
        "context": [],
        "coding": [],
        "comparison": [],
        "other": [],
    }
    for reason in reasons:
        text = str(reason)
        lowered = text.lower()
        if lowered.startswith("local:"):
            buckets["local"].append(text)
        elif lowered.startswith("corpus:"):
            buckets["corpus"].append(text)
        elif lowered.startswith("lane_scheduling:"):
            buckets["lane"].append(text)
        elif lowered.startswith("context_cache:"):
            buckets["context"].append(text)
        elif lowered.startswith("coding_loop:"):
            buckets["coding"].append(text)
        elif lowered.startswith("comparison:"):
            buckets["comparison"].append(text)
        else:
            buckets["other"].append(text)

    out: list[str] = []
    order = ["local", "corpus", "lane", "context", "coding", "comparison", "other"]
    labels = {
        "local": "local",
        "corpus": "corpus",
        "lane": "lane",
        "context": "context",
        "coding": "coding",
        "comparison": "comparison",
        "other": "other",
    }
    for key in order:
        for item in buckets[key]:
            out.append(f"{labels[key]}: {item}")
            if len(out) >= max_items:
                return out
    return out


def run_release_readiness_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    """Smokecheck report serialization contract for release readiness artifacts."""
    errors: list[str] = []
    out = workdir / "release-readiness-smoke.json"
    report = ReleaseReadinessReport(
        workspace=str(workdir),
        passed=True,
        release_gate_passed=True,
        migration_matrix_passed=True,
        plugin_matrix_passed=True,
        lane_scheduling_passed=True,
        context_cache_passed=True,
        coding_loop_passed=True,
        remote_health_passed=True,
        reasons=[],
        gate_breaches=[],
        breach_counts={},
        release_gate={"passed": True},
        migration_matrix={"with_errors": 0},
        plugin_matrix={"passed": True},
        lane_scheduling={"passed": True},
        context_cache={"passed": True},
        coding_loop={"passed": True},
        remote_health={"checked": False, "status": "skipped", "detail": ""},
    )
    write_release_readiness_report(out, report)
    if not out.exists():
        errors.append("report file was not created")
        return False, errors
    try:
        payload = json.loads(out.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"invalid json output: {e}")
        return False, errors

    if payload.get("passed") is not True:
        errors.append("expected passed=true")
    if payload.get("release_gate_passed") is not True:
        errors.append("expected release_gate_passed=true")
    if payload.get("migration_matrix_passed") is not True:
        errors.append("expected migration_matrix_passed=true")
    if payload.get("plugin_matrix_passed") is not True:
        errors.append("expected plugin_matrix_passed=true")
    if payload.get("lane_scheduling_passed") is not True:
        errors.append("expected lane_scheduling_passed=true")
    if payload.get("context_cache_passed") is not True:
        errors.append("expected context_cache_passed=true")
    if payload.get("coding_loop_passed") is not True:
        errors.append("expected coding_loop_passed=true")
    if payload.get("remote_health_passed") is not True:
        errors.append("expected remote_health_passed=true")
    if not isinstance(payload.get("gate_breaches"), list):
        errors.append("expected gate_breaches=list")
    if not isinstance(payload.get("breach_counts"), dict):
        errors.append("expected breach_counts=dict")

    return len(errors) == 0, errors
