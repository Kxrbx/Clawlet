# 🦞 Clawlet

A lightweight AI agent framework with identity awareness. Built as an alternative to OpenClaw/nanobot with a focus on simplicity, local-first support, and extensibility.

## Features

- **Identity System** - Agents read SOUL.md, USER.md, MEMORY.md to understand who they are
- **Multiple LLM Providers** - OpenRouter, Ollama, LM Studio support out of the box
- **Local-First** - Works with local models via Ollama or LM Studio
- **Multiple Channels** - Telegram, Discord integrations
- **Persistent Memory** - SQLite (default) or PostgreSQL backends
- **Health Checks** - Monitor provider, storage, and system health
- **Rate Limiting** - Built-in protection against API overload
- **Web Dashboard** - React + Tailwind UI for monitoring and management

## Quick Start

### Option 1: Interactive Onboarding (Recommended)

```bash
# Clone the repo
git clone https://github.com/Kxrbx/Clawlet.git
cd Clawlet

# Install with pip
pip install -e .

# Run interactive onboarding
clawlet onboard
```

This guides you through:
- Choosing your AI provider
- Setting up API keys or local models
- Configuring messaging channels
- Customizing your agent's personality

### Option 2: Quick Init

```bash
# Initialize with defaults
clawlet init

# Edit config
~/.clawlet/config.yaml

# Start agent
clawlet agent
```

### Configure Provider

Edit `~/.clawlet/config.yaml`:

```yaml
# For OpenRouter (recommended for best results)
provider:
  primary: openrouter
  openrouter:
    api_key: "your-openrouter-api-key"
    model: "anthropic/claude-sonnet-4"

# Or for local models with Ollama
provider:
  primary: ollama
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.2"
```

### Start Agent

```bash
# Start with Telegram
clawlet agent --channel telegram

# Or Discord
clawlet agent --channel discord
```

## Configuration

### Providers

#### OpenRouter

```yaml
provider:
  primary: openrouter
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"  # Use env var
    model: "anthropic/claude-sonnet-4"
```

#### Ollama (Local)

```yaml
provider:
  primary: ollama
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.2"
```

Make sure Ollama is running:
```bash
ollama serve
ollama pull llama3.2
```

#### LM Studio (Local)

```yaml
provider:
  primary: lmstudio
  lmstudio:
    base_url: "http://localhost:1234"
```

Enable the local server in LM Studio (port 1234 by default).

### Channels

#### Telegram

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get the bot token
3. Add to config:

```yaml
channels:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
```

#### Discord

1. Create a bot in Discord Developer Portal
2. Get the bot token
3. Add to config:

```yaml
channels:
  discord:
    enabled: true
    token: "${DISCORD_BOT_TOKEN}"
```

### Storage

#### SQLite (Default)

```yaml
storage:
  backend: sqlite
  sqlite:
    path: "~/.clawlet/clawlet.db"
```

#### PostgreSQL

```yaml
storage:
  backend: postgres
  postgres:
    host: "localhost"
    port: 5432
    database: "clawlet"
    user: "clawlet"
    password: "${POSTGRES_PASSWORD}"
```

## CLI Commands

```bash
# Initialize workspace
clawlet init

# Start agent
clawlet agent

# Check status
clawlet status

# Run health checks
clawlet health

# Validate configuration
clawlet validate

# View config
clawlet config

# Show version
clawlet --version
```

## Architecture

```
clawlet/
├── agent/
│   ├── identity.py    # Load SOUL.md, USER.md, MEMORY.md
│   ├── loop.py        # Main agent loop with tool calling
│   └── memory.py      # Memory management
├── bus/
│   └── queue.py       # Message bus for channels
├── channels/
│   ├── base.py        # Base channel interface
│   ├── telegram.py    # Telegram integration
│   └── discord.py     # Discord integration
├── providers/
│   ├── base.py        # Base provider interface
│   ├── openrouter.py  # OpenRouter API
│   ├── ollama.py      # Ollama local LLM
│   └── lmstudio.py    # LM Studio local LLM
├── storage/
│   ├── sqlite.py      # SQLite backend
│   └── postgres.py    # PostgreSQL backend
├── tools/
│   ├── registry.py    # Tool registry
│   ├── files.py       # File operations
│   ├── shell.py       # Shell commands (secured)
│   └── web_search.py  # Brave search
├── config.py          # Configuration with validation
├── health.py          # Health check system
├── rate_limit.py      # Rate limiting
├── exceptions.py      # Custom exceptions
└── retry.py           # Retry utilities
```

## Security

The shell tool has multiple security layers:

- **Pattern blocking** - Dangerous patterns (pipes, redirects, subshells) are blocked
- **Safe execution** - Uses `create_subprocess_exec()` not `create_subprocess_shell()`
- **Command parsing** - Uses `shlex.split()` for safe argument parsing

Blocked patterns include: `|`, `>`, `<`, `$()`, `&&`, `||`, `;`, backticks, and more.

## Dashboard

The web dashboard provides monitoring and management:

```bash
cd dashboard
npm install
npm run dev
```

Features:
- System health overview
- Agent management
- Real-time console
- Settings configuration

## Development

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=clawlet

# Specific test file
pytest tests/test_shell_security.py
```

### Code Style

We use:
- **Black** for formatting
- **isort** for import sorting
- **mypy** for type checking

```bash
black clawlet tests
isort clawlet tests
mypy clawlet
```

## Comparison with OpenClaw/nanobot

| Feature | Clawlet | OpenClaw | nanobot |
|---------|---------|----------|---------|
| Language | Python | TypeScript | Python |
| Local LLMs | ✅ Ollama, LM Studio | ❌ | ❌ |
| Dashboard | ✅ React | ✅ | ❌ |
| Identity System | ✅ | ✅ | ❌ |
| Health Checks | ✅ | ✅ | ❌ |
| Rate Limiting | ✅ | ❌ | ❌ |
| Postgres + SQLite | ✅ | ✅ | SQLite only |

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## Support

- **Issues**: [GitHub Issues](https://github.com/Kxrbx/Clawlet/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Kxrbx/Clawlet/discussions)

---

Built with 💕 by the Clawlet team.
