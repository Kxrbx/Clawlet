"""
Tests for configuration management.
"""

def test_config_loads_from_yaml(temp_workspace):
    from clawlet.config import Config, SQLiteConfig, ProviderConfig, OpenRouterConfig, StorageConfig
    
    config_path = temp_workspace / "config.yaml"
    config_content = """
provider:
  primary: openrouter
  openrouter:
    api_key: test-key-123
    model: test-model
storage:
  backend: sqlite
  sqlite:
    path: ~/.clawlet/test.db
agent:
  max_iterations: 5
"""
    config_path.write_text(config_content)
    
    config = Config.from_yaml(config_path)
    
    assert config.provider.primary == "openrouter"
    assert config.provider.openrouter.api_key == "test-key-123"
    assert config.provider.openrouter.model == "test-model"
    assert config.storage.backend == "sqlite"
    assert config.storage.sqlite.path == "~/.clawlet/test.db"
    assert config.agent.max_iterations == 5


def test_config_env_substitution(temp_workspace, monkeypatch):
    from clawlet.config import Config
    
    monkeypatch.setenv("MY_API_KEY", "env-key-456")
    
    config_path = temp_workspace / "config.yaml"
    config_content = """
provider:
  primary: openrouter
  openrouter:
    api_key: ${MY_API_KEY}
    model: ${MODEL_NAME:-default-model}
"""
    config_path.write_text(config_content)
    
    config = Config.from_yaml(config_path)
    
    assert config.provider.openrouter.api_key == "env-key-456"
    assert config.provider.openrouter.model == "default-model"  # since MODEL_NAME not set


def test_config_reload(temp_workspace):
    from clawlet.config import Config, SQLiteConfig, ProviderConfig, OpenRouterConfig, StorageConfig
    
    config_path = temp_workspace / "config.yaml"
    config_content = """
provider:
  primary: openrouter
  openrouter:
    api_key: key-v1
    model: model-v1
agent:
  max_iterations: 10
"""
    config_path.write_text(config_content)
    
    config = Config.from_yaml(config_path)
    config.config_path = config_path
    
    # Change file
    new_content = """
provider:
  primary: openrouter
  openrouter:
    api_key: key-v2
    model: model-v2
agent:
  max_iterations: 20
"""
    config_path.write_text(new_content)
    
    config.reload()
    
    assert config.provider.openrouter.api_key == "key-v2"
    assert config.agent.max_iterations == 20


def test_agent_mode_defaults_and_override(temp_workspace):
    from clawlet.config import Config

    # Build a minimal valid config file for explicit mode assertion
    config_path = temp_workspace / "config.yaml"
    config_path.write_text(
        """
provider:
  primary: openrouter
  openrouter:
    api_key: test-key-123
agent:
  mode: full_exec
  shell_allow_dangerous: true
"""
    )

    cfg = Config.from_yaml(config_path)
    assert cfg.agent.mode == "full_exec"
    assert cfg.agent.shell_allow_dangerous is True


def test_full_exec_mode_expands_tool_scope(temp_workspace):
    from clawlet.config import Config
    from clawlet.tools import create_default_tool_registry

    config_path = temp_workspace / "config.yaml"
    config_path.write_text(
        """
provider:
  primary: openrouter
  openrouter:
    api_key: test-key-123
agent:
  mode: full_exec
  shell_allow_dangerous: false
"""
    )

    cfg = Config.from_yaml(config_path)
    registry = create_default_tool_registry(allowed_dir=str(temp_workspace), config=cfg)

    read_tool = registry.get("read_file")
    shell_tool = registry.get("shell")

    assert read_tool is not None
    assert shell_tool is not None
    assert getattr(read_tool, "allowed_dir", "sentinel") is None
    assert "mkdir" in shell_tool.get_allowed()


def test_init_config_template_is_valid_yaml_and_includes_agent_mode():
    import yaml
    from clawlet.cli import get_config_template

    data = yaml.safe_load(get_config_template())

    assert data["agent"]["mode"] == "safe"
    assert data["agent"]["shell_allow_dangerous"] is False
    assert "channels" in data
    assert "telegram" in data["channels"]
    assert "discord" in data["channels"]
    assert data["runtime"]["engine"] == "hybrid_rust"
    assert data["runtime"]["enable_parallel_read_batches"] is True
    assert data["runtime"]["max_parallel_read_tools"] == 4
    assert data["runtime"]["remote"]["enabled"] is False
    assert data["runtime"]["policy"]["lanes"]["read_only"] == "parallel:read_only"
    assert data["runtime"]["policy"]["lanes"]["workspace_write"] == "serial:workspace_write"
    assert data["benchmarks"]["gates"]["min_deterministic_replay_pass_rate_pct"] == 98.0
    assert data["benchmarks"]["gates"]["min_lane_speedup_ratio"] == 1.20
    assert data["benchmarks"]["gates"]["max_lane_parallel_elapsed_ms"] == 1000
    assert data["benchmarks"]["gates"]["min_context_cache_speedup_ratio"] == 1.05
    assert data["benchmarks"]["gates"]["max_context_cache_warm_ms"] == 1200
    assert data["benchmarks"]["gates"]["min_coding_loop_success_rate_pct"] == 99.0
    assert data["benchmarks"]["gates"]["max_coding_loop_p95_total_ms"] == 2500
    assert data["benchmarks"]["gates"]["require_rust_equivalence"] is False
    assert data["plugins"]["sdk_version"] == "2.0.0"


def test_agent_loop_module_imports_on_python_310_compat_path():
    """Guard against reintroducing datetime.UTC import incompatibility."""
    import importlib
    module = importlib.import_module("clawlet.agent.loop")
    assert hasattr(module, "UTC_TZ")


def test_runtime_engine_controls_tool_rust_paths(temp_workspace, monkeypatch):
    from clawlet.config import Config
    from clawlet.tools import create_default_tool_registry

    config_path = temp_workspace / "config.yaml"
    config_path.write_text(
        """
provider:
  primary: openrouter
  openrouter:
    api_key: test-key-123
runtime:
  engine: python
"""
    )
    cfg = Config.from_yaml(config_path)
    registry = create_default_tool_registry(allowed_dir=str(temp_workspace), config=cfg)
    assert registry.get("shell").use_rust_core is False
    assert registry.get("read_file").use_rust_core is False

    cfg.runtime.engine = "hybrid_rust"
    monkeypatch.setattr("clawlet.tools.rust_core_available", lambda: True)
    registry2 = create_default_tool_registry(allowed_dir=str(temp_workspace), config=cfg)
    assert registry2.get("shell").use_rust_core is True
    assert registry2.get("read_file").use_rust_core is True


def test_config_migration_analysis_detects_legacy_keys(temp_workspace):
    from clawlet.config_migration import analyze_config_migration

    config_path = temp_workspace / "config.yaml"
    config_path.write_text(
        """
provider:
  primary: openrouter
telegram:
  enabled: true
agent:
  full_exec: true
legacy_custom_key: true
"""
    )

    report = analyze_config_migration(config_path)
    paths = {i.path for i in report.issues}
    assert "telegram" in paths
    assert "agent.full_exec" in paths
    assert "legacy_custom_key" in paths
    # provider.openrouter missing block should be surfaced
    assert "provider.openrouter" in paths


def test_config_migration_analysis_provider_blockers(temp_workspace):
    from clawlet.config_migration import analyze_config_migration

    config_path = temp_workspace / "config.yaml"
    config_path.write_text("agent:\n  mode: safe\n")

    report = analyze_config_migration(config_path)
    assert report.has_blockers is True
    assert any(i.path == "provider" and i.severity == "error" for i in report.issues)


def test_config_migration_autofix_rewrites_legacy_keys(temp_workspace):
    from clawlet.config_migration import apply_config_migration_autofix
    import yaml

    config_path = temp_workspace / "config.yaml"
    config_path.write_text(
        """
provider:
  primary: openrouter
telegram:
  enabled: true
agent:
  full_exec: false
"""
    )

    dry = apply_config_migration_autofix(config_path, write=False)
    assert dry.changed is True
    assert any("agent.full_exec" in a for a in dry.actions)
    assert any("telegram" in a for a in dry.actions)

    applied = apply_config_migration_autofix(config_path, write=True, create_backup=True)
    assert applied.changed is True
    assert applied.backup_path.endswith(".bak")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "telegram" not in data
    assert "channels" in data and "telegram" in data["channels"]
    assert "full_exec" not in data["agent"]
    assert data["agent"]["mode"] == "safe"


def test_migration_matrix_scans_multiple_workspaces(temp_workspace):
    from clawlet.config_migration_matrix import run_migration_matrix

    root = temp_workspace / "matrix"
    root.mkdir(parents=True, exist_ok=True)

    ws_a = root / "a"
    ws_a.mkdir()
    (ws_a / "config.yaml").write_text(
        "provider:\n  primary: openrouter\n  openrouter:\n    api_key: test\n",
        encoding="utf-8",
    )

    ws_b = root / "b"
    ws_b.mkdir()
    (ws_b / "config.yaml").write_text(
        "provider:\n  primary: openrouter\ntelegram:\n  enabled: true\nagent:\n  full_exec: true\n",
        encoding="utf-8",
    )

    report = run_migration_matrix(root, pattern="config.yaml", max_workspaces=20)
    assert report.scanned >= 2
    assert report.with_issues >= 1
    assert report.total_issues >= 1


def test_summarize_migration_hints_returns_lines(temp_workspace):
    from clawlet.config_migration import analyze_config_migration, summarize_migration_hints

    config_path = temp_workspace / "config.yaml"
    config_path.write_text(
        "provider:\n  primary: openrouter\ntelegram:\n  enabled: true\nagent:\n  full_exec: true\n",
        encoding="utf-8",
    )
    report = analyze_config_migration(config_path)
    hints = summarize_migration_hints(report, max_items=3)
    assert len(hints) >= 1
    assert any("Hint:" in line for line in hints)


def test_release_readiness_report_serialization(temp_workspace):
    from clawlet.release_readiness import (
        ReleaseReadinessReport,
        run_release_readiness_smokecheck,
        summarize_gate_breaches,
        write_release_readiness_report,
    )

    report = ReleaseReadinessReport(
        workspace=str(temp_workspace),
        passed=True,
        release_gate_passed=True,
        migration_matrix_passed=True,
        plugin_matrix_passed=True,
        lane_scheduling_passed=True,
        context_cache_passed=True,
        coding_loop_passed=True,
        rust_equivalence_passed=True,
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
        rust_equivalence={"passed": True, "gate_passed": True},
        remote_health={"checked": False, "status": "skipped", "detail": ""},
    )
    out = temp_workspace / "release-readiness-report.json"
    write_release_readiness_report(out, report)
    assert out.exists()
    breaches = summarize_gate_breaches(report)
    assert breaches == []
    ok, errors = run_release_readiness_smokecheck(temp_workspace)
    assert ok is True
    assert errors == []


def test_summarize_gate_breaches_groups_release_gate_reasons(temp_workspace):
    from clawlet.release_readiness import ReleaseReadinessReport, summarize_gate_breaches

    report = ReleaseReadinessReport(
        workspace=str(temp_workspace),
        passed=False,
        release_gate_passed=False,
        migration_matrix_passed=True,
        plugin_matrix_passed=True,
        lane_scheduling_passed=False,
        context_cache_passed=False,
        coding_loop_passed=False,
        rust_equivalence_passed=True,
        remote_health_passed=True,
        reasons=["release_gate: failed"],
        gate_breaches=[],
        breach_counts={},
        release_gate={
            "passed": False,
            "breach_counts": {"lane": 1, "context": 1},
            "gate_breaches": [
                "lane: lane_scheduling: parallel elapsed 2000.00ms exceeds gate 1000.00ms",
                "context: context_cache: warm latency 1500.00ms exceeds gate 1200.00ms",
            ],
            "reasons": [
                "local: p95 latency 5000.00ms exceeded gate 3000.00ms",
                "lane_scheduling: parallel elapsed 2000.00ms exceeds gate 1000.00ms",
                "context_cache: warm latency 1500.00ms exceeds gate 1200.00ms",
                "coding_loop: success rate 70.00% is below gate 99.00%",
            ],
        },
        migration_matrix={"with_errors": 0},
        plugin_matrix={"passed": True},
        lane_scheduling={"passed": False},
        context_cache={"passed": False},
        coding_loop={"passed": False},
        rust_equivalence={"passed": True, "gate_passed": True},
        remote_health={"checked": False, "status": "skipped", "detail": ""},
    )
    breaches = summarize_gate_breaches(report)
    assert any(item.startswith("lane:") for item in breaches)
    assert any(item.startswith("context:") for item in breaches)


def test_summarize_gate_breaches_falls_back_to_reasons(temp_workspace):
    from clawlet.release_readiness import ReleaseReadinessReport, summarize_gate_breaches

    report = ReleaseReadinessReport(
        workspace=str(temp_workspace),
        passed=False,
        release_gate_passed=False,
        migration_matrix_passed=True,
        plugin_matrix_passed=True,
        lane_scheduling_passed=False,
        context_cache_passed=True,
        coding_loop_passed=True,
        rust_equivalence_passed=True,
        remote_health_passed=True,
        reasons=["release_gate: failed"],
        gate_breaches=[],
        breach_counts={},
        release_gate={
            "passed": False,
            "reasons": ["lane_scheduling: speedup ratio 1.00x is below gate 1.20x"],
        },
        migration_matrix={"with_errors": 0},
        plugin_matrix={"passed": True},
        lane_scheduling={"passed": False},
        context_cache={"passed": True},
        coding_loop={"passed": True},
        rust_equivalence={"passed": True, "gate_passed": True},
        remote_health={"checked": False, "status": "skipped", "detail": ""},
    )
    breaches = summarize_gate_breaches(report)
    assert breaches
    assert breaches[0].startswith("lane:")


def test_summarize_gate_breaches_groups_rust_reason(temp_workspace):
    from clawlet.release_readiness import ReleaseReadinessReport, summarize_gate_breaches

    report = ReleaseReadinessReport(
        workspace=str(temp_workspace),
        passed=False,
        release_gate_passed=False,
        migration_matrix_passed=True,
        plugin_matrix_passed=True,
        lane_scheduling_passed=True,
        context_cache_passed=True,
        coding_loop_passed=True,
        rust_equivalence_passed=False,
        remote_health_passed=True,
        reasons=["release_gate: failed"],
        gate_breaches=[],
        breach_counts={},
        release_gate={
            "passed": False,
            "reasons": [
                "rust_equivalence: rust extension unavailable while benchmarks.gates.require_rust_equivalence=true"
            ],
        },
        migration_matrix={"with_errors": 0},
        plugin_matrix={"passed": True},
        lane_scheduling={"passed": True},
        context_cache={"passed": True},
        coding_loop={"passed": True},
        rust_equivalence={"passed": False, "gate_passed": False},
        remote_health={"checked": False, "status": "skipped", "detail": ""},
    )

    breaches = summarize_gate_breaches(report)
    assert breaches
    assert breaches[0].startswith("rust:")
