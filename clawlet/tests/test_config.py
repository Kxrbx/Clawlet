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
    assert "telegram" in data
    assert "discord" in data
    assert data["runtime"]["engine"] == "hybrid_rust"
    assert data["benchmarks"]["gates"]["min_deterministic_replay_pass_rate_pct"] == 98.0
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
