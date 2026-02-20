# Clawlet 🤖🌸

> A lightweight AI agent framework with identity awareness. Build autonomous agents that know who they are.

![Python](https://img.shields.io/badge/Python-%3E%3D3.10-blue?logo=python)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-0.1.0-orange.svg)

---

## 📑 Table of Contents
- [✨ Features](#-features)
- [📋 Prerequisites](#-prerequisites)
- [🚀 Installation](#-installation)
- [⚡ Usage](#-usage)
- [🗂️ Project Structure](#️-project-structure)
- [🧩 Core Modules](#-core-modules)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## ✨ Features

- 🔐 **Identity Awareness** – Agents have persistent identity via `IdentityLoader`
- 🧠 **Agent Loop** – Async event loop with health checks and rate limiting
- 💾 **Memory Management** – Pluggable storage backends for context persistence
- ⚙️ **Configuration** – YAML-based config with sensible defaults
- 🛡️ **Health & Resilience** – Circuit breakers, retries, rate limiters built-in
- 📡 **Multi-channel** – Support for various messaging providers (extensible)
- 🎨 **Beautiful CLI** – Typer + Rich with sakura-themed output
- 📝 **Structured Logging** – Loguru integration for production-grade logs

---

## 📋 Prerequisites

- **Python** >= 3.10
- **pip** (for dependencies)
- Optional: `uv` or `poetry` for dependency management

---

## 🚀 Installation

### From source (development)

```bash
# Clone the repository
git clone https://github.com/yourorg/clawlet.git
cd clawlet

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate

# Install dependencies (if requirements.txt exists)
pip install -r requirements.txt

# Or install in editable mode
pip install -e .
```

### As a package (once published)

```bash
pip install clawlet
```

---

## ⚡ Usage

### CLI

```bash
# Show help
python -m clawlet --help

# Run agent
python -m clawlet run --config path/to/config.yaml

# Health check
python -m clawlet health

# Interactive mode
python -m clawlet repl
```

### As a library

```python
from clawlet import AgentLoop, Config, IdentityLoader

# Load config
config = Config.load("config.yaml")

# Initialize identity
identity = IdentityLoader.load_from_file("identity.json")

# Create agent loop
loop = AgentLoop(config, identity)

# Run
asyncio.run(loop.start())
```

---

## 🗂️ Project Structure

```
clawlet/
├── agent/               # Core agent logic
│   ├── identity.py      # Identity loading & validation
│   ├── loop.py          # Main event loop
│   └── memory.py        # Memory/storage backend
├── bus/                 # Event bus (pub/sub)
├── channels/            # Channel adapters (Telegram, Discord, etc.)
├── cli/                 # CLI commands (Typer app)
│   ├── __init__.py      # Main CLI entry point
│   └── onboard.py       # Onboarding wizard
├── config.py            # Configuration management
├── dashboard/           # Web dashboard (optional)
├── exceptions.py        # Custom exception hierarchy
├── health.py            # Health checks & monitoring
├── heartbeat/           # Heartbeat system
├── nanobot/             # Nanobot agent implementation
├── providers/           # LLM provider adapters (OpenAI, Anthropic, etc.)
├── rate_limit.py        # Rate limiting utilities
├── retry.py             # Retry logic with backoff
├── storage/             # Storage backends (filesystem, database)
├── tools/               # Agent tools & plugins
├── __init__.py          # Package exports
├── __main__.py          # Entry point for `python -m clawlet`
└── README.md            # This file
```

---

## 🧩 Core Modules

### `agent.identity.IdentityLoader`
Loads agent identity from JSON file (name, persona, preferences). Ensures required fields are present.

### `agent.loop.AgentLoop`
Main async loop that:
- Fetches messages from channels
- Runs the agent's reasoning step
- Posts replies
- Handles errors with retries & circuit breakers

### `agent.memory.MemoryManager`
Abstracted storage interface with implementations:
- `FileMemory` – JSON file storage
- `SQLiteMemory` – SQLite backend (coming soon)
- `RedisMemory` – Redis backend (coming soon)

### `config.Config`
YAML configuration with defaults for:
- Channels (enabled/disabled, API keys)
- Rate limits per provider
- Health check intervals
- Logging settings

### `health.HealthChecker`
Async health monitoring:
- Checks all channels every N seconds
- Alerts on failures
- Integrates with external monitoring (optional)

### `rate_limit.RateLimiter`
Token bucket algorithm for provider rate limiting. Supports per-provider limits and burst capacity.

---

## 🎨 CLI Commands

| Command | Description |
|---------|-------------|
| `run` | Start the agent loop |
| `health` | Run health checks and exit |
| `repl` | Interactive agent session |
| `onboard` | First-time setup wizard |
| `config` | Validate & view configuration |
| `version` | Show version info |

---

## 🔧 Configuration

Create a `config.yaml` in your workspace:

```yaml
# config.yaml
workspace: "~/.clawlet"

channels:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
  discord:
    enabled: false

providers:
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    base_url: "https://openrouter.ai/api/v1"
    model: "openrouter/anthropic/claude-3.5-sonnet"

rate_limits:
  openrouter:
    requests_per_minute: 30

logging:
  level: "INFO"
  format: "{time} {level} {message}"
```

Environment variables are supported via `${VAR_NAME}` syntax.

---

## 🧪 Development Workflow

1. **Make changes** in a module
2. **Run tests** (if present): `pytest tests/`
3. **Check health**: `python -m clawlet health`
4. **Run agent**: `python -m clawlet run --config examples/dev.yaml`
5. **Format code**: `ruff format .`
6. **Lint**: `ruff check .`

---

## 📦 Dependencies

### Runtime
- `typer` – CLI framework
- `rich` – terminal formatting
- `loguru` – logging
- `pydantic` – config validation
- `pyyaml` – YAML parsing
- `aiohttp` – async HTTP (for providers)
- `asyncio` – async runtime (stdlib)

### Optional
- `redis` – Redis storage backend
- `sqlalchemy` – SQLite/Postgres storage
- `telegram` – python-telegram-bot
- `discord.py` – Discord integration

See `requirements.txt` (or create one) for exact versions.

---

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Write tests for new functionality
4. Ensure CI passes (`ruff format`, `ruff check`, `pytest`)
5. Submit a Pull Request

### Code Style
- Format with `ruff format .`
- Lint with `ruff check .` (fix automatically where possible)
- Type hints required for public functions
- Docstrings in Google style

---

## 📄 License

MIT – see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with love by the Clawlet team. Inspired by agent frameworks like AutoGPT, LangChain, and BabyAGI, but designed to be simpler, more identity-aware, and production-resilient out of the box.
