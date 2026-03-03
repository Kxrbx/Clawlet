"""Unit tests for Config module."""

import os
import tempfile
from pathlib import Path
import yaml
import pytest

from clawlet.config import (
    Config, 
    StorageConfig, 
    SQLiteConfig, 
    ProviderConfig, 
    OpenRouterConfig,
    AgentSettings,
    HeartbeatSettings
)
from clawlet.plugins.conformance import check_plugin_conformance
from clawlet.plugins.matrix import run_plugin_conformance_matrix
from clawlet.plugins.sdk import PluginTool, ToolInput, ToolOutput, ToolSpec


def test_config_load_valid_yaml():
    """Test loading a valid config YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        config_data = {
            "provider": {
                "primary": "openrouter",
                "openrouter": {
                    "api_key": "test-key-123",
                    "model": "anthropic/claude-3.5-sonnet"
                }
            },
            "storage": {
                "backend": "sqlite",
                "sqlite": {
                    "path": "~/.clawlet/test.db"
                }
            }
        }
        config_path.write_text(yaml.dump(config_data))
        
        config = Config.from_yaml(config_path)
        
        assert config.provider.primary == "openrouter"
        assert config.provider.openrouter.api_key == "test-key-123"
        assert config.storage.backend == "sqlite"
        assert config.storage.sqlite.path == "~/.clawlet/test.db"


def test_config_env_var_substitution():
    """Test environment variable substitution in config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        config_data = {
            "provider": {
                "primary": "openrouter",
                "openrouter": {
                    "api_key": "${OPENROUTER_API_KEY}",
                    "model": "gpt-4"
                }
            }
        }
        config_path.write_text(yaml.dump(config_data))
        
        # Set env var
        os.environ["OPENROUTER_API_KEY"] = "key-from-env"
        
        config = Config.from_yaml(config_path)
        assert config.provider.openrouter.api_key == "key-from-env"
        
        # Cleanup
        del os.environ["OPENROUTER_API_KEY"]


def test_config_missing_api_key_raises():
    """Test that missing API key raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        config_data = {
            "provider": {
                "primary": "openrouter",
                "openrouter": {
                    "api_key": "",
                    "model": "gpt-4"
                }
            }
        }
        config_path.write_text(yaml.dump(config_data))
        
        with pytest.raises(ValueError, match="OpenRouter API key is required"):
            Config.from_yaml(config_path)


def test_config_default_values():
    """Test that default values are set correctly."""
    provider = ProviderConfig()
    storage = StorageConfig()
    agent_settings = AgentSettings()
    heartbeat_settings = HeartbeatSettings()
    
    cfg = Config(provider=provider, storage=storage, agent=agent_settings, heartbeat=heartbeat_settings)
    
    assert cfg.provider.primary == "openrouter"
    assert cfg.storage.backend == "sqlite"
    assert cfg.agent.max_iterations == 10
    assert cfg.heartbeat.interval_minutes == 120
    assert cfg.runtime.engine == "hybrid_rust"
    assert cfg.runtime.enable_parallel_read_batches is True
    assert cfg.runtime.max_parallel_read_tools == 4
    assert cfg.runtime.replay.directory == ".runtime"
    assert cfg.runtime.remote.enabled is False
    assert cfg.runtime.policy.lanes["read_only"] == "parallel:read_only"
    assert cfg.runtime.policy.lanes["workspace_write"] == "serial:workspace_write"
    assert cfg.benchmarks.gates.min_deterministic_replay_pass_rate_pct == 98.0
    assert cfg.benchmarks.gates.min_lane_speedup_ratio == 1.20
    assert cfg.benchmarks.gates.max_lane_parallel_elapsed_ms == 1000.0
    assert cfg.benchmarks.gates.min_context_cache_speedup_ratio == 1.05
    assert cfg.benchmarks.gates.max_context_cache_warm_ms == 1200.0
    assert cfg.benchmarks.gates.min_coding_loop_success_rate_pct == 99.0
    assert cfg.benchmarks.gates.max_coding_loop_p95_total_ms == 2500.0
    assert cfg.benchmarks.gates.require_rust_equivalence is False
    assert cfg.plugins.sdk_version == "2.0.0"


def test_runtime_policy_lanes_must_use_supported_prefixes():
    provider = ProviderConfig()
    storage = StorageConfig()
    agent_settings = AgentSettings()
    heartbeat_settings = HeartbeatSettings()

    with pytest.raises(ValueError, match="must start with 'serial:' or 'parallel:'"):
        Config(
            provider=provider,
            storage=storage,
            agent=agent_settings,
            heartbeat=heartbeat_settings,
            runtime={
                "policy": {
                    "lanes": {
                        "read_only": "readonly",
                        "workspace_write": "serial:workspace_write",
                        "elevated": "serial:elevated",
                    }
                }
            },
        )


def test_runtime_max_parallel_read_tools_bounds():
    provider = ProviderConfig()
    storage = StorageConfig()
    agent_settings = AgentSettings()
    heartbeat_settings = HeartbeatSettings()

    with pytest.raises(ValueError):
        Config(
            provider=provider,
            storage=storage,
            agent=agent_settings,
            heartbeat=heartbeat_settings,
            runtime={"max_parallel_read_tools": 0},
        )


class _GoodPlugin(PluginTool):
    def __init__(self):
        super().__init__(ToolSpec(name="good_plugin", description="ok plugin"))

    async def execute_with_context(self, tool_input: ToolInput, context) -> ToolOutput:
        return ToolOutput(output="ok")


class _BadPluginNoOverride(PluginTool):
    def __init__(self):
        super().__init__(ToolSpec(name="bad_plugin", description="bad plugin", sdk_version="1.0.0"))


def test_plugin_conformance_passes_valid_plugin():
    report = check_plugin_conformance([_GoodPlugin()])
    assert report.passed is True
    assert len(report.errors) == 0


def test_plugin_conformance_detects_incompatible_sdk_and_missing_override():
    report = check_plugin_conformance([_BadPluginNoOverride()])
    codes = {issue.code for issue in report.issues}
    assert "sdk_version_incompatible" in codes
    assert "execute_with_context_not_overridden" in codes
    assert report.passed is False


def test_plugin_matrix_aggregates_results():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        good = root / "good"
        bad = root / "bad"
        good.mkdir(parents=True, exist_ok=True)
        bad.mkdir(parents=True, exist_ok=True)

        (good / "plugin.py").write_text(
            "from clawlet.plugins import PluginTool, ToolInput, ToolOutput, ToolSpec\\n"
            "class GoodTool(PluginTool):\\n"
            "    def __init__(self):\\n"
            "        super().__init__(ToolSpec(name='good_tool', description='good'))\\n"
            "    async def execute_with_context(self, tool_input: ToolInput, context) -> ToolOutput:\\n"
            "        return ToolOutput(output='ok')\\n"
            "TOOLS=[GoodTool()]\\n",
            encoding="utf-8",
        )
        (bad / "plugin.py").write_text(
            "from clawlet.plugins import PluginTool, ToolSpec\\n"
            "class BadTool(PluginTool):\\n"
            "    def __init__(self):\\n"
            "        super().__init__(ToolSpec(name='bad_tool', description='bad', sdk_version='1.0.0'))\\n"
            "TOOLS=[BadTool()]\\n",
            encoding="utf-8",
        )

        report = run_plugin_conformance_matrix([good, bad])
        assert report.scanned_directories == 2
        assert report.scanned_tools >= 2
        assert report.total_errors >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
