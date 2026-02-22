# Changelog

All notable changes to Clawlet will be documented in this file.

## [0.2.5] - 2026-02-22

### Features

- **Dashboard Error Handling**: Added ErrorBoundary component for graceful error handling in the React dashboard, preventing entire app crashes from component errors.

### Refactoring

- **Rate Limiting Enhancement**: Added automatic cleanup of stale entries and configurable maximum total entries to prevent memory growth from long-running agents.

- **Telegram Message Formatting**: Enhanced message sending with MarkdownV2 fallback support, providing better formatting options for Telegram bot messages.

- **SQLite Path Expansion**: Expanded SQLite path configuration to support user home directory (`~`) expansion for easier database file placement.

### Maintenance

- **Environment Variables Support**: Updated `.gitignore` to include environment variable files (`.env`) for safer local development.

- **Dashboard API Base URL**: Updated API base URL configuration for improved flexibility in different deployment environments.

## [0.2.4] - 2026-02-22

### Features

- **Memory Persistence**: Added memory persistence with periodic saves to maintain agent state across sessions. Memory is saved every 5 iterations during execution and persisted on agent shutdown for session continuity.

### Refactoring

- **Config Schema Migration**: Migrated from nested `channels:` dictionary to individual top-level fields for each channel (telegram, discord, whatsapp, slack). Also adds web_search configuration support with automatic migration logic for legacy config files.

- **Tool Call Execution**: Simplified tool call execution in agent loop by removing complex regex-based parsing. Added confirmation parameter to `Workspace.delete()` to prevent accidental deletions.

### Dependencies

- **New CLI Dependencies**: Added [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/) for improved interactive CLI experiences.
- **FastAPI Integration**: Added FastAPI and Questionary dependencies for enhanced API and interactive prompt support.

### Maintenance

- **Project Configuration**: Added `pyproject.toml` for standardized Python project configuration.
- **CLI Entry Point**: Updated CLI entry point from `main` to `app` for consistency.
- **Encoding Fix**: Explicitly specified UTF-8 encoding when reading identity files (USER.md, MEMORY.md, HEARTBEAT.md).

### Documentation

- **Visual Branding**: Added logo image to README for improved visual presentation.

## [0.2.3] - 2026-02-19

### Refactoring

- **Config Consolidation**: Created `APIKeyConfig` base class to eliminate code duplication across 14+ provider configurations. Reduced config.py by ~19% (~123 lines).

- **CLI Modularization**: Split monolithic CLI (`__init__.py` - 1441 lines) into modular command files:
  - New `clawlet/cli/commands/` directory with 10 command modules
  - Reduced main CLI file to 156 lines (89% reduction)
  - Improved maintainability and navigation

- **Tool Call Parser Extraction**: Created `clawlet/agent/tool_parser.py` to unify regex-based tool call extraction patterns. Simplified `agent/loop.py` by delegating to reusable parser class.

### Maintenance

- **Backward Compatibility**: Added `Config` alias and `load_config()` function to maintain API compatibility for external consumers

## [0.2.2] - 2026-02-18

### Security

- **Path Traversal Fix**: Added symlink attack protection in file tools using `resolve(strict=True)` to prevent attackers from escaping allowed directories via symlinks
- **Tool Rate Limiting**: Added rate limiting to tool execution (10 calls per minute per tool) to prevent resource exhaustion attacks

### Stability

- **Graceful Shutdown**: Added SIGTERM/SIGINT signal handlers to agent loop for proper cleanup on system shutdown
- **Discord Error Handling**: Added try/catch to Discord message handler to prevent bot crashes from processing errors
- **Slack Socket Mode Cleanup**: Fixed daemon thread cleanup to ensure proper graceful shutdown of Slack connections

### Configuration

- **Workspace Config Isolation**: Fixed workspace config sharing bug where modifying workspace config would affect parent config

### Maintenance

- **Model Names Updated**: Updated OpenAI provider to use valid model names (removed non-existent gpt-5, o3)

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


