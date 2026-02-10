# Changelog

All notable changes to Clawlet will be documented in this file.

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
- Additional tools (web scraping, code execution)
- Skill system for extensions
- Vector database integration
- Multi-agent orchestration
- Streaming responses in CLI
- Better error recovery
- More test coverage (target 80%)
