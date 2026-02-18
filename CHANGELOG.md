# Changelog

All notable changes to Clawlet will be documented in this file.

## [0.2.1] - 2026-02-18

### Security

- **Fixed ReDoS Vulnerability**: Replaced vulnerable regex pattern in tool call extraction with safer JSON parsing to prevent catastrophic backslash
- **Error Message Sanitization**: Improved error handling to prevent internal details from being exposed to users. All exceptions now return generic user-friendly messages while logging detailed errors internally.
- **Input Validation**: Added comprehensive input validation across all modules:
  - Inbound message validation (100KB max, content sanitization)
  - Tool parameter validation (type checking, schema validation)
  - Webhook payload validation (10MB max, UTF-8 validation)
- **Dashboard API Authentication**: Added optional API key authentication (`X-API-Key` header) to protect dashboard endpoints

### Performance

- **HTTP Connection Pooling**: Added shared connection pool for LLM providers with configurable limits (100 max connections, 20 keepalive)
- **Memory Management**: Improved agent history memory management with:
  - 10KB max per message
  - 1MB total history limit
  - Automatic truncation of oversized tool results
  - Memory usage tracking and statistics

### Features

- **Outbound Rate Limiting**: Added outbound message rate limiting with sliding window algorithm (20/minute, 100/hour per chat)
- **ValidationError Exception**: Added new exception class with validation helpers for consistent input validation

## [0.2.0] - 2026-02-14

### Added
- **Brave Search API Support**: Added optional Brave Search API integration for web searches. Users can now enable web search during onboarding or add it later via settings. Configure via `web_search.api_key` in config.yaml or `BRAVE_SEARCH_API_KEY` environment variable.
- **Interactive AI Model Selection**: Added interactive AI model selection and management command for easier model switching.
- **Dynamic OpenRouter Model Selection**: Enhanced OpenRouter model selection with caching for better performance.
- **Dashboard API Abstraction Layer**: Added API abstraction layer and connected Settings persistence.

### Improved
- **Sakura Theme Dashboard**: Major UI/UX improvements with Sakura theme, real-time API integration, health history chart, live console, and React Query.
- **CLI Enhancements**: Automatically start frontend dev server with dashboard command.
- **Error Handling**: Resolved asyncio.run conflict in async onboarding and moved CircuitBreakerOpen exception to dedicated exceptions module.

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


