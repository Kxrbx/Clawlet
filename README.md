# 🌸 Clawlet

<div align="center">
<img width="256" height="256" alt="Clawlet logo" src="https://github.com/user-attachments/assets/de0343fb-ad04-4563-896b-686a375c9721" />

**A lightweight AI agent framework with identity awareness**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub release](https://img.shields.io/github/v/release/Kxrbx/Clawlet?include_prereleases)](https://github.com/Kxrbx/Clawlet/releases)

*Build AI agents that know who they are*

[Quick Start](#-quick-start) • [Features](#-features) • [Documentation](#-documentation) • [Providers](#-llm-providers) • [v0.2.7](#-v027---2026-02-22)

</div>

---


<div align="center">
<img width="809" height="475" alt="{28F593B5-58B5-49E8-A1D7-5C88E563726B}" src="https://github.com/user-attachments/assets/1d01fabc-7ddc-4f64-8b35-a279e4ad981f" />
</div>


## Why Clawlet?

Clawlet is a **lightweight** alternative to OpenClaw/nanobot, designed for developers who want:

- 🏠 **Local-First** - Run Ollama or LM Studio, no cloud required
- 🎭 **Identity Awareness** - Agents read SOUL.md, USER.md, MEMORY.md
- 🔧 **Simple Setup** - Interactive onboarding in under 2 minutes
- 📊 **Built-in Dashboard** - React UI for monitoring and management
- 🔒 **Security-First** - Hardened shell tool, safe command execution
- 🌐 **Web Search** - Brave Search API integration for up-to-date information
- 🔌 **Skills System** - Modular capabilities with OpenClaw-compatible SKILL.md format

## ✨ Features

### Core
- **Identity System** - Define your agent's personality, values, and memory
- **18+ LLM Providers** - Cloud and local options for every budget
- **Persistent Memory** - SQLite (default) or PostgreSQL
- **Tool System** - File ops, shell commands, web search
- **Models Cache** - Daily auto-updating cache with disk persistence
- **Skills System** - Extend agent capabilities with modular skills

### Infrastructure
- **Health Checks** - Monitor providers, storage, channels
- **Rate Limiting** - Sliding window + token bucket algorithms
- **Config Validation** - Pydantic-based with environment variable support
- **Retry Logic** - Exponential backoff with circuit breaker
- **Webhooks** - Receive events from GitHub, Stripe, and custom sources
- **Scheduling** - Cron-based task scheduling with timezone support

### Channels
- **Telegram** - Bot integration
- **Discord** - Bot integration
- **WhatsApp** - Business API integration
- **Slack** - Socket Mode and HTTP integration

### Multi-Agent
- **Workspace Management** - Isolated agent environments
- **Message Routing** - Route messages to appropriate agents
- **Specialized Agents** - Configure agents for specific tasks

### Dashboard
- **React + Tailwind UI** - Modern Sakura-themed design
- **FastAPI Backend** - RESTful API with OpenAPI docs
- **Real-time Monitoring** - Health history charts, console logs
- **Agent Management** - Start/stop agents, view status
- **Settings UI** - Full config editor with models browser


---

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
1. **Choose Provider** - 18+ providers available
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

---

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

---

## 🤖 LLM Providers

Clawlet supports **18+ LLM providers** giving you flexibility in choice and pricing.

### Cloud Providers

| Provider | API | Description |
|----------|-----|-------------|
| **OpenRouter** | [openrouter.ai](https://openrouter.ai) | Aggregates 100+ models, pay-as-you-go |
| **OpenAI** | [openai.com](https://openai.com) | GPT-4o, GPT-4o mini, o1 series |
| **Anthropic** | [anthropic.com](https://anthropic.com) | Claude 4 (Sonnet, Haiku) |
| **Google Gemini** | [ai.google](https://ai.google.dev) | Gemini 2.0 Flash, Pro |
| **MiniMax** | [minimax.chat](https://www.minimax.chat) | Chinese AI, competitive pricing |
| **Moonshot (Kimi)** | [moonshot.ai](https://www.moonshot.ai) | Kimi k2.5, strong reasoning |
| **Qwen (Alibaba)** | [qwen.ai](https://qwen.ai) | Open-source friendly |
| **Z.AI (GLM)** | [zhipuai.cn](https://www.zhipuai.cn) | ChatGLM series |
| **GitHub Copilot** | [github.com](https://github.com/features/copilot) | Code-focused models |
| **Vercel AI** | [vercel.com](https://vercel.com/ai) | AI SDK Gateway |
| **OpenCode Zen** | [opencode.com](https://opencode.com) | Code generation |
| **Xiaomi** | [xiaomi.ai](https://xiaomi.ai) | Mi AI |
| **Synthetic AI** | [synthetic.ai](https://synthetic.ai) | Specialized models |
| **Venice AI** | [venice.ai](https://venice.ai) | Uncensored models |

### Local Providers (Free)

| Provider | Description |
|----------|-------------|
| **Ollama** | Run llama3.2, mistral, codellama locally |
| **LM Studio** | Desktop app for loading GGUF models |

### Example Configuration

#### OpenRouter (Recommended for variety)

```yaml
provider:
  primary: openrouter
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    model: "anthropic/claude-sonnet-4-20250514"
```

#### OpenAI (Direct)

```yaml
provider:
  primary: openai
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o"
```

#### Anthropic (Claude)

```yaml
provider:
  primary: anthropic
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-sonnet-5-20260203"
```

#### Ollama (Local - Free)

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

#### LM Studio (Local - Free)

```yaml
provider:
  primary: lmstudio
  lmstudio:
    base_url: "http://localhost:1234"
```

Enable the local server in LM Studio (port 1234).

---

## 🌐 Web Search

Clawlet integrates with **Brave Search API** for web search capabilities:

```yaml
web_search:
  api_key: "${BRAVE_SEARCH_API_KEY}"
  enabled: true
```

Get your API key at [brave.com/search/api](https://brave.com/search/api/).

---

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

---

## 🎨 Exemples of Customizing Your Agent

### SOUL.md - Agent Personality

```markdown
# SOUL.md

## Names
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

---

## 📊 Dashboard (WIP)

Launch the web dashboard:

```bash
clawlet dashboard
```

**URLs:**
- Frontend: http://localhost:5173
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

**Features:**
- System health overview with history charts
- Real-time agent management
- Live console logs
- Settings configuration UI
- Full config.yaml editor
- Models browser with cache info

---

## 🔒 Security

Clawlet takes security seriously:

- **Shell Tool Hardening** - 15+ dangerous patterns blocked
- **Safe Execution** - Uses `create_subprocess_exec()` not shell
- **Command Parsing** - `shlex.split()` for safe arguments
- **Rate Limiting** - Prevent API overload
- **Config Validation** - Pydantic ensures safe configs

Blocked patterns: `|`, `>`, `<`, `$()`, `&&`, `||`, `;`, backticks, and more.

---

## 🏗️ Architecture

```
clawlet/
├── agent/           # Identity, loop, memory, router, workspace
├── bus/             # Message bus
├── channels/        # Telegram, Discord, WhatsApp, Slack
├── providers/       # 18+ LLM providers
├── skills/          # Skills system with bundled skills and templates
├── webhooks/        # GitHub, Stripe, custom webhooks
├── heartbeat/       # Scheduling and periodic tasks
├── storage/         # SQLite, PostgreSQL
├── tools/           # Files, shell, web search
├── dashboard/       # React + FastAPI
├── config.py        # Pydantic validation
├── health.py        # Health checks
├── rate_limit.py    # Rate limiting
├── exceptions.py    # Custom exceptions
└── retry.py         # Retry + circuit breaker
```

---

## 📈 Features Overview

| Feature | Description |
|---------|-------------|
| LLM Providers | 18+ cloud and local providers |
| Local LLMs | Ollama, LM Studio (free) |
| Dashboard | React + FastAPI with Sakura theme | WIP
| Identity System | SOUL/USER/MEMORY files |
| Health Checks | Monitor providers, storage, channels |
| Rate Limiting | Sliding window + token bucket |
| Storage | SQLite + PostgreSQL |
| Web Search | Brave Search API |
| Models Cache | Daily auto-updating with disk persistence |
| Interactive Onboarding | 5-step guided setup |
| Skills System | Modular capabilities with SKILL.md |
| Webhooks | GitHub, Stripe, custom integrations |
| Scheduling | Cron-based task automation |
| Multi-Agent | Workspace isolation and routing |

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Skills Documentation](docs/skills.md) | Create and manage modular skills |
| [Skills API Reference](docs/skills-api.md) | Technical API documentation |
| [Channels Documentation](docs/channels.md) | Telegram, Discord, WhatsApp, Slack |
| [Webhooks Documentation](docs/webhooks.md) | GitHub, Stripe, custom webhooks |
| [Scheduling Documentation](docs/scheduling.md) | Cron expressions and task scheduling |
| [Multi-Agent Documentation](docs/multi-agent.md) | Workspace management and routing |
| [Quick Start Guide](QUICKSTART.md) | Get started quickly |
| [Deployment Guide](DEPLOYMENT.md) | Production deployment |

---

## 🤝 Contributing

Contributions welcome!

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Open a Pull Request

---

---

## 📝 v0.2.7 - 2026-02-22

### Latest Updates
- **CORS Configuration**: Environment variable support for custom CORS origins (`CLAWLET_CORS_ORIGINS`)
- **API Security**: Optional API key enforcement for dashboard access (`CLAWLET_REQUIRE_API_KEY`)
- **Health Monitoring**: Configurable health history lines via `CLAWLET_MAX_HEALTH_HISTORY_LINES`
- **OpenAI OAuth**: Added OAuth flow support for OpenAI provider authentication
- **LM Studio**: Improved timeout handling for reliable local LLM connections
- **UI Updates**: Enhanced button component styling variants

### Previous Versions
See [CHANGELOG.md](CHANGELOG.md) for complete version history.

---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/Kxrbx/Clawlet/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Kxrbx/Clawlet/discussions)

---

<div align="center">

Built with 💕 by the Clawlet team

[⬆ Back to Top](#-clawlet)

</div>
