"""Workspace template content helpers for CLI initialization."""

from __future__ import annotations


def get_soul_template() -> str:
    return """# SOUL.md - Who You Are

This file defines your agent's core identity, personality, and values.

## Name
Clawlet

## Purpose
I am a lightweight AI assistant designed to be helpful, honest, and harmless.

## Personality
- Warm and supportive
- Clear and concise
- Curious and eager to help
- Respectful of boundaries

## Values
1. **Helpfulness**: I strive to provide genuinely useful assistance
2. **Honesty**: I'm truthful about my capabilities and limitations
3. **Privacy**: I respect your data and never share it inappropriately
4. **Growth**: I learn from our interactions to become better

## Communication Style
- Use emojis sparingly but warmly
- Be direct when needed, gentle when appropriate
- Ask clarifying questions when uncertain
- Celebrate wins together

---

_This file is yours to customize. Make your agent unique!_
"""


def get_user_template() -> str:
    return """# USER.md - About Your Human

Tell your agent about yourself so it can help you better.

## Name
[Your name]

## What to call you
[Preferred name/nickname]

## Pronouns
[Optional]

## Timezone
[Your timezone, e.g., UTC, America/New_York]

## Notes
- What do you care about?
- What projects are you working on?
- What annoys you?
- What makes you laugh?

---

_The more your agent knows, the better it can help!_
"""


def get_memory_template() -> str:
    return """# MEMORY.md - Long-Term Memory

This file stores important memories that persist across sessions.

## Key Information
- Add important facts here
- Decisions made
- Lessons learned
- Things to remember

## Recent Updates
- [Date] Initial setup

---

_Memories are consolidated from daily notes automatically._
"""


def get_heartbeat_template() -> str:
    return """# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.
"""


def get_queue_template() -> str:
    return """# QUEUE.md - Proactive Task Queue

- [ ] [P1] Review pending alerts and triage critical blockers.
- [ ] [P2] Improve one small reliability issue in the current workspace.
- [ ] [P3] Clean up stale notes and summarize progress.
"""


def get_config_template() -> str:
    return """# Clawlet Configuration

# LLM Provider Settings
provider:
  # Primary provider: openrouter, ollama, lmstudio
  primary: ollama

  # Example OpenRouter settings:
  # openrouter:
  #   api_key: "${OPENROUTER_API_KEY}"
  #   model: "anthropic/claude-sonnet-4"
  
  # Ollama settings (local)
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.2"
  
  # LM Studio settings (local)
  lmstudio:
    base_url: "http://localhost:1234"
    model: "local-model"

# Channel Settings
channels:
  telegram:
    enabled: false
    token: ""
    stream_mode: "progress"
    stream_update_interval_seconds: 1.5
    disable_web_page_preview: true
    use_reply_keyboard: true
    register_commands: true
  
  discord:
    enabled: false
    token: ""
  
  whatsapp:
    enabled: false

# Storage Settings
storage:
  # backend: sqlite or postgres
  backend: sqlite
  
  # SQLite settings
  sqlite:
    path: "~/.clawlet/clawlet.db"
  
  # PostgreSQL settings
  postgres:
    host: "localhost"
    port: 5432
    database: "clawlet"
    user: "clawlet"
    password: ""

# Optional structured HTTP auth profiles
# http_auth_profiles:
#   example_service:
#     bearer_token_path: ".config/example_service/credentials.json"
#     env_var: "EXAMPLE_SERVICE_TOKEN"
#     header_name: "Authorization"
#     header_prefix: "Bearer "

# Agent Settings
agent:
  max_iterations: 50
  max_tool_calls_per_message: 20
  context_window: 20
  temperature: 0.7
  mode: safe
  shell_allow_dangerous: false

# Heartbeat Settings
heartbeat:
  enabled: true
  interval_minutes: 30
  quiet_hours_start: 0  # disabled when start == end
  quiet_hours_end: 0    # disabled when start == end
  target: "last"        # "last" or "main"
  ack_max_chars: 24
  send_reasoning: false
  proactive_enabled: false
  proactive_queue_path: "tasks/QUEUE.md"
  proactive_handoff_dir: "memory/proactive"
  proactive_max_turns_per_hour: 4
  proactive_max_tool_calls_per_cycle: 3

# Scheduler Settings (cron/interval jobs)
scheduler:
  enabled: false
  timezone: "UTC"
  max_concurrent: 3
  check_interval: 60
  state_file: "~/.clawlet/scheduler_state.json"
  jobs_file: "~/.clawlet/cron/jobs.json"
  runs_dir: "~/.clawlet/cron/runs"
  tasks:
    daily_summary:
      name: "Daily Summary"
      action: "agent"
      cron: "0 18 * * *"
      timezone: "UTC"
      session_target: "main"
      wake_mode: "now"
      delivery_mode: "announce"
      prompt: "Generate a concise summary of today's activity."
      priority: "normal"
      retry:
        max_attempts: 3
        delay_seconds: 60
        backoff_multiplier: 2.0
        max_delay_seconds: 3600

# Runtime v2 Settings
runtime:
  engine: python
  enable_idempotency_cache: true
  enable_parallel_read_batches: true
  max_parallel_read_tools: 4
  default_tool_timeout_seconds: 30
  default_tool_retries: 1
  outbound_publish_retries: 2
  outbound_publish_backoff_seconds: 0.5
  policy:
    allowed_modes: [read_only, workspace_write]
    require_approval_for: [elevated]
    lanes:
      read_only: "parallel:read_only"
      workspace_write: "serial:workspace_write"
      elevated: "serial:elevated"
  replay:
    enabled: true
    directory: ".runtime"
    retention_days: 30
    redact_tool_outputs: false
    validate_events: true
    validation_mode: "warn"
  remote:
    enabled: false
    endpoint: ""
    timeout_seconds: 60
    api_key_env: "CLAWLET_REMOTE_API_KEY"

# Benchmarks + hard quality gates
benchmarks:
  enabled: true
  gates:
    max_p95_latency_ms: 3000
    min_tool_success_rate_pct: 99.0
    min_deterministic_replay_pass_rate_pct: 98.0
    min_lane_speedup_ratio: 1.20
    max_lane_parallel_elapsed_ms: 1000
    min_context_cache_speedup_ratio: 1.05
    max_context_cache_warm_ms: 1200
    min_coding_loop_success_rate_pct: 99.0
    max_coding_loop_p95_total_ms: 2500

# Plugin SDK v2
plugins:
  auto_load: true
  directories:
    - "~/.clawlet/plugins"
  sdk_version: "2.0.0"
"""
