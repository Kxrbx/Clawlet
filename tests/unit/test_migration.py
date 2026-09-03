"""Tests for the v1 -> v2 migration helper (offline, tmp workspaces)."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from migrate_v1_to_v2 import analyze, fix_file


def _write(path: Path, payload: dict) -> Path:
    path.write_text(yaml.dump(payload), encoding="utf-8")
    return path


def test_reports_hybrid_rust_and_missing_sections(tmp_path):
    cfg = _write(
        tmp_path / "config.yaml",
        {
            "provider": {"primary": "ollama"},
            "runtime": {"engine": "hybrid_rust"},
        },
    )
    issues = analyze(cfg)
    assert any("hybrid_rust" in i for i in issues)
    assert any("orchestrator" in i for i in issues)
    assert any("task_profiles" in i for i in issues)


def test_write_fixes_engine_and_validates(tmp_path):
    cfg = _write(
        tmp_path / "config.yaml",
        {
            "provider": {"primary": "ollama"},
            "runtime": {"engine": "hybrid_rust"},
        },
    )
    assert fix_file(cfg)
    assert (tmp_path / "config.yaml.bak").exists()
    remaining = analyze(cfg)
    assert not any("hybrid_rust" in i for i in remaining)
    assert not any("fails v2" in i for i in remaining)
    assert not fix_file(cfg)  # idempotent


def test_clean_v2_config_has_no_actionable_issues(tmp_path):
    cfg = _write(
        tmp_path / "config.yaml",
        {
            "provider": {"primary": "ollama"},
            "runtime": {"engine": "python"},
            "orchestrator": {"max_iterations": 5},
            "task_profiles": {"code": {"provider": "ollama", "model": "llama3.2"}},
        },
    )
    issues = analyze(cfg)
    assert not any("hybrid_rust" in i for i in issues)
    assert not any("fails v2" in i for i in issues)
