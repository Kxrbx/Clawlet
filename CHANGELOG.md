# Changelog

All notable changes to Clawlet will be documented in this file.

## [Unreleased]

### Added
- **Brave Search API Support**: Added optional Brave Search API integration for web searches. Users can now enable web search during onboarding or add it later via settings. Configure via `web_search.api_key` in config.yaml or `BRAVE_SEARCH_API_KEY` environment variable.

## [0.1.1] - 2026-02-13

### Added
- **New LLM Providers**:
  - Anthropic (Claude) API support
  - OpenAI API support
  - Google Gemini API support
  - MiniMax API support
  - Moonshot AI (Kimi) API support
  - Qwen (Alibaba) API support
  - Z.AI (GLM) API support
  - GitHub Copilot API support
  - Vercel AI Gateway support
  - OpenCode Zen API support
  - Xiaomi AI API support
  - Synthetic AI API support
  - Venice AI API support (uncensored models)
- **Models Cache System** - Daily auto-updating cache for provider models with disk persistence
- **Enhanced Dashboard**:
  - Console logs panel
  - Health history charts
  - Status badges
  - Real-time agent management (start/stop)
  - Settings configuration UI
  - Full config.yaml editor
  - Models browser with cache info
- **Heartbeat Scheduler Enhancements**:
  - Priority levels for tasks (HIGH, MEDIUM, LOW)
  - State persistence (save/load)
  - Daily models cache update task
- **TokenBucket Rate Limiting** - Additional algorithm for more flexible rate limiting

### Improved
- Expanded provider factory functions in `clawlet/providers/__init__.py`
- More comprehensive health checks with detailed provider/storage status
- Extended configuration options for all new providers

## [0.1.0] - 2026-02-10

### Added
- Initial release of Clawlet framework
- Identity system (SOUL.md, USER.md, MEMORY.md, HEARTBEAT.md)
- Multiple LLM providers:
  - OpenRouter API
  - Ollama (local LLM)
  - LM Studio (local LLM)
- Multiple channel integrations:
  - Telegram
  - Discord
- Storage backends:
  - SQLite (default)
  - PostgreSQL
- Tools system:
  - File operations (read/write/edit/list)
  - Shell commands (secured against injection)
  - Web search (Brave API)
- Message bus for inter-channel communication
- Agent loop with tool calling support
- Health check system
- Rate limiting (sliding window + token bucket)
- Configuration with Pydantic validation
- Custom exception hierarchy
- Retry logic with exponential backoff
- Circuit breaker pattern
- CLI commands:
  - init - Initialize workspace
  - agent - Start agent
  - status - Show status
  - health - Run health checks
  - validate - Validate config
  - config - View/configure
- Web dashboard (React + Tailwind)
- Dashboard API (FastAPI)

### Security
- Shell tool blocks dangerous patterns (pipes, redirects, subshells)
- Uses safe subprocess execution methods
- Command parsing with shlex.split()

### Documentation
- Comprehensive README with quick start
- Configuration examples
- API documentation
- Security notes
- Comparison with OpenClaw/nanobot

## [Unreleased]

### Planned
- Dashboard real-time agent management
- More channels (WhatsApp, Slack, Signal)
- Vector database integration
- Multi-agent orchestration
- Streaming responses
- Better error recovery
