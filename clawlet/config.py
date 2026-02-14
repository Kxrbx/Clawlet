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


class OpenAIConfig(BaseModel):
    """OpenAI provider configuration."""
    api_key: str = Field(..., description="OpenAI API key")
    use_oauth: bool = Field(default=False, description="Use OAuth instead of API key")
    organization: Optional[str] = Field(default=None, description="Organization ID")
    model: str = Field(default="gpt-5", description="Model to use")
    base_url: str = Field(default="https://api.openai.com/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_OPENAI_API_KEY":
            raise ValueError("OpenAI API key is required")
        return v


class AnthropicConfig(BaseModel):
    """Anthropic provider configuration."""
    api_key: str = Field(..., description="Anthropic API key")
    model: str = Field(default="claude-sonnet-5-20260203", description="Model to use")
    base_url: str = Field(default="https://api.anthropic.com/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_ANTHROPIC_API_KEY":
            raise ValueError("Anthropic API key is required")
        return v


class MiniMaxConfig(BaseModel):
    """MiniMax provider configuration."""
    api_key: str = Field(..., description="MiniMax API key")
    model: str = Field(default="abab7-preview", description="Model to use")
    base_url: str = Field(default="https://api.minimax.chat/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_MINIMAX_API_KEY":
            raise ValueError("MiniMax API key is required")
        return v


class MoonshotConfig(BaseModel):
    """Moonshot (Kimi) provider configuration."""
    api_key: str = Field(..., description="Moonshot API key")
    model: str = Field(default="kimi-k2.5", description="Model to use")
    base_url: str = Field(default="https://api.moonshot.ai/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_MOONSHOT_API_KEY":
            raise ValueError("Moonshot API key is required")
        return v


class GoogleConfig(BaseModel):
    """Google (Gemini) provider configuration."""
    api_key: str = Field(..., description="Google API key")
    model: str = Field(default="gemini-4-pro", description="Model to use")
    base_url: str = Field(default="https://generativelanguage.googleapis.com/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_GOOGLE_API_KEY":
            raise ValueError("Google API key is required")
        return v


class QwenConfig(BaseModel):
    """Qwen (Alibaba) provider configuration."""
    api_key: str = Field(..., description="Qwen API key")
    model: str = Field(default="qwen4", description="Model to use")
    base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_QWEN_API_KEY":
            raise ValueError("Qwen API key is required")
        return v


class ZAIConfig(BaseModel):
    """ZAI (ChatGLM) provider configuration."""
    api_key: str = Field(..., description="ZAI API key")
    model: str = Field(default="glm-5", description="Model to use")
    base_url: str = Field(default="https://open.bigmodel.cn/api/paas/v4", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_ZAI_API_KEY":
            raise ValueError("ZAI API key is required")
        return v


class CopilotConfig(BaseModel):
    """GitHub Copilot provider configuration."""
    access_token: str = Field(..., description="GitHub access token")
    github_app_id: Optional[str] = Field(default=None, description="GitHub App ID")
    github_private_key: Optional[str] = Field(default=None, description="GitHub App private key")
    model: str = Field(default="gpt-4.2", description="Model to use")
    base_url: str = Field(default="https://api.github.com/copilot", description="API base URL")
    
    @field_validator('access_token')
    @classmethod
    def validate_access_token(cls, v: str) -> str:
        if not v or v == "YOUR_GITHUB_ACCESS_TOKEN":
            raise ValueError("GitHub access token is required")
        return v


class VercelConfig(BaseModel):
    """Vercel (AI SDK) provider configuration."""
    api_key: str = Field(..., description="Vercel API key")
    model: str = Field(default="openai/gpt-5", description="Model to use")
    base_url: str = Field(default="https://api.openai.com/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_VERCEL_API_KEY":
            raise ValueError("Vercel API key is required")
        return v


class OpenCodeZenConfig(BaseModel):
    """OpenCode Zen provider configuration."""
    api_key: str = Field(..., description="OpenCode Zen API key")
    model: str = Field(default="zen-3.0", description="Model to use")
    base_url: str = Field(default="https://api.opencode.ai/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_OPENCODE_ZEN_API_KEY":
            raise ValueError("OpenCode Zen API key is required")
        return v


class XiaomiConfig(BaseModel):
    """Xiaomi provider configuration."""
    api_key: str = Field(..., description="Xiaomi API key")
    model: str = Field(default="mi-agent-2", description="Model to use")
    base_url: str = Field(default="https://api.xiaomi.com/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_XIAOMI_API_KEY":
            raise ValueError("Xiaomi API key is required")
        return v


class SyntheticConfig(BaseModel):
    """Synthetic provider configuration."""
    api_key: str = Field(..., description="Synthetic API key")
    model: str = Field(default="synthetic-llm-2", description="Model to use")
    base_url: str = Field(default="https://api.synthetic.ai/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_SYNTHETIC_API_KEY":
            raise ValueError("Synthetic API key is required")
        return v


class VeniceAIConfig(BaseModel):
    """Venice AI provider configuration."""
    api_key: str = Field(..., description="Venice AI API key")
    model: str = Field(default="venice-llama-4", description="Model to use")
    base_url: str = Field(default="https://api.venice.ai/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "YOUR_VENICE_API_KEY":
            raise ValueError("Venice AI API key is required")
        return v


class BraveSearchConfig(BaseModel):
    """Brave Search API configuration."""
    api_key: str = Field(default="", description="Brave Search API key")
    enabled: bool = Field(default=False, description="Enable Brave Search")
    max_results: int = Field(default=5, ge=1, le=20, description="Max search results")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        # Allow empty if not enabled
        return v


class ProviderConfig(BaseModel):
    """Provider configuration."""
    primary: Literal[
        "openrouter", 
        "ollama", 
        "lmstudio",
        "openai",
        "anthropic",
        "minimax",
        "moonshot",
        "google",
        "qwen",
        "zai",
        "copilot",
        "vercel",
        "opencode_zen",
        "xiaomi",
        "synthetic",
        "venice_ai"
    ] = "openrouter"
    openrouter: Optional[OpenRouterConfig] = None
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    lmstudio: LMStudioConfig = Field(default_factory=LMStudioConfig)
    openai: Optional[OpenAIConfig] = None
    anthropic: Optional[AnthropicConfig] = None
    minimax: Optional[MiniMaxConfig] = None
    moonshot: Optional[MoonshotConfig] = None
    google: Optional[GoogleConfig] = None
    qwen: Optional[QwenConfig] = None
    zai: Optional[ZAIConfig] = None
    copilot: Optional[CopilotConfig] = None
    vercel: Optional[VercelConfig] = None
    opencode_zen: Optional[OpenCodeZenConfig] = None
    xiaomi: Optional[XiaomiConfig] = None
    synthetic: Optional[SyntheticConfig] = None
    venice_ai: Optional[VeniceAIConfig] = None


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
    web_search: BraveSearchConfig = Field(default_factory=BraveSearchConfig)
    
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
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(mode='python'), f, default_flow_style=False)
        
        logger.info(f"Saved config to {path}")

    def reload(self) -> None:
        """Reload configuration from the original YAML file."""
        if self.config_path and self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            # Update self with new data
            updated = Config(**data)
            self.__dict__.update(updated.__dict__)
            logger.info(f"Reloaded config from {self.config_path}")
        else:
            logger.warning("Cannot reload config: file not found")


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
                    api_key=os.environ.get("OPENROUTER_API_KEY"),
                ),
            ),
        )


def get_default_config_path() -> Path:
    """Get the default config path."""
    return Path.home() / ".clawlet" / "config.yaml"
