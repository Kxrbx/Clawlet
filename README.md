# 🦞 Clawlet

A lightweight AI agent framework with identity awareness, inspired by OpenClaw but designed for simplicity and speed.

## Features

- **Identity-aware**: Reads and understands its own SOUL.md, USER.md, MEMORY.md, HEARTBEAT.md files
- **Lightweight**: ~1.8k lines of code, optimized for small hardware (Pi, VPS)
- **Multi-channel**: Telegram, Discord support
- **Multi-provider**: OpenRouter, Ollama, LM Studio
- **Memory system**: SQLite + PostgreSQL support with automatic consolidation
- **Tools**: File operations, shell execution, web search (Brave API)
- **Tool calling**: Iterative tool execution with function calling support
- **Heartbeat**: Periodic task scheduler for proactive behavior
- **Web dashboard**: React + Tailwind + shadcn/ui for agent management
- **Fast startup**: <50ms CLI startup time

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/Kxrbx/Clawlet.git
cd Clawlet
pip install -e .

# Or install from PyPI (coming soon)
pip install clawlet
```

### Initialize Workspace

```bash
# Create workspace with identity files
clawlet init

# This creates ~/.clawlet/ with:
# - SOUL.md (who your agent is)
# - USER.md (who they're helping)  
# - MEMORY.md (long-term memories)
# - HEARTBEAT.md (periodic tasks)
# - config.yaml (configuration)
```

### Configure

Edit `~/.clawlet/config.yaml` with your API keys:

```yaml
provider:
  primary: openrouter
  openrouter:
    api_key: "YOUR_API_KEY"
    model: "anthropic/claude-sonnet-4"
  
  # Ollama (local)
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.2"
  
  # LM Studio (local, OpenAI-compatible)
  lmstudio:
    base_url: "http://localhost:1234"
    model: "local-model"

channels:
  telegram:
    enabled: true
    token: "YOUR_BOT_TOKEN"
  
  discord:
    enabled: true
    token: "YOUR_DISCORD_BOT_TOKEN"
```

### Run

```bash
# Start the agent
clawlet agent

# With specific channel
clawlet agent --channel telegram

# Check status
clawlet status
```

## Identity System

Clawlet's unique feature is its identity system. Edit the markdown files to customize your agent:

### SOUL.md
Define who the agent is, their personality, values, and communication style.

### USER.md  
Tell the agent about yourself - name, timezone, preferences, projects.

### MEMORY.md
Long-term memories that persist across sessions. Updated automatically.

### HEARTBEAT.md
Define periodic tasks the agent should perform (e.g., check emails, review calendar).

## Architecture

```
clawlet/
├── agent/
│   ├── identity.py        # Load SOUL.md, USER.md, etc.
│   ├── loop.py          # Core agent loop with tool calling
│   └── memory.py         # Memory management (coming soon)
├── channels/
│   ├── base.py            # Base channel interface
│   ├── telegram.py        # Telegram integration
│   └── discord.py         # Discord integration
├── tools/
│   ├── registry.py         # Tool registry
│   ├── files.py           # Read/write/list files
│   ├── shell.py           # Execute shell commands (safe)
│   └── web_search.py      # Web search via Brave API
├── providers/
│   ├── base.py            # Base provider interface
│   ├── openrouter.py       # OpenRouter API
│   ├── ollama.py          # Ollama (local)
│   └── lmstudio.py        # LM Studio (local)
├── storage/
│   ├── sqlite.py           # SQLite backend
│   └── postgres.py         # PostgreSQL backend
├── heartbeat/
│   └── scheduler.py       # Periodic task scheduler
├── bus/
│   └── queue.py           # Message bus
├── cli/
│   └── commands.py        # CLI commands
└── dashboard/
    ├── src/
    │   ├── App.tsx            # React app
    │   └── components/ui/  # UI components
    └── package.json
```

## Comparison

| Feature | Clawlet | Nanobot | Tinyclaw | OpenClaw |
|---------|---------|---------|----------|----------|
| Identity Files | ✅ | ❌ | ❌ | ✅ |
| Size | ~1.8k lines | ~8.5k | ~500 | 430k+ |
| Pi-Friendly | ✅ | ✅ | ✅ | ❌ |
| Dashboard | ✅ | ❌ | ❌ | ⚠️ |
| Ollama | ✅ | ❌ | ❌ | ✅ |
| LM Studio | ✅ | ❌ | ❌ | ❌ |
| Discord | ✅ | ❌ | ❌ | ✅ |
| Tool Calling | ✅ | ❌ | ❌ | ✅ |
| Heartbeat | ✅ | ❌ | ❌ | ✅ |
| Memory System | ✅ | ⚠️ | ❌ | ✅ |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black clawlet

# Type check
mypy clawlet
```

## License

MIT

## Links

- **GitHub**: https://github.com/Kxrbx/Clawlet
- **Documentation**: https://docs.clawlet.ai (coming soon)
- **Demo Dashboard**: https://dashboard.clawlet.ai (coming soon)

---

Built with 💕 by the Clawlet team
- Inspired by [OpenClaw](https://github.com/openclaw/openclaw)
- Similar to [Nanobot](https://github.com/kalebhf/nanobot) but simpler
