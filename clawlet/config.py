"""
Configuration management with validation.
"""

import os
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
import yaml

from loguru import logger


class OpenRouterConfig(BaseModel):
    """OpenRouter provider configuration."""
    api_key: str = Field(..., description="OpenRouter API key")
    model: str = Field(default="anthropic/claude-sonnet-4", description="Model to use")
    base_url: str = Field(default="https://openrouter.ai/api/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_OPENROUTER_API_KEY":
            raise ValueError("OpenRouter API key is required")
        return v


class OllamaConfig(BaseModel):
    """Ollama provider configuration."""
    base_url: str = Field(default="http://localhost:11434", description="Ollama server URL")
    model: str = Field(default="llama3.2", description="Model to use")


class LMStudioConfig(BaseModel):
    """LM Studio provider configuration."""
    base_url: str = Field(default="http://localhost:1234", description="LM Studio server URL")
    model: str = Field(default="local-model", description="Model name")


class ProviderConfig(BaseModel):
    """Provider configuration."""
    primary: Literal["openrouter", "ollama", "lmstudio"] = "openrouter"
    openrouter: Optional[OpenRouterConfig] = None
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    lmstudio: LMStudioConfig = Field(default_factory=LMStudioConfig)


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""
    enabled: bool = False
    token: str = ""
    
    @field_validator('token')
    @classmethod
    def validate_token_if_enabled(cls, v: str, info) -> str:
        if info.data.get('enabled') and not v:
            raise ValueError("Telegram token is required when enabled")
        return v


class DiscordConfig(BaseModel):
    """Discord channel configuration."""
    enabled: bool = False
    token: str = ""
    command_prefix: str = "!"
    
    @field_validator('token')
    @classmethod
    def validate_token_if_enabled(cls, v: str, info) -> str:
        if info.data.get('enabled') and not v:
            raise ValueError("Discord token is required when enabled")
        return v


class SQLiteConfig(BaseModel):
    """SQLite storage configuration."""
    path: str = "~/.clawlet/clawlet.db"


class PostgresConfig(BaseModel):
    """PostgreSQL storage configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "clawlet"
    user: str = "clawlet"
    password: str = ""


class StorageConfig(BaseModel):
    """Storage configuration."""
    backend: Literal["sqlite", "postgres"] = "sqlite"
    sqlite: SQLiteConfig = Field(default_factory=SQLiteConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)


class AgentSettings(BaseModel):
    """Agent settings."""
    max_iterations: int = Field(default=10, ge=1, le=50)
    context_window: int = Field(default=20, ge=5, le=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_history: int = Field(default=100, ge=10, le=1000)


class HeartbeatSettings(BaseModel):
    """Heartbeat settings."""
    interval_minutes: int = Field(default=120, ge=10, le=1440)
    quiet_hours_start: int = Field(default=2, ge=0, le=23)
    quiet_hours_end: int = Field(default=9, ge=0, le=23)


class Config(BaseModel):
    """Main configuration."""
    provider: ProviderConfig
    channels: dict = Field(default_factory=lambda: {
        "telegram": TelegramConfig(),
        "discord": DiscordConfig(),
    })
    storage: StorageConfig = Field(default_factory=StorageConfig)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    heartbeat: HeartbeatSettings = Field(default_factory=HeartbeatSettings)
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file."""
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        
        # Support environment variable substitution
        data = cls._substitute_env_vars(data)
        
        return cls(**data)
    
    @staticmethod
    def _substitute_env_vars(data: dict) -> dict:
        """Recursively substitute environment variables in config."""
        import re
        
        def substitute(value):
            if isinstance(value, str):
                # Match ${VAR_NAME} or ${VAR_NAME:-default}
                pattern = r'\$\{([^}]+)\}'
                
                def replace(match):
                    expr = match.group(1)
                    if ':-' in expr:
                        var_name, default = expr.split(':-', 1)
                        return os.environ.get(var_name, default)
                    return os.environ.get(expr, '')
                
                return re.sub(pattern, replace, value)
            elif isinstance(value, dict):
                return {k: substitute(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [substitute(item) for item in value]
            return value
        
        return substitute(data)
    
    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            yaml.dump(self.model_dump(mode='python'), f, default_flow_style=False)
        
        logger.info(f"Saved config to {path}")


def load_config(workspace: Optional[Path] = None) -> Config:
    """
    Load configuration from workspace or default location.
    
    Args:
        workspace: Workspace directory (defaults to ~/.clawlet)
        
    Returns:
        Config object
    """
    workspace = workspace or Path.home() / ".clawlet"
    config_path = workspace / "config.yaml"
    
    if config_path.exists():
        logger.info(f"Loading config from {config_path}")
        return Config.from_yaml(config_path)
    else:
        logger.warning(f"No config file at {config_path}, using defaults")
        # Create default config with placeholder values
        return Config(
            provider=ProviderConfig(
                primary="openrouter",
                openrouter=OpenRouterConfig(
                    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                ),
            ),
        )


def get_default_config_path() -> Path:
    """Get the default config path."""
    return Path.home() / ".clawlet" / "config.yaml"
