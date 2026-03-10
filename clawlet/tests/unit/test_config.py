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
    HeartbeatSettings,
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
    assert cfg.agent.max_iterations == 50
    assert cfg.agent.max_tool_calls_per_message == 20
    assert cfg.heartbeat.enabled is True
    assert cfg.heartbeat.interval_minutes == 30
    assert cfg.heartbeat.quiet_hours_start == 0
    assert cfg.heartbeat.quiet_hours_end == 0
    assert cfg.heartbeat.target == "last"
    assert cfg.heartbeat.ack_max_chars == 24
    assert cfg.heartbeat.proactive_enabled is False
    assert cfg.heartbeat.proactive_queue_path == "tasks/QUEUE.md"
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


def test_scheduler_task_schema_loads():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        config_data = {
            "provider": {
                "primary": "openrouter",
                "openrouter": {
                    "api_key": "test-key-123",
                    "model": "anthropic/claude-3.5-sonnet",
                },
            },
            "scheduler": {
                "enabled": True,
                "timezone": "UTC",
                "tasks": {
                    "daily_summary": {
                        "name": "Daily Summary",
                        "action": "agent",
                        "cron": "0 18 * * *",
                        "session_target": "main",
                        "wake_mode": "now",
                        "delivery_mode": "announce",
                        "prompt": "Summarize today's activity.",
                    }
                },
            },
        }
        config_path.write_text(yaml.dump(config_data))

        config = Config.from_yaml(config_path)
        assert config.scheduler.enabled is True
        assert "daily_summary" in config.scheduler.tasks
        task = config.scheduler.tasks["daily_summary"]
        assert task.name == "Daily Summary"
        assert task.session_target == "main"
        assert task.wake_mode == "now"
        assert task.delivery_mode == "announce"


def test_scheduler_task_wake_mode_accepts_upstream_alias():
    provider = ProviderConfig()
    storage = StorageConfig()
    agent_settings = AgentSettings()
    heartbeat_settings = HeartbeatSettings()

    cfg = Config(
        provider=provider,
        storage=storage,
        agent=agent_settings,
        heartbeat=heartbeat_settings,
        scheduler={
            "tasks": {
                "job": {
                    "name": "Job",
                    "action": "agent",
                    "interval": "1h",
                    "wake_mode": "next-heartbeat",
                }
            }
        },
    )
    assert cfg.scheduler.tasks["job"].wake_mode == "next_heartbeat"


def test_scheduler_task_supports_advanced_openclaw_fields():
    provider = ProviderConfig()
    storage = StorageConfig()
    agent_settings = AgentSettings()
    heartbeat_settings = HeartbeatSettings()

    cfg = Config(
        provider=provider,
        storage=storage,
        agent=agent_settings,
        heartbeat=heartbeat_settings,
        scheduler={
            "tasks": {
                "job": {
                    "name": "Job",
                    "action": "agent",
                    "interval": "1h",
                    "agent_id": "agent-a",
                    "session_key": "session-a",
                    "delete_after_run": True,
                    "best_effort_delivery": True,
                    "failure_alert": {
                        "enabled": True,
                        "after": 2,
                        "cooldown_seconds": 60,
                        "mode": "announce",
                        "channel": "scheduler",
                        "to": "main",
                    },
                }
            }
        },
    )
    task = cfg.scheduler.tasks["job"]
    assert task.agent_id == "agent-a"
    assert task.session_key == "session-a"
    assert task.delete_after_run is True
    assert task.best_effort_delivery is True
    assert task.failure_alert.enabled is True
    assert task.failure_alert.after == 2


def test_scheduler_task_rejects_multiple_schedule_modes():
    provider = ProviderConfig()
    storage = StorageConfig()
    agent_settings = AgentSettings()
    heartbeat_settings = HeartbeatSettings()

    with pytest.raises(ValueError, match="only set one of: cron, interval, one_time"):
        Config(
            provider=provider,
            storage=storage,
            agent=agent_settings,
            heartbeat=heartbeat_settings,
            scheduler={
                "tasks": {
                    "bad_task": {
                        "name": "Bad Task",
                        "action": "agent",
                        "cron": "0 9 * * *",
                        "interval": "1h",
                    }
                }
            },
        )


def test_heartbeat_legacy_every_and_active_hours_are_normalized():
    provider = ProviderConfig(primary="openrouter", openrouter=OpenRouterConfig(api_key="k", model="m"))
    storage = StorageConfig()
    agent_settings = AgentSettings()
    heartbeat_settings = HeartbeatSettings(every="90m", active_hours="8-20")

    cfg = Config(provider=provider, storage=storage, agent=agent_settings, heartbeat=heartbeat_settings)
    assert cfg.heartbeat.interval_minutes == 90
    assert cfg.heartbeat.quiet_hours_start == 20
    assert cfg.heartbeat.quiet_hours_end == 8


def test_legacy_top_level_tasks_are_normalized_to_scheduler():
    provider = ProviderConfig()
    storage = StorageConfig()
    agent_settings = AgentSettings()
    heartbeat_settings = HeartbeatSettings()

    config = Config(
        provider=provider,
        storage=storage,
        agent=agent_settings,
        heartbeat=heartbeat_settings,
        tasks={
            "legacy_task": {
                "name": "Legacy Task",
                "action": "agent",
                "cron": "0 12 * * *",
            }
        },
    )

    assert "legacy_task" in config.scheduler.tasks
    assert config.scheduler.tasks["legacy_task"].name == "Legacy Task"


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
            "from clawlet.plugins import PluginTool, ToolInput, ToolOutput, ToolSpec\n"
            "class GoodTool(PluginTool):\n"
            "    def __init__(self):\n"
            "        super().__init__(ToolSpec(name='good_tool', description='good'))\n"
            "    async def execute_with_context(self, tool_input: ToolInput, context) -> ToolOutput:\n"
            "        return ToolOutput(output='ok')\n"
            "TOOLS=[GoodTool()]\n",
            encoding="utf-8",
        )
        (bad / "plugin.py").write_text(
            "from clawlet.plugins import PluginTool, ToolSpec\n"
            "class BadTool(PluginTool):\n"
            "    def __init__(self):\n"
            "        super().__init__(ToolSpec(name='bad_tool', description='bad', sdk_version='1.0.0'))\n"
            "TOOLS=[BadTool()]\n",
            encoding="utf-8",
        )

        report = run_plugin_conformance_matrix([good, bad])
        assert report.scanned_directories == 2
        assert report.scanned_tools >= 2
        assert report.total_errors >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
