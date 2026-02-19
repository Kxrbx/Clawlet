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


class APIKeyConfig(BaseModel):
    """Base class for provider configs requiring API keys."""
    api_key: str = Field(..., description="API key")
    model: str = Field(default="default", description="Model to use")
    base_url: str = Field(default="", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("API key is required")
        # Check against class-specific placeholder
        class_name = cls.__name__.replace('Config', '').upper()
        placeholder = f"YOUR_{class_name}_API_KEY"
        if v == placeholder:
            raise ValueError(f"{class_name.replace('_', ' ')} API key is required")
        return v


class OpenRouterConfig(APIKeyConfig):
    """OpenRouter provider configuration."""
    model: str = Field(default="anthropic/claude-sonnet-4", description="Model to use")
    base_url: str = Field(default="https://openrouter.ai/api/v1", description="API base URL")


class OllamaConfig(BaseModel):
    """Ollama provider configuration."""
    base_url: str = Field(default="http://localhost:11434", description="Ollama server URL")
    model: str = Field(default="llama3.2", description="Model to use")


class LMStudioConfig(BaseModel):
    """LM Studio provider configuration."""
    base_url: str = Field(default="http://localhost:1234", description="LM Studio server URL")
    model: str = Field(default="local-model", description="Model name")


class OpenAIConfig(APIKeyConfig):
    """OpenAI provider configuration."""
    use_oauth: bool = Field(default=False, description="Use OAuth instead of API key")
    organization: Optional[str] = Field(default=None, description="Organization ID")
    model: str = Field(default="gpt-5", description="Model to use")
    base_url: str = Field(default="https://api.openai.com/v1", description="API base URL")


class AnthropicConfig(APIKeyConfig):
    """Anthropic provider configuration."""
    model: str = Field(default="claude-sonnet-5-20260203", description="Model to use")
    base_url: str = Field(default="https://api.anthropic.com/v1", description="API base URL")


class MiniMaxConfig(APIKeyConfig):
    """MiniMax provider configuration."""
    model: str = Field(default="abab7-preview", description="Model to use")
    base_url: str = Field(default="https://api.minimax.chat/v1", description="API base URL")


class MoonshotConfig(APIKeyConfig):
    """Moonshot (Kimi) provider configuration."""
    model: str = Field(default="kimi-k2.5", description="Model to use")
    base_url: str = Field(default="https://api.moonshot.ai/v1", description="API base URL")


class GoogleConfig(APIKeyConfig):
    """Google (Gemini) provider configuration."""
    model: str = Field(default="gemini-4-pro", description="Model to use")
    base_url: str = Field(default="https://generativelanguage.googleapis.com/v1", description="API base URL")


class QwenConfig(APIKeyConfig):
    """Qwen (Alibaba) provider configuration."""
    model: str = Field(default="qwen4", description="Model to use")
    base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="API base URL")


class ZAIConfig(APIKeyConfig):
    """ZAI (ChatGLM) provider configuration."""
    model: str = Field(default="glm-5", description="Model to use")
    base_url: str = Field(default="https://open.bigmodel.cn/api/paas/v4", description="API base URL")


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


class VercelConfig(APIKeyConfig):
    """Vercel (AI SDK) provider configuration."""
    model: str = Field(default="openai/gpt-5", description="Model to use")
    base_url: str = Field(default="https://api.openai.com/v1", description="API base URL")


class OpenCodeZenConfig(APIKeyConfig):
    """OpenCode Zen provider configuration."""
    model: str = Field(default="zen-3.0", description="Model to use")
    base_url: str = Field(default="https://api.opencode.ai/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("API key is required")
        if v == "YOUR_OPENCODE_ZEN_API_KEY":
            raise ValueError("OpenCode Zen API key is required")
        return v


class XiaomiConfig(APIKeyConfig):
    """Xiaomi provider configuration."""
    model: str = Field(default="mi-agent-2", description="Model to use")
    base_url: str = Field(default="https://api.xiaomi.com/v1", description="API base URL")


class SyntheticConfig(APIKeyConfig):
    """Synthetic provider configuration."""
    model: str = Field(default="synthetic-llm-2", description="Model to use")
    base_url: str = Field(default="https://api.synthetic.ai/v1", description="API base URL")


class VeniceAIConfig(APIKeyConfig):
    """Venice AI provider configuration."""
    model: str = Field(default="venice-llama-4", description="Model to use")
    base_url: str = Field(default="https://api.venice.ai/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("API key is required")
        if v == "YOUR_VENICE_API_KEY":
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


class WhatsAppConfig(BaseModel):
    """WhatsApp Business API channel configuration."""
    enabled: bool = False
    phone_number_id: str = ""
    access_token: str = ""
    verify_token: str = ""
    allowed_users: list[str] = Field(default_factory=list)
    port: int = Field(default=8080, ge=1, le=65535)
    host: str = "0.0.0.0"
    mark_read: bool = True
    
    @field_validator('phone_number_id', 'access_token')
    @classmethod
    def validate_required_if_enabled(cls, v: str, info) -> str:
        if info.data.get('enabled') and not v:
            raise ValueError(f"{info.field_name} is required when WhatsApp is enabled")
        return v


class SlackConfig(BaseModel):
    """Slack channel configuration using Slack Bolt."""
    enabled: bool = False
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-... (for Socket Mode)
    signing_secret: str = ""  # For HTTP mode
    socket_mode: bool = True  # Use Socket Mode (recommended)
    allowed_channels: list[str] = Field(default_factory=list)
    allowed_users: list[str] = Field(default_factory=list)
    port: int = Field(default=3000, ge=1, le=65535)  # For HTTP mode
    host: str = "0.0.0.0"  # For HTTP mode
    
    @field_validator('bot_token')
    @classmethod
    def validate_bot_token_if_enabled(cls, v: str, info) -> str:
        if info.data.get('enabled') and not v:
            raise ValueError("Slack bot_token is required when enabled")
        return v
    
    @field_validator('app_token')
    @classmethod
    def validate_app_token_if_socket_mode(cls, v: str, info) -> str:
        if info.data.get('enabled') and info.data.get('socket_mode', True) and not v:
            raise ValueError("Slack app_token is required for Socket Mode")
        return v
    
    @field_validator('signing_secret')
    @classmethod
    def validate_signing_secret_if_http_mode(cls, v: str, info) -> str:
        if info.data.get('enabled') and not info.data.get('socket_mode', True) and not v:
            raise ValueError("Slack signing_secret is required for HTTP mode")
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


class SkillsConfig(BaseModel):
    """Skills system configuration."""
    enabled: bool = Field(default=True, description="Enable the skills system")
    directories: list[str] = Field(
        default_factory=lambda: ["~/.clawlet/skills", "./skills"],
        description="Directories to search for skills"
    )
    disabled: list[str] = Field(
        default_factory=list,
        description="List of skill names to disable"
    )
    # Skill-specific configurations are stored as a dict
    # e.g., {"email": {"smtp_server": "...", ...}}
    email: dict = Field(default_factory=dict)
    calendar: dict = Field(default_factory=dict)
    notes: dict = Field(default_factory=dict)


class GitHubWebhookConfig(BaseModel):
    """GitHub webhook configuration."""
    secret: str = Field(default="", description="GitHub webhook secret for signature verification")


class StripeWebhookConfig(BaseModel):
    """Stripe webhook configuration."""
    secret: str = Field(default="", description="Stripe signing secret for signature verification")


class WebhooksConfig(BaseModel):
    """Webhooks system configuration."""
    enabled: bool = Field(default=False, description="Enable the webhooks server")
    host: str = Field(default="0.0.0.0", description="Host to bind the webhook server")
    port: int = Field(default=8080, ge=1, le=65535, description="Port for the webhook server")
    secret: str = Field(default="", description="Default secret for custom webhooks")
    github: GitHubWebhookConfig = Field(default_factory=GitHubWebhookConfig)
    stripe: StripeWebhookConfig = Field(default_factory=StripeWebhookConfig)
    rate_limit_max: int = Field(default=100, ge=1, description="Max requests per rate limit window")
    rate_limit_window: int = Field(default=60, ge=1, description="Rate limit window in seconds")
    queue_max_size: int = Field(default=1000, ge=10, description="Max events in queue")
    # Custom webhook handlers: {"handler_name": "secret"}
    custom_handlers: dict[str, str] = Field(default_factory=dict)


class RetryPolicyConfig(BaseModel):
    """Retry policy configuration for scheduled tasks."""
    max_attempts: int = Field(default=3, ge=1, le=10, description="Maximum retry attempts")
    delay_seconds: float = Field(default=60.0, ge=1.0, description="Initial delay between retries in seconds")
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0, description="Exponential backoff multiplier")
    max_delay_seconds: float = Field(default=3600.0, ge=60.0, description="Maximum delay between retries")


class TaskConfig(BaseModel):
    """Configuration for a single scheduled task."""
    name: str = Field(..., description="Unique task name")
    
    # Scheduling (one of these)
    cron: Optional[str] = Field(default=None, description="Cron expression (e.g., '0 8 * * *')")
    interval: Optional[str] = Field(default=None, description="Interval (e.g., '5m', '1h', '1d')")
    one_time: Optional[str] = Field(default=None, description="One-time execution at ISO datetime")
    
    # Timezone
    timezone: str = Field(default="UTC", description="Timezone for scheduling")
    
    # Action
    action: str = Field(default="callback", description="Action type: agent, tool, webhook, health_check, skill, callback")
    prompt: Optional[str] = Field(default=None, description="Prompt for agent action")
    tool: Optional[str] = Field(default=None, description="Tool name for tool action")
    webhook_url: Optional[str] = Field(default=None, description="URL for webhook action")
    webhook_method: str = Field(default="POST", description="HTTP method for webhook")
    skill: Optional[str] = Field(default=None, description="Skill name for skill action")
    params: dict = Field(default_factory=dict, description="Additional parameters")
    
    # Task settings
    enabled: bool = Field(default=True, description="Whether task is enabled")
    priority: str = Field(default="normal", description="Priority: low, normal, high, critical")
    
    # Dependencies
    depends_on: list[str] = Field(default_factory=list, description="Task IDs this task depends on")
    
    # Retry
    retry: Optional[RetryPolicyConfig] = Field(default=None, description="Retry policy")
    
    # Notifications
    notify_on_success: bool = Field(default=False, description="Notify on successful execution")
    notify_on_failure: bool = Field(default=True, description="Notify on failed execution")
    
    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tags for organization")


class ScheduleConfig(BaseModel):
    """Configuration for the scheduling system."""
    enabled: bool = Field(default=True, description="Enable the scheduling system")
    timezone: str = Field(default="UTC", description="Default timezone for tasks")
    tasks: dict[str, TaskConfig] = Field(default_factory=dict, description="Scheduled tasks by ID")
    max_concurrent: int = Field(default=3, ge=1, le=10, description="Maximum concurrent task executions")
    default_retry_attempts: int = Field(default=3, ge=1, le=10, description="Default max retry attempts")
    default_retry_delay: str = Field(default="1m", description="Default retry delay")
    check_interval_seconds: float = Field(default=60.0, ge=10.0, le=300.0, description="How often to check for pending tasks")
    state_file: str = Field(default="~/.clawlet/scheduler_state.json", description="Path to save scheduler state")


class RouteRuleConfig(BaseModel):
    """Configuration for a single routing rule."""
    agent: str = Field(..., description="Agent ID to route to (workspace name)")
    channel: Optional[str] = Field(default=None, description="Channel to match (telegram, discord, slack, whatsapp)")
    user_id: Optional[str] = Field(default=None, description="Specific user ID to match")
    enabled: bool = Field(default=True, description="Whether this rule is active")


class RouterConfig(BaseModel):
    """Configuration for the routing system."""
    enabled: bool = Field(default=True, description="Enable the routing system")
    rules: dict[str, RouteRuleConfig] = Field(default_factory=dict, description="Routing rules by rule ID")
    fallback_agent: Optional[str] = Field(default=None, description="Default agent for unmatched messages")


class ClawletConfig(BaseSettings):
    """Main Clawlet configuration."""
    app_name: str = "Clawlet"
    version: str = "0.1.0"
    debug: bool = False
    
    # Provider configuration
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    
    # Channel configurations
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    
    # Storage
    storage: StorageConfig = Field(default_factory=StorageConfig)
    
    # Agent settings
    agent: AgentSettings = Field(default_factory=AgentSettings)
    
    # Heartbeat
    heartbeat: HeartbeatSettings = Field(default_factory=HeartbeatSettings)
    
    # Skills
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    
    # Webhooks
    webhooks: WebhooksConfig = Field(default_factory=WebhooksConfig)
    
    # Scheduling
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    
    # Router
    router: RouterConfig = Field(default_factory=RouterConfig)
    
    # Paths
    data_dir: str = "~/.clawlet"
    config_dir: str = "~/.clawlet"
    
    class Config:
        env_prefix = "CLAWLET_"
        env_nested_delimiter = "__"
    
    @classmethod
    def from_yaml(cls, path: str | Path) -> "ClawletConfig":
        """Load configuration from a YAML file."""
        path = Path(path).expanduser()
        if not path.exists():
            logger.warning(f"Config file not found: {path}")
            return cls()
        
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        
        return cls(**data)
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "ClawletConfig":
        """Load configuration from file or environment."""
        if config_path:
            return cls.from_yaml(config_path)
        
        # Try default config locations
        default_paths = [
            Path("~/.clawlet/config.yaml"),
            Path("~/.clawlet.yml"),
            Path("./clawlet.yaml"),
            Path("./config.yaml"),
        ]
        
        for path in default_paths:
            if path.exists():
                logger.info(f"Loading config from: {path}")
                return cls.from_yaml(path)
        
        logger.info("No config file found, using defaults")
        return cls()
    
    def save(self, path: str | Path) -> None:
        """Save configuration to a YAML file."""
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            yaml.dump(self.model_dump(exclude_none=True), f, default_flow_style=False)


# Default config instance
default_config = ClawletConfig()

# ============================================================================
# Backward-compatible aliases (for existing code)
# ============================================================================

# Alias for ClawletConfig
Config = ClawletConfig


def load_config(workspace: Path = None) -> ClawletConfig:
    """Load configuration from the workspace.
    
    This is a backward-compatible function that loads the config
    from the workspace directory.
    """
    if workspace is None:
        workspace = Path.home() / ".clawlet"
    
    config_path = workspace / "config.yaml"
    
    if config_path.exists():
        return ClawletConfig.from_yaml(config_path)
    
    return ClawletConfig()


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    return Path.home() / ".clawlet" / "config.yaml"
