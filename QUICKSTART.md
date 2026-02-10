# Quick Start Guide

## First Time Setup

### Option 1: Interactive Onboarding (Recommended)

The easiest way to set up Clawlet:

```bash
clawlet onboard
```

This will guide you through:
1. Choosing your AI provider
2. Configuring API keys or local models
3. Setting up messaging channels
4. Customizing your agent's personality
5. Creating your workspace

### Option 2: Quick Init

For a fast setup with defaults:

```bash
clawlet init
```

Then manually edit `~/.clawlet/config.yaml` to add your API keys.

---

## Provider Setup

### OpenRouter (Cloud - Recommended)

1. Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys)
2. Run `clawlet onboard` and select OpenRouter
3. Paste your API key when prompted

### Ollama (Local - Free)

1. Install Ollama: [ollama.ai](https://ollama.ai)
2. Pull a model: `ollama pull llama3.2`
3. Start Ollama: `ollama serve`
4. Run `clawlet onboard` and select Ollama

### LM Studio (Local - Free)

1. Install LM Studio: [lmstudio.ai](https://lmstudio.ai)
2. Load a model in LM Studio
3. Enable the local server (port 1234)
4. Run `clawlet onboard` and select LM Studio

---

## Channel Setup

### Telegram

1. Open Telegram and search for @BotFather
2. Send `/newbot` and follow the instructions
3. Copy the bot token
4. Run `clawlet onboard` and enable Telegram

### Discord

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" and create a bot
4. Copy the token
5. Run `clawlet onboard` and enable Discord

---

## Running Your Agent

```bash
# Start with default channel
clawlet agent

# Start with specific channel
clawlet agent --channel telegram
clawlet agent --channel discord

# Use a different model
clawlet agent --model anthropic/claude-sonnet-4
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `clawlet onboard` | Interactive guided setup |
| `clawlet init` | Quick setup with defaults |
| `clawlet agent` | Start the agent |
| `clawlet status` | Show workspace status |
| `clawlet health` | Run health checks |
| `clawlet validate` | Validate config |
| `clawlet config` | View configuration |
| `clawlet --help` | Show all commands |

---

## File Structure

After setup, your workspace (`~/.clawlet/`) contains:

```
~/.clawlet/
├── config.yaml      # Main configuration
├── SOUL.md          # Agent personality
├── USER.md          # Your information
├── MEMORY.md        # Long-term memory
├── HEARTBEAT.md     # Periodic tasks
└── memory/          # Memory storage
    └── *.db         # SQLite database
```

---

## Customizing Your Agent

### SOUL.md

Edit this file to change your agent's personality:

```markdown
# SOUL.md - Who You Are

## Name
MyAgent

## Personality
- Friendly and helpful
- Good at coding
- Loves terrible puns
```

### USER.md

Tell your agent about yourself:

```markdown
# USER.md - About Your Human

## Name
Alex

## Timezone
America/New_York

## Notes
- Working on a Python project
- Prefers concise answers
- Loves coffee
```

---

## Troubleshooting

### "Cannot connect to Ollama"

Make sure Ollama is running:
```bash
ollama serve
```

### "API key invalid"

Check your config:
```bash
clawlet config provider.openrouter.api_key
```

### "Agent not responding"

Run health checks:
```bash
clawlet health
```

---

## Need Help?

- **Docs**: [github.com/Kxrbx/Clawlet](https://github.com/Kxrbx/Clawlet)
- **Issues**: [GitHub Issues](https://github.com/Kxrbx/Clawlet/issues)
- **Chat**: [GitHub Discussions](https://github.com/Kxrbx/Clawlet/discussions)
