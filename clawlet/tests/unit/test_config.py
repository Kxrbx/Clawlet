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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
