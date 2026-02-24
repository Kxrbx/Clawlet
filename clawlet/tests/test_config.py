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
