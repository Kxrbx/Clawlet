# Quick Start Guide

Get up and running with Clawlet in minutes.

---

## First Time Setup

### Option 1: Interactive Onboarding (Recommended)

The easiest way to set up Clawlet:

```bash
clawlet onboard
```

This will guide you through:
1. Choosing your AI provider (18+ options)
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

Clawlet supports **18+ LLM providers**. Choose what fits your needs:

### Cloud Providers

#### OpenRouter (Recommended - 100+ models)

1. Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys)
2. Run `clawlet onboard` and select OpenRouter
3. Paste your API key when prompted

**Popular models:**
- `anthropic/claude-sonnet-4-20250514`
- `openai/gpt-4o`
- `google/gemini-2.0-flash-exp`

#### OpenAI

1. Get an API key at [platform.openai.com](https://platform.openai.com/api-keys)
2. Run `clawlet onboard` and select OpenAI
3. Paste your API key

**Popular models:**
- `gpt-4o`
- `gpt-4o-mini`
- `o1-preview`

#### Anthropic (Claude)

1. Get an API key at [console.anthropic.com](https://console.anthropic.com)
2. Run `clawlet onboard` and select Anthropic
3. Paste your API key

**Popular models:**
- `claude-sonnet-5-20260203`
- `claude-haiku-5-20250501`

#### Google Gemini

1. Get an API key at [aistudio.google.com](https://aistudio.google.com/app/apikey)
2. Run `clawlet onboard` and select Google
3. Paste your API key

**Popular models:**
- `gemini-2.0-flash-exp`
- `gemini-1.5-pro`

#### MiniMax

1. Get an API key at [platform.minimax.chat](https://platform.minimax.chat)
2. Run `clawlet onboard` and select MiniMax
3. Paste your API key

**Default model:** `abab7-preview`

#### Moonshot (Kimi)

1. Get an API key at [platform.moonshot.ai](https://platform.moonshot.ai)
2. Run `clawlet onboard` and select Moonshot
3. Paste your API key

**Default model:** `kimi-k2.5`

#### Qwen (Alibaba)

1. Get an API key at [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com)
2. Run `clawlet onboard` and select Qwen
3. Paste your API key

**Default model:** `qwen-turbo`

#### Z.AI (GLM)

1. Get an API key at [open.bigmodel.cn](https://open.bigmodel.cn)
2. Run `clawlet onboard` and select Z.AI
3. Paste your API key

**Default model:** `glm-4`

#### GitHub Copilot

1. Get your token from [github.com/settings/tokens](https://github.com/settings/tokens)
2. Run `clawlet onboard` and select Copilot
3. Paste your token

#### Vercel AI

1. Get an API key at [vercel.com](https://vercel.com)
2. Run `clawlet onboard` and select Vercel
3. Paste your API key

#### OpenCode Zen

1. Get an API key at [opencode.com](https://opencode.com)
2. Run `clawlet onboard` and select OpenCode Zen
3. Paste your API key

#### Xiaomi AI

1. Get an API key from Xiaomi AI platform
2. Run `clawlet onboard` and select Xiaomi
3. Paste your API key

#### Synthetic AI

1. Get an API key at [synthetic.ai](https://synthetic.ai)
2. Run `clawlet onboard` and select Synthetic
3. Paste your API key

#### Venice AI

1. Get an API key at [venice.ai](https://venice.ai)
2. Run `clawlet onboard` and select Venice AI
3. Paste your API key

**Note:** Venice AI provides uncensored models.

---

### Local Providers (Free)

#### Ollama

1. Install Ollama: [ollama.ai](https://ollama.ai)
2. Pull a model: `ollama pull llama3.2`
3. Start Ollama: `ollama serve`
4. Run `clawlet onboard` and select Ollama

**Default model:** `llama3.2`

#### LM Studio

1. Install LM Studio: [lmstudio.ai](https://lmstudio.ai)
2. Load a model in LM Studio
3. Enable the local server (port 1234)
4. Run `clawlet onboard` and select LM Studio

---

## Web Search Setup

Enable Brave Search for web search capabilities:

1. Get an API key at [brave.com/search/api](https://brave.com/search/api/)
2. Run `clawlet onboard` and enable web search
3. Paste your API key

Or add manually to `config.yaml`:

```yaml
web_search:
  api_key: "YOUR_BRAVE_SEARCH_API_KEY"
  enabled: true
```

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
clawlet agent --model anthropic/claude-sonnet-4-20250514

# Start dashboard
clawlet dashboard
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `clawlet onboard` | Interactive guided setup |
| `clawlet init` | Quick setup with defaults |
| `clawlet agent` | Start the agent |
| `clawlet dashboard` | Launch web dashboard |
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

### "Cannot connect to LM Studio"

Make sure the local server is enabled in LM Studio (port 1234).

### "Web search not working"

Verify Brave Search API key is set:
```bash
clawlet config web_search.api_key
```

---

## Need Help?

- **Docs**: [github.com/Kxrbx/Clawlet](https://github.com/Kxrbx/Clawlet)
- **Issues**: [GitHub Issues](https://github.com/Kxrbx/Clawlet/issues)
- **Chat**: [GitHub Discussions](https://github.com/Kxrbx/Clawlet/discussions)
