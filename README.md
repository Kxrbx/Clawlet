# 🦞 Clawlet

A lightweight AI agent framework with identity awareness.

## Features

- **Identity-aware**: Reads and understands its own SOUL.md, USER.md, MEMORY.md, HEARTBEAT.md files
- **Lightweight**: ~5k lines of code, optimized for small hardware (Pi, VPS)
- **Multi-channel**: Telegram, Discord, WhatsApp support
- **Memory system**: SQLite + PostgreSQL support with automatic consolidation
- **Tools**: File operations, shell execution, web search, subagent spawning
- **Heartbeat**: Periodic task execution for proactive behavior

## Quick Start

### Installation

```bash
# Install from source
git clone https://github.com/clawlet/clawlet.git
cd clawlet
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

channels:
  telegram:
    enabled: true
    token: "YOUR_BOT_TOKEN"
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
│   ├── identity.py    # Load SOUL.md, USER.md, etc.
│   ├── loop.py        # Core agent loop
│   └── memory.py      # Memory management
├── channels/
│   ├── telegram.py    # Telegram integration
│   └── discord.py     # Discord integration
├── tools/
│   ├── files.py       # Read/write/edit files
│   └── shell.py       # Execute commands
├── storage/
│   └── sqlite.py      # SQLite backend
├── bus/
│   └── queue.py       # Message bus
└── cli/
    └── commands.py    # CLI commands
```

## Comparison

| Feature | Clawlet | Nanobot | Tinyclaw | OpenClaw |
|---------|---------|---------|----------|----------|
| Identity Files | ✅ | ❌ | ❌ | ✅ |
| Size | ~5k lines | ~8.5k | ~500 | 430k+ |
| Pi-Friendly | ✅ | ✅ | ✅ | ❌ |
| Dashboard | ✅ | ❌ | ❌ | ⚠️ |
| Ollama | ✅ | ❌ | ❌ | ✅ |
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

- **Website**: https://clawlet.ai
- **Documentation**: https://docs.clawlet.ai
- **GitHub**: https://github.com/clawlet/clawlet
- **Discord**: https://discord.gg/clawlet

---

Built with 💜 by the Clawlet team
