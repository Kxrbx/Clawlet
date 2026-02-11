# 🦞 Clawlet

<div align="center">

**A lightweight AI agent framework with identity awareness**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub release](https://img.shields.io/github/v/release/Kxrbx/Clawlet?include_prereleases)](https://github.com/Kxrbx/Clawlet/releases)

*Build AI agents that know who they are*

[Quick Start](#-quick-start) • [Features](#-features) • [Documentation](#-documentation) • [Examples](#-examples)

</div>

---

## Why Clawlet?

Clawlet is a **lightweight** alternative to OpenClaw/nanobot, designed for developers who want:

- 🏠 **Local-First** - Run Ollama or LM Studio, no cloud required
- 🎭 **Identity Awareness** - Agents read SOUL.md, USER.md, MEMORY.md
- 🔧 **Simple Setup** - Interactive onboarding in under 2 minutes
- 📊 **Built-in Dashboard** - React UI for monitoring and management
- 🔒 **Security-First** - Hardened shell tool, safe command execution

## ✨ Features

### Core
- **Identity System** - Define your agent's personality, values, and memory
- **Multiple LLM Providers** - OpenRouter, Ollama, LM Studio
- **Persistent Memory** - SQLite (default) or PostgreSQL
- **Tool System** - File ops, shell commands, web search

### Infrastructure
- **Health Checks** - Monitor providers, storage, channels
- **Rate Limiting** - Sliding window + token bucket algorithms
- **Config Validation** - Pydantic-based with environment variable support
- **Retry Logic** - Exponential backoff with circuit breaker

### Channels
- **Telegram** - Bot integration
- **Discord** - Bot integration

### Dashboard
- **React + Tailwind UI** - Modern, responsive design
- **FastAPI Backend** - RESTful API with OpenAPI docs
- **Real-time Monitoring** - Health, logs, agent status

## 🚀 Quick Start

### Install

```bash
# Clone
git clone https://github.com/Kxrbx/Clawlet.git
cd Clawlet

# Install
pip install -e .

# Optional: Dashboard dependencies
pip install -e ".[dashboard]"
```

### Interactive Setup (Recommended)

```bash
clawlet onboard
```

This 5-step wizard guides you through:
1. **Choose Provider** - OpenRouter, Ollama, or LM Studio
2. **Configure** - API keys or local settings
3. **Channels** - Telegram/Discord setup
4. **Identity** - Name and personality
5. **Create Workspace** - All files generated

### Or Quick Init

```bash
clawlet init
# Edit ~/.clawlet/config.yaml with your settings
```

### Start Your Agent

```bash
# Start agent
clawlet agent --channel telegram

# Or start dashboard
clawlet dashboard
```

## 📋 CLI Commands

| Command | Description |
|---------|-------------|
| `clawlet onboard` | Interactive guided setup ✨ |
| `clawlet init` | Quick setup with defaults |
| `clawlet agent` | Start the AI agent |
| `clawlet dashboard` | Launch web dashboard |
| `clawlet status` | Show workspace status |
| `clawlet health` | Run health checks |
| `clawlet validate` | Validate configuration |
| `clawlet config [key]` | View configuration |
| `clawlet --version` | Show version |

## 📁 Project Structure

```
~/.clawlet/              # Your workspace
├── config.yaml          # Main configuration
├── SOUL.md              # Agent personality
├── USER.md              # Your information
├── MEMORY.md            # Long-term memory
├── HEARTBEAT.md         # Periodic tasks
└── memory/
    └── clawlet.db       # SQLite database
```

## ⚙️ Configuration

### OpenRouter (Cloud)

```yaml
provider:
  primary: openrouter
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    model: "anthropic/claude-sonnet-4"
```

### Ollama (Local - Free)

```yaml
provider:
  primary: ollama
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.2"
```

```bash
# Start Ollama
ollama serve
ollama pull llama3.2
```

### LM Studio (Local - Free)

```yaml
provider:
  primary: lmstudio
  lmstudio:
    base_url: "http://localhost:1234"
```

Enable the local server in LM Studio (port 1234).

## 🎨 Customizing Your Agent

### SOUL.md - Agent Personality

```markdown
# SOUL.md

## Name
MyAgent

## Personality
- Friendly and helpful
- Good at explaining complex topics
- Loves terrible puns

## Values
1. Helpfulness - Always try to be useful
2. Honesty - Be clear about limitations
3. Privacy - Respect user data
```

### USER.md - About You

```markdown
# USER.md

## Name
Alex

## Timezone
America/New_York

## Notes
- Working on Python projects
- Prefers concise answers
- Coffee enthusiast
```

## 📊 Dashboard

Launch the web dashboard:

```bash
clawlet dashboard
```

**URLs:**
- Frontend: http://localhost:5173
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

**Features:**
- System health overview
- Agent management
- Real-time console
- Settings configuration

## 🔒 Security

Clawlet takes security seriously:

- **Shell Tool Hardening** - 15+ dangerous patterns blocked
- **Safe Execution** - Uses `create_subprocess_exec()` not shell
- **Command Parsing** - `shlex.split()` for safe arguments
- **Rate Limiting** - Prevent API overload
- **Config Validation** - Pydantic ensures safe configs

Blocked patterns: `|`, `>`, `<`, `$()`, `&&`, `||`, `;`, backticks, and more.

## 🏗️ Architecture

```
clawlet/
├── agent/           # Identity, loop, memory
├── bus/             # Message bus
├── channels/        # Telegram, Discord
├── providers/       # OpenRouter, Ollama, LM Studio
├── storage/         # SQLite, PostgreSQL
├── tools/           # Files, shell, web search
├── dashboard/       # React + FastAPI
├── config.py        # Pydantic validation
├── health.py        # Health checks
├── rate_limit.py    # Rate limiting
├── exceptions.py    # Custom exceptions
└── retry.py         # Retry + circuit breaker
```

## 📈 Comparison

| Feature | Clawlet | OpenClaw | nanobot |
|---------|---------|----------|---------|
| Language | Python | TypeScript | Python |
| Local LLMs | ✅ Ollama, LM Studio | ❌ | ❌ |
| Dashboard | ✅ React + FastAPI | ✅ | ❌ |
| Identity System | ✅ SOUL/USER/MEMORY | ✅ | ❌ |
| Health Checks | ✅ | ✅ | ❌ |
| Rate Limiting | ✅ | ❌ | ❌ |
| Storage | SQLite + PostgreSQL | SQLite + PostgreSQL | SQLite |
| Interactive Onboarding | ✅ | ✅ | ❌ |

## 🤝 Contributing

Contributions welcome!

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE)

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/Kxrbx/Clawlet/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Kxrbx/Clawlet/discussions)

---

<div align="center">

Built with 💕 by the Clawlet team

[⬆ Back to Top](#-clawlet)

</div>
