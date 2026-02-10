"""
Tests for configuration validation.
"""

import pytest
import tempfile
import os
from pathlib import Path

from clawlet.config import (
    Config,
    OpenRouterConfig,
    OllamaConfig,
    LMStudioConfig,
    ProviderConfig,
    StorageConfig,
    AgentSettings,
    load_config,
)


class TestOpenRouterConfig:
    """Test OpenRouter config validation."""
    
    def test_valid_config(self):
        """Test valid OpenRouter config."""
        config = OpenRouterConfig(
            api_key="sk-test-123",
            model="anthropic/claude-sonnet-4",
        )
        
        assert config.api_key == "sk-test-123"
        assert config.model == "anthropic/claude-sonnet-4"
    
    def test_invalid_api_key(self):
        """Test that placeholder API key is rejected."""
        with pytest.raises(ValueError, match="API key is required"):
            OpenRouterConfig(api_key="YOUR_OPENROUTER_API_KEY")
    
    def test_empty_api_key(self):
        """Test that empty API key is rejected."""
        with pytest.raises(ValueError, match="API key is required"):
            OpenRouterConfig(api_key="")


class TestOllamaConfig:
    """Test Ollama config."""
    
    def test_defaults(self):
        """Test default Ollama config."""
        config = OllamaConfig()
        
        assert config.base_url == "http://localhost:11434"
        assert config.model == "llama3.2"
    
    def test_custom_values(self):
        """Test custom Ollama config."""
        config = OllamaConfig(
            base_url="http://192.168.1.100:11434",
            model="mistral",
        )
        
        assert config.base_url == "http://192.168.1.100:11434"
        assert config.model == "mistral"


class TestLMStudioConfig:
    """Test LM Studio config."""
    
    def test_defaults(self):
        """Test default LM Studio config."""
        config = LMStudioConfig()
        
        assert config.base_url == "http://localhost:1234"
        assert config.model == "local-model"


class TestProviderConfig:
    """Test provider configuration."""
    
    def test_openrouter_primary(self):
        """Test OpenRouter as primary provider."""
        config = ProviderConfig(
            primary="openrouter",
            openrouter=OpenRouterConfig(api_key="sk-test"),
        )
        
        assert config.primary == "openrouter"
        assert config.openrouter is not None
    
    def test_ollama_primary(self):
        """Test Ollama as primary provider."""
        config = ProviderConfig(
            primary="ollama",
        )
        
        assert config.primary == "ollama"
        assert config.ollama is not None


class TestStorageConfig:
    """Test storage configuration."""
    
    def test_sqlite_default(self):
        """Test SQLite as default storage."""
        config = StorageConfig()
        
        assert config.backend == "sqlite"
        assert "clawlet.db" in config.sqlite.path
    
    def test_postgres(self):
        """Test PostgreSQL storage config."""
        config = StorageConfig(
            backend="postgres",
            postgres={
                "host": "db.example.com",
                "port": 5432,
                "database": "clawlet_prod",
                "user": "admin",
                "password": "secret",
            }
        )
        
        assert config.backend == "postgres"
        assert config.postgres.host == "db.example.com"


class TestAgentSettings:
    """Test agent settings."""
    
    def test_defaults(self):
        """Test default agent settings."""
        settings = AgentSettings()
        
        assert settings.max_iterations == 10
        assert settings.context_window == 20
        assert settings.temperature == 0.7
    
    def test_custom_settings(self):
        """Test custom agent settings."""
        settings = AgentSettings(
            max_iterations=50,
            temperature=0.5,
        )
        
        assert settings.max_iterations == 50
        assert settings.temperature == 0.5
    
    def test_validation_bounds(self):
        """Test that settings are validated."""
        # Max iterations too high
        with pytest.raises(ValueError):
            AgentSettings(max_iterations=100)
        
        # Temperature too high
        with pytest.raises(ValueError):
            AgentSettings(temperature=3.0)


class TestConfig:
    """Test main config loading."""
    
    def test_from_yaml(self, tmp_path):
        """Test loading config from YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
provider:
  primary: ollama
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.2"

storage:
  backend: sqlite

agent:
  max_iterations: 20
""")
        
        config = Config.from_yaml(config_file)
        
        assert config.provider.primary == "ollama"
        assert config.storage.backend == "sqlite"
        assert config.agent.max_iterations == 20
    
    def test_env_var_substitution(self, tmp_path, monkeypatch):
        """Test environment variable substitution."""
        monkeypatch.setenv("TEST_API_KEY", "secret-key-123")
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
provider:
  primary: openrouter
  openrouter:
    api_key: "${TEST_API_KEY}"
    model: "test-model"
""")
        
        config = Config.from_yaml(config_file)
        
        assert config.provider.openrouter.api_key == "secret-key-123"
    
    def test_to_yaml(self, tmp_path):
        """Test saving config to YAML."""
        config = Config(
            provider=ProviderConfig(
                primary="ollama",
            )
        )
        
        config_path = tmp_path / "output.yaml"
        config.to_yaml(config_path)
        
        assert config_path.exists()
        
        # Load it back
        loaded = Config.from_yaml(config_path)
        assert loaded.provider.primary == "ollama"


class TestLoadConfig:
    """Test load_config function."""
    
    def test_missing_config_returns_default(self, tmp_path):
        """Test that missing config returns defaults."""
        config = load_config(tmp_path)
        
        # Should have default provider
        assert config.provider is not None
    
    def test_loads_existing_config(self, tmp_path):
        """Test loading existing config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
provider:
  primary: ollama
""")
        
        config = load_config(tmp_path)
        
        assert config.provider.primary == "ollama"
