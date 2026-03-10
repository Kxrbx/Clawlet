"""
Configuration management with validation.
"""

import os
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import yaml

from loguru import logger


def _validate_api_key_strict(api_key: str, provider_name: str = "") -> str:
    """
    Validate API key with strict format checks.
    Raises ValueError if the key is invalid.
    """
    if not api_key or api_key.strip() != api_key:
        raise ValueError(f"{provider_name} API key is required and must not have leading/trailing whitespace")
    
    if any(c.isspace() for c in api_key):
        raise ValueError(f"{provider_name} API key contains internal whitespace")
    
    lower_key = api_key.lower()
    placeholder_patterns = ["test", "xxx", "dummy", "placeholder", "demo", "example"]
    if lower_key in placeholder_patterns:
        raise ValueError(f"{provider_name} API key appears to be a placeholder")
    
    if lower_key.startswith("your_") or api_key.startswith("YOUR_"):
        raise ValueError(f"{provider_name} API key appears to be a placeholder (starts with 'YOUR_')")
    
    return api_key


class OpenRouterConfig(BaseModel):
    """OpenRouter provider configuration."""
    api_key: str = Field(..., description="OpenRouter API key")
    model: str = Field(default="anthropic/claude-sonnet-4", description="Model to use")
    base_url: str = Field(default="https://openrouter.ai/api/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "OpenRouter")


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
    organization: Optional[str] = Field(default=None, description="OpenAI Organization ID")
    model: str = Field(default="gpt-5", description="Model to use")
    base_url: str = Field(default="https://api.openai.com/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "OpenAI")


class AnthropicConfig(BaseModel):
    """Anthropic provider configuration."""
    api_key: str = Field(..., description="Anthropic API key")
    model: str = Field(default="claude-sonnet-5-20260203", description="Model to use")
    base_url: str = Field(default="https://api.anthropic.com", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "Anthropic")


class MiniMaxConfig(BaseModel):
    """MiniMax provider configuration."""
    api_key: str = Field(..., description="MiniMax API key")
    model: str = Field(default="abab7-preview", description="Model to use")
    base_url: str = Field(default="https://api.minimax.chat/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "MiniMax")


class MoonshotConfig(BaseModel):
    """Moonshot AI provider configuration."""
    api_key: str = Field(..., description="Moonshot API key")
    model: str = Field(default="kimi-k2.5", description="Model to use")
    base_url: str = Field(default="https://api.moonshot.chat/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "Moonshot")


class GoogleConfig(BaseModel):
    """Google Gemini provider configuration."""
    api_key: str = Field(..., description="Google API key")
    model: str = Field(default="gemini-4-pro", description="Model to use")
    base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "Google")


class QwenConfig(BaseModel):
    """Qwen (Alibaba) provider configuration."""
    api_key: str = Field(..., description="Qwen API key")
    model: str = Field(default="qwen4", description="Model to use")
    base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "Qwen")


class ZAIConfig(BaseModel):
    """Z.AI (GLM) provider configuration."""
    api_key: str = Field(..., description="Z.AI API key")
    model: str = Field(default="glm-5", description="Model to use")
    base_url: str = Field(default="https://open.bigmodel.cn/api/paas/v4", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "Z.AI")


class CopilotConfig(BaseModel):
    """GitHub Copilot provider configuration."""
    access_token: str = Field(..., description="GitHub Access Token")
    model: str = Field(default="gpt-4.2", description="Model to use")
    
    @field_validator('access_token')
    @classmethod
    def validate_token(cls, v: str) -> str:
        return _validate_api_key_strict(v, "GitHub Token")


class VercelConfig(BaseModel):
    """Vercel AI Gateway provider configuration."""
    api_key: str = Field(..., description="Vercel API key")
    model: str = Field(default="openai/gpt-5", description="Model to use")
    base_url: str = Field(default="https://gateway.ai.cloudflare.com/v1/account/gateway", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "Vercel")


class OpenCodeZenConfig(BaseModel):
    """OpenCode Zen provider configuration."""
    api_key: str = Field(..., description="OpenCode Zen API key")
    model: str = Field(default="zen-3.0", description="Model to use")
    base_url: str = Field(default="https://api.opencode.io/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "OpenCode Zen")


class XiaomiConfig(BaseModel):
    """Xiaomi provider configuration."""
    api_key: str = Field(..., description="Xiaomi API key")
    model: str = Field(default="mi-agent-2", description="Model to use")
    base_url: str = Field(default="https://api.xiaomi.com/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "Xiaomi")


class SyntheticConfig(BaseModel):
    """Synthetic AI provider configuration."""
    api_key: str = Field(..., description="Synthetic AI API key")
    model: str = Field(default="synthetic-llm-2", description="Model to use")
    base_url: str = Field(default="https://api.synthetic.ai/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "Synthetic AI")


class VeniceAIConfig(BaseModel):
    """Venice AI provider configuration."""
    api_key: str = Field(..., description="Venice AI API key")
    model: str = Field(default="venice-llama-4", description="Model to use")
    base_url: str = Field(default="https://api.venice.ai/v1", description="API base URL")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        return _validate_api_key_strict(v, "Venice AI")


class BraveSearchConfig(BaseModel):
    """Brave Search web search configuration."""
    api_key: str = Field(default="", description="Brave Search API key")
    enabled: bool = Field(default=False, description="Enable Brave Search")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str, info) -> str:
        if info.data.get('enabled'):
            if not v:
                raise ValueError("Brave Search API key is required when enabled")
            return _validate_api_key_strict(v, "Brave Search")
        return v


class ProviderConfig(BaseModel):
    """Provider configuration."""
    primary: Literal[
        "openrouter", "openai", "anthropic", "minimax", "moonshot",
        "google", "qwen", "zai", "copilot", "vercel", "opencode_zen",
        "xiaomi", "synthetic", "venice", "ollama", "lmstudio"
    ] = "openrouter"
    openrouter: Optional[OpenRouterConfig] = None
    openai: Optional["OpenAIConfig"] = None
    anthropic: Optional["AnthropicConfig"] = None
    minimax: Optional["MiniMaxConfig"] = None
    moonshot: Optional["MoonshotConfig"] = None
    google: Optional["GoogleConfig"] = None
    qwen: Optional["QwenConfig"] = None
    zai: Optional["ZAIConfig"] = None
    copilot: Optional["CopilotConfig"] = None
    vercel: Optional["VercelConfig"] = None
    opencode_zen: Optional["OpenCodeZenConfig"] = None
    xiaomi: Optional["XiaomiConfig"] = None
    synthetic: Optional["SyntheticConfig"] = None
    venice: Optional["VeniceAIConfig"] = None
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
    max_iterations: int = Field(default=50, ge=1, le=50)
    max_tool_calls_per_message: int = Field(default=20, ge=1, le=50)
    context_window: int = Field(default=20, ge=5, le=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_history: int = Field(default=100, ge=10, le=1000)
    mode: Literal["safe", "full_exec"] = Field(
        default="safe",
        description="Execution mode: safe (workspace-restricted) or full_exec (machine-wide)"
    )
    shell_allow_dangerous: bool = Field(
        default=False,
        description="Allow dangerous shell patterns (only meaningful in full_exec mode)"
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, data):
        """Support legacy agent config keys for backward compatibility."""
        if not isinstance(data, dict):
            return data

        # Legacy schema: agent.full_exec: true|false
        if "mode" not in data and "full_exec" in data:
            full_exec = bool(data.get("full_exec"))
            data["mode"] = "full_exec" if full_exec else "safe"
            # Legacy full_exec implied broad shell flexibility.
            if full_exec and "shell_allow_dangerous" not in data:
                data["shell_allow_dangerous"] = True

        # Legacy alias used by some configs/tools.
        if "mode" not in data and "execution_mode" in data:
            data["mode"] = data.get("execution_mode")

        return data


class HeartbeatSettings(BaseModel):
    """Heartbeat settings."""
    enabled: bool = True
    every: Optional[str] = None  # legacy/upstream-style cadence, e.g. "2h"
    active_hours: Optional[str] = None  # legacy/upstream-style hours, e.g. "9-18"
    interval_minutes: int = Field(default=30, ge=10, le=1440)
    quiet_hours_start: int = Field(default=0, ge=0, le=23)
    quiet_hours_end: int = Field(default=0, ge=0, le=23)
    target: Literal["last", "main"] = "last"
    ack_max_chars: int = Field(default=24, ge=1, le=500)
    send_reasoning: bool = False
    proactive_enabled: bool = False
    proactive_queue_path: str = "tasks/QUEUE.md"
    proactive_handoff_dir: str = "memory/proactive"
    proactive_max_turns_per_hour: int = Field(default=4, ge=1, le=60)
    proactive_max_tool_calls_per_cycle: int = Field(default=3, ge=1, le=20)

    @model_validator(mode="after")
    def normalize_legacy_heartbeat_fields(self):
        """Normalize legacy heartbeat fields with compatibility warnings."""
        if self.every:
            try:
                from clawlet.heartbeat.cron_scheduler import parse_interval

                td = parse_interval(str(self.every))
                minutes = max(10, int(td.total_seconds() // 60))
                if minutes != self.interval_minutes:
                    self.interval_minutes = minutes
                    logger.warning(
                        "heartbeat.every is deprecated; normalized to heartbeat.interval_minutes"
                    )
            except Exception:
                logger.warning(
                    f"heartbeat.every='{self.every}' could not be parsed; keeping interval_minutes={self.interval_minutes}"
                )
        if self.active_hours and "-" in str(self.active_hours):
            try:
                start_raw, end_raw = str(self.active_hours).split("-", 1)
                start = int(start_raw.strip()) % 24
                end = int(end_raw.strip()) % 24
                self.quiet_hours_start = end
                self.quiet_hours_end = start
                logger.warning(
                    "heartbeat.active_hours is deprecated; normalized to quiet_hours_start/quiet_hours_end"
                )
            except Exception:
                logger.warning(
                    f"heartbeat.active_hours='{self.active_hours}' could not be parsed; keeping quiet hours unchanged"
                )
        return self


class SchedulerRetrySettings(BaseModel):
    """Retry policy for scheduled tasks."""

    max_attempts: int = Field(default=3, ge=1, le=10)
    delay_seconds: float = Field(default=60.0, ge=0.0, le=86400.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    max_delay_seconds: float = Field(default=3600.0, ge=0.0, le=86400.0)


class SchedulerFailureAlertSettings(BaseModel):
    """Failure alert policy for scheduled tasks."""

    enabled: bool = False
    after: int = Field(default=3, ge=1, le=100)
    cooldown_seconds: int = Field(default=3600, ge=0, le=604800)
    mode: Literal["announce", "webhook"] = "announce"
    channel: str = "scheduler"
    to: str = "main"


class SchedulerTaskConfig(BaseModel):
    """Configuration for one scheduled task."""

    name: str
    action: Literal["agent", "tool", "webhook", "health_check", "skill", "callback"] = "agent"
    enabled: bool = True

    # Routing and execution semantics (upstream-aligned contract).
    agent_id: Optional[str] = None
    session_key: Optional[str] = None
    session_target: Literal["main", "isolated"] = "main"
    wake_mode: Literal["now", "next_heartbeat"] = "now"
    delivery_mode: Literal["announce", "none", "webhook"] = "none"
    delivery_channel: Optional[str] = None
    best_effort_delivery: bool = False
    delete_after_run: bool = False

    # Schedule expression (exactly one may be set).
    cron: Optional[str] = None
    interval: Optional[str] = None  # e.g. "15m", "2h"
    one_time: Optional[str] = None  # ISO-8601
    timezone: str = "UTC"

    # Action parameters
    prompt: Optional[str] = None
    tool: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_method: str = "POST"
    skill: Optional[str] = None
    checks: list[str] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)

    # Scheduling controls
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    depends_on: list[str] = Field(default_factory=list)
    notify_on_success: bool = False
    notify_on_failure: bool = True
    failure_alert: SchedulerFailureAlertSettings = Field(default_factory=SchedulerFailureAlertSettings)
    tags: list[str] = Field(default_factory=list)
    retry: SchedulerRetrySettings = Field(default_factory=SchedulerRetrySettings)

    @model_validator(mode="before")
    @classmethod
    def _normalize_wake_mode_aliases(cls, data):
        """Accept upstream wake-mode spelling and normalize internally."""
        if not isinstance(data, dict):
            return data
        wake_mode = data.get("wake_mode")
        if isinstance(wake_mode, str) and wake_mode.strip().lower() == "next-heartbeat":
            data["wake_mode"] = "next_heartbeat"
        return data

    @model_validator(mode="after")
    def validate_schedule_mode(self):
        """Require at most one schedule mode."""
        schedule_modes = sum([
            self.cron is not None,
            self.interval is not None,
            self.one_time is not None,
        ])
        if schedule_modes > 1:
            raise ValueError(
                f"Task '{self.name}' can only set one of: cron, interval, one_time"
            )
        return self


class SchedulerSettings(BaseModel):
    """Top-level scheduler settings."""

    enabled: bool = False
    timezone: str = "UTC"
    max_concurrent: int = Field(default=3, ge=1, le=64)
    check_interval: int = Field(default=60, ge=1, le=3600)
    state_file: str = "~/.clawlet/scheduler_state.json"
    jobs_file: str = "~/.clawlet/cron/jobs.json"
    runs_dir: str = "~/.clawlet/cron/runs"
    tasks: dict[str, SchedulerTaskConfig] = Field(default_factory=dict)


class RateLimitSettings(BaseModel):
    """Rate limiting settings."""
    enabled: bool = True
    max_entries: int = Field(default=10000, ge=1000, le=100000)
    default_requests_per_minute: int = Field(default=60, ge=1, le=1000)
    tool_requests_per_minute: int = Field(default=30, ge=1, le=500)


class RuntimePolicySettings(BaseModel):
    """Runtime execution policy settings."""

    allowed_modes: list[Literal["read_only", "workspace_write", "elevated"]] = Field(
        default_factory=lambda: ["read_only", "workspace_write"]
    )
    require_approval_for: list[Literal["read_only", "workspace_write", "elevated"]] = Field(
        default_factory=lambda: ["elevated"]
    )
    lanes: dict[Literal["read_only", "workspace_write", "elevated"], str] = Field(
        default_factory=lambda: {
            "read_only": "parallel:read_only",
            "workspace_write": "serial:workspace_write",
            "elevated": "serial:elevated",
        }
    )

    @field_validator("lanes")
    @classmethod
    def _validate_lanes(cls, value: dict[Literal["read_only", "workspace_write", "elevated"], str]):
        required = ("read_only", "workspace_write", "elevated")
        missing = [k for k in required if k not in value]
        if missing:
            raise ValueError(f"runtime.policy.lanes missing keys: {', '.join(missing)}")
        for mode, lane in value.items():
            if not isinstance(lane, str) or not lane.strip():
                raise ValueError(f"runtime.policy.lanes.{mode} must be a non-empty string")
            lane_norm = lane.strip().lower()
            if not (lane_norm.startswith("serial:") or lane_norm.startswith("parallel:")):
                raise ValueError(
                    f"runtime.policy.lanes.{mode} must start with 'serial:' or 'parallel:'"
                )
            value[mode] = lane_norm
        return value


class RuntimeReplaySettings(BaseModel):
    """Replay/event-log settings."""

    enabled: bool = True
    directory: str = ".runtime"
    retention_days: int = Field(default=30, ge=1, le=3650)
    redact_tool_outputs: bool = False
    validate_events: bool = True
    validation_mode: Literal["warn", "error"] = "warn"


class RuntimeRemoteSettings(BaseModel):
    """Remote optional worker settings."""

    enabled: bool = False
    endpoint: str = ""
    timeout_seconds: float = Field(default=60.0, ge=1.0, le=600.0)
    api_key_env: str = "CLAWLET_REMOTE_API_KEY"


class RuntimeSettings(BaseModel):
    """Runtime engine settings."""

    engine: Literal["python", "hybrid_rust"] = "hybrid_rust"
    policy: RuntimePolicySettings = Field(default_factory=RuntimePolicySettings)
    replay: RuntimeReplaySettings = Field(default_factory=RuntimeReplaySettings)
    remote: RuntimeRemoteSettings = Field(default_factory=RuntimeRemoteSettings)
    enable_idempotency_cache: bool = True
    enable_parallel_read_batches: bool = True
    max_parallel_read_tools: int = Field(default=4, ge=1, le=64)
    default_tool_timeout_seconds: float = Field(default=30.0, ge=1.0, le=600.0)
    default_tool_retries: int = Field(default=1, ge=0, le=5)
    outbound_publish_retries: int = Field(default=2, ge=0, le=10)
    outbound_publish_backoff_seconds: float = Field(default=0.5, ge=0.0, le=30.0)


class BenchmarkGatesSettings(BaseModel):
    """Benchmark quality gate thresholds."""

    max_p95_latency_ms: float = Field(default=3000.0, ge=1.0)
    min_tool_success_rate_pct: float = Field(default=99.0, ge=0.0, le=100.0)
    min_deterministic_replay_pass_rate_pct: float = Field(default=98.0, ge=0.0, le=100.0)
    min_lane_speedup_ratio: float = Field(default=1.20, ge=1.0, le=20.0)
    max_lane_parallel_elapsed_ms: float = Field(default=1000.0, ge=1.0)
    min_context_cache_speedup_ratio: float = Field(default=1.05, ge=1.0, le=20.0)
    max_context_cache_warm_ms: float = Field(default=1200.0, ge=1.0)
    min_coding_loop_success_rate_pct: float = Field(default=99.0, ge=0.0, le=100.0)
    max_coding_loop_p95_total_ms: float = Field(default=2500.0, ge=1.0)
    require_rust_equivalence: bool = False


class BenchmarksSettings(BaseModel):
    """Benchmarking config."""

    enabled: bool = True
    gates: BenchmarkGatesSettings = Field(default_factory=BenchmarkGatesSettings)


class PluginSettings(BaseModel):
    """Plugin SDK settings."""

    auto_load: bool = True
    directories: list[str] = Field(default_factory=lambda: ["~/.clawlet/plugins"])
    sdk_version: str = "2.0.0"


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
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    web_search: BraveSearchConfig = Field(default_factory=BraveSearchConfig)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    benchmarks: BenchmarksSettings = Field(default_factory=BenchmarksSettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)
    
    # Track the source file path for reload
    config_path: Optional[Path] = None
    
    def __init__(self, **data):
        # Handle root-level telegram/discord fields by moving them to channels dict
        # This makes the config adaptive to both formats
        if 'channels' not in data:
            data['channels'] = {}
        
        # If telegram is at root level, move it to channels
        if 'telegram' in data:
            if 'telegram' not in data['channels'] or not data['channels'].get('telegram'):
                data['channels']['telegram'] = data['telegram']
            del data['telegram']
        
        # If discord is at root level, move it to channels
        if 'discord' in data:
            if 'discord' not in data['channels'] or not data['channels'].get('discord'):
                data['channels']['discord'] = data['discord']
            del data['discord']

        # Legacy scheduling shape support:
        # - top-level `tasks` -> `scheduler.tasks`
        if 'tasks' in data and 'scheduler' not in data:
            data['scheduler'] = {"tasks": data['tasks']}
            del data['tasks']
        
        super().__init__(**data)
    
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

    def save(self, path: Path) -> None:
        """Backward-compatible alias for writing config to disk."""
        self.to_yaml(path)

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
        
        # Security check: enforce config file permissions (0600)
        try:
            import stat
            st = config_path.stat()
            mode = st.st_mode
            # Check if others have read permission (S_IROTH) or group has any access beyond owner?
            # For simplicity, check if world-readable
            if mode & stat.S_IROTH:
                logger.warning(
                    f"Config file {config_path} is readable by others. "
                    f"Attempting to restrict permissions to 0600."
                )
                try:
                    config_path.chmod(0o600)
                except Exception as chmod_err:
                    logger.error(f"Failed to restrict config permissions: {chmod_err}")
                    raise PermissionError(
                        f"Config file has insecure permissions (octal: {oct(mode)[-3:]}) "
                        f"and could not be fixed. Aborting for security."
                    ) from chmod_err
        except Exception as e:
            logger.debug(f"Could not check config file permissions: {e}")
        
        try:
            from clawlet.config_migration import analyze_config_migration, summarize_migration_hints

            migration_report = analyze_config_migration(config_path)
            if migration_report.issues:
                logger.warning(
                    f"Detected {len(migration_report.issues)} migration-related config issue(s). "
                    "Run `clawlet validate --migration` or `clawlet migrate-config --write`."
                )
                for line in summarize_migration_hints(migration_report, max_items=5):
                    logger.warning(f"Migration hint: {line}")
        except Exception as migration_err:
            logger.debug(f"Migration analysis skipped: {migration_err}")

        config = Config.from_yaml(config_path)
        config.config_path = config_path
        return config
    else:
        logger.warning(f"No config file at {config_path}, using defaults")
        # Create default config with placeholder values
        config = Config(
            provider=ProviderConfig(
                primary="openrouter",
                openrouter=OpenRouterConfig(
                    api_key=os.environ.get("OPENROUTER_API_KEY"),
                ),
            ),
        )
        config.config_path = config_path
        return config


def get_default_config_path() -> Path:
    """Get the default config path."""
    return Path.home() / ".clawlet" / "config.yaml"
