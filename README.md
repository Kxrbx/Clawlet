# 🌸 Clawlet v2 (`0.6.0a8`)

<div align="center">

![Clawlet v2 — one loop, one registry, one SessionDB](docs/assets/clawlet-v2-banner.svg)

**A lightweight AI agent framework with identity awareness**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.6.0a8-magenta.svg)](CHANGELOG.md)

*Your agent now picks the right brain, the right tools, and the right budget — for every single request.*

[Quick Start](#-quick-start) • [What changed from v1](#-v1--v2-what-actually-changed-for-you) • [Per-task models](#-one-agent-many-brains--per-task-models) • [Migration](#-migrating-from-v1) • [Changelog](CHANGELOG.md)

</div>

---

## TL;DR — should you upgrade?

**Yes, if you want a cheaper, safer, more capable agent with zero extra work.**

| v1 | v2 |
|---|---|
| One model for everything | A specialist per task: strong coder for code, cheap/fast model for chat, local model for memory |
| One big toolbox, always fully loaded | Filtered toolboxes per task (`coding`, `browser`, `memory-only`…) — fewer mistakes, lower cost |
| You curate memory by hand | Memory curates itself every 24h, history compresses automatically |
| ~200MB install even for local-only use | Lean core, heavy stuff opt-in (`pip install clawlet[full]` restores the old footprint) |
| Dashboard in the browser, aging CLI menu | Just type `clawlet` — full-screen Sakura TUI with chat, sessions, palette, replay |
| Opaque routing | `clawlet tasks list / show / test-routing` — see exactly which brain handles what |

No database migration. No forced rewrite. Missing `orchestrator` / `task_profiles` sections in your `config.yaml` simply fall back to sensible built-ins.

---

## 🚀 Quick Start

```bash
git clone https://github.com/Kxrbx/Clawlet.git
cd Clawlet
git checkout v2-revamp

pip install -e .          # lean core (local-first, no 200MB of chat SDKs)
# or
pip install -e ".[full]"  # the old all-included v1 footprint
```

```bash
clawlet onboard     # now 8 steps — step 7-8: per-task models
clawlet validate
clawlet             # launches the TUI — no subcommand needed

# or headless / channel mode:
clawlet agent [--channel telegram] [--toolsets coding,browser]
```

Your workspace stays familiar:

```
~/.clawlet/
├── config.yaml
├── SOUL.md / USER.md / MEMORY.md / HEARTBEAT.md
└── memory/
    └── clawlet.db   # sessions + messages + memory, all in one place
```

---

## 🆚 v1 → v2: what actually changed for you

### 1. 🧠 One agent, many brains — per-task models

**Before (v1):** one global `provider.primary` + one model. Your expensive Claude Sonnet answered "ok 👍" and your cheap local model struggled with a refactor. Same brain, every job.

**Now (v2):** every non-trivial message is classified and handed to an **isolated sub-agent** with its own provider, model, tools, and budget. Small talk skips the machinery entirely (fast traced fallback).

9 task kinds, fixed taxonomy, fully overridable:

`code · plan · research · browser · memory · review · ops-tool · chat · scheduled`

Concrete example:

```yaml
provider:
  primary: openrouter
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    model: "anthropic/claude-sonnet-4"

task_profiles:
  code:   {provider: anthropic, model: claude-sonnet-5-20260203, toolset: coding}
  chat:   {provider: openrouter, model: anthropic/claude-haiku-4, toolset: minimal}
  memory: {provider: ollama, model: llama3.2, toolset: memory-only}
```

Result: code gets the strong model, chit-chat gets the cheap one, memory work stays local and free. Sub-agents get a clean slice of history (never your full log), their own budget, and their lineage is recorded — `replay` and sessions show parent → child.

Inspect it live, no network needed:

```bash
clawlet tasks list
clawlet tasks show code
clawlet tasks test-routing "fix the login bug"
```

> Want the details? `docs/runtime-v2.md` is the canonical runtime doc.

### 2. 🧰 Toolsets — the right tools, nothing more

**Before:** the agent always saw everything. More tools = more confusion, more accidental writes, more tokens burned.

**Now:** named views over the same registry. Same tools, filtered per task:

| Toolset | Sees | Used for |
|---|---|---|
| `full` | everything | ops, scheduled jobs (the only one that auto-includes future tools) |
| `coding` | read + write/edit/shell/http + skills | `code` tasks |
| `browser` | fetch / web search / http | `research`, `browser` tasks |
| `minimal` | read-only + read memory + skill list | `plan`, `review`, `chat` |
| `memory-only` | remember / recall / search / curate / status | `memory` tasks |

```bash
clawlet agent --toolsets coding,browser
```

Each profile already declares its toolset, so in practice you configure once and forget it.

### 3. 💾 Memory that maintains itself

**Before:** hybrid memory (SQLite + `MEMORY.md` + daily notes) worked, but *you* had to remember to curate it. Long sessions eventually overflowed.

**Now:**

- **Auto-consolidation (24h):** recent daily notes (`memory/YYYY-MM-DD.md`) are promoted into durable memory on their own. Never breaks your heartbeat tick — failures are logged, not raised.
- **Two-threshold compression:** history compresses by count *or* size (defaults 100 msgs / 200k chars). Big tool outputs are capped first, then a short summary + anchor is kept. No LLM call just to trim.
- **Skills on demand:** instead of stuffing all 50 skills into every prompt, the agent sees a one-line-per-skill index (~630 tokens) and loads the full skill only when needed. More room for *your* conversation.
- **Searchable sessions:** same `clawlet.db`, new `sessions` table (parent lineage, task kind, profile snapshot) + instant full-text `session_search` with fallback when FTS5 is missing. Old `messages` table untouched — nothing to migrate.

Same files, same tools (`remember / recall / search / review / curate / status`), far less babysitting.

### 4. 🪶 Lighter install, faster start

**Before:** `pip install` dragged in Telegram, Discord, Slack, Twilio, Textual… ~200MB even if you only used Ollama locally.

**Now:** lean core (pydantic, YAML, httpx, typer, rich, croniter, aiosqlite…), everything heavy is an extra:

```bash
pip install -e ".[channels-telegram]"
pip install -e ".[channels-discord]"
pip install -e ".[storage-postgres]"
pip install -e ".[tui]"
pip install -e ".[monitoring]"
pip install -e ".[full]"   # v1-style everything
```

Python **3.11+** required (was 3.10+). Under the hood ~1,700 lines of copy-pasted providers were factorized into one `OpenAICompatibleProvider`, duplicate rate limiters merged, dead code dropped (~10k lines total). You feel it as faster `--version`, faster `tools`, fewer weird import errors.

### 5. 🌸 TUI first

**Before:** TUI existed but the CLI menu was the entry point; dashboard lived in the browser (React + FastAPI, separate `npm install`).

**Now:**

- Bare `clawlet` launches the **full-screen Sakura TUI** — chat, sessions, command palette, replay views.
- Web dashboard deleted (7k+ lines gone, frontend + backend). One console to maintain, no second stack.
- CLI culled to what you actually use daily: `onboard / agent / tasks / sessions / cron / heartbeat / replay / recovery / benchmark / health / validate / config / models`.

### 6. 🧭 Onboarding that asks about *how you work*

`clawlet onboard` is now 8 steps: providers, keys, channels, identity… **plus per-task models**. Answer "strong model for code, cheap for chat, local for memory" once, and v2 writes the `task_profiles` section for you.

---

## 📋 Commands

| Command | What it does |
|---|---|
| `clawlet` / `clawlet tui` | Full-screen terminal console |
| `clawlet onboard` / `init` | Guided (8 steps) / quick setup |
| `clawlet agent [--channel telegram] [--toolsets coding,browser]` | Run the runtime |
| `clawlet tasks list / show <kind> / test-routing "<text>"` | **New.** See and test routing offline |
| `clawlet sessions` | List / export stored sessions (with lineage) |
| `clawlet heartbeat status\|last\|enable\|disable` | Heartbeat ops |
| `clawlet replay <run_id>` / `recovery list` | Replay events / resume interrupted runs |
| `clawlet cron list / add / run-now / runs` | Scheduling |
| `clawlet benchmark run` / `corpus` | Perf gates |
| `clawlet health [--deep]` / `validate` / `config` | Diagnostics |

---

## ⚙️ Config reference (minimal v2)

```yaml
provider:
  primary: openrouter
  openrouter: {api_key: "${OPENROUTER_API_KEY}", model: "anthropic/claude-sonnet-4"}

orchestrator:
  max_iterations: 5
  allow_direct_fallback: true
  trivial_max_chars: 200
  classifier_mode: hybrid   # rules | llm | hybrid
  max_depth: 1

task_profiles:
  code: {provider: anthropic, model: claude-sonnet-5-20260203, toolset: coding}

runtime: {engine: python}   # only value accepted in v2
heartbeat: {enabled: true, interval_minutes: 30}
```

Resolution order per request: `task_profiles[<kind>] → task_profiles.defaults → provider.primary`. Anything you omit inherits cleanly — a v1 config without these keys still boots.

---

## 🔄 Migrating from v1

**Breaking, but small:**

1. **Python 3.11+.** Upgrade your interpreter first.
2. **`runtime.engine: hybrid_rust` is gone.** Only `python` is accepted. Edit the key by hand (one line).
3. **Re-install with extras if you need them.** Fresh `pip install -e .` no longer includes Telegram/Discord/Slack/Postgres/TUI-heavy deps. Use `pip install -e ".[full]"` to get the v1 footprint back, or pick à la carte (see above).
4. **Database: nothing to do.** SessionDB tables are created next to your existing `messages`. Your history survives.
5. **Webhooks / web dashboard are gone.** See below.

```bash
clawlet validate   # run this after editing config.yaml — it catches all of the above
```

---

## 🗑️ What was removed — and what to use instead

We deleted ~13k lines. Deliberately. Less code = fewer bugs, faster installs, one maintained path.

| Removed in v2 | Why | Use instead |
|---|---|---|
| Web dashboard (React + FastAPI backend) | Second stack, separate `npm install`, untested | Built-in Sakura **TUI** (`clawlet`) — chat, sessions, palette, replay |
| `clawlet/webhooks/` (GitHub/Stripe/custom server) | Unwired, 1.2k lines, security surface | `http_request` tool + `cron` jobs, or your own tiny forwarder |
| `HeartbeatScheduler` legacy, `AgentRouter` (channel→workspace router) | Replaced | **Orchestrator** (request→task-kind→sub-agent) + `cron_scheduler` |
| `benchmark equivalence`, Rust-bridge, plugin SDK stub, nested READMEs, old migration matrix | Dead / speculative | `benchmark run`, `tasks test-routing`, `release_smoke.py` |
| 17 `create_*_provider` factories, 13 duplicated `*Config` validators, private rate limiters | Duplication | One `provider_factory` + one `APIKeyConfig` + shared `RateLimiter` |
| Unused pins (`openai`, `anthropic`, `twilio`, `tenacity`…) from core | Forced weight | Install via the matching extra only when you use that backend |

Out of scope for v2.0 (v2.1 backlog): 30+ platform gateway, kanban-swarm multi-agents, natural-language cron, Tauri Desktop.

---

## 🤖 Providers

Same 16+ providers you know — OpenRouter, OpenAI, Anthropic, Gemini, Ollama, LM Studio, MiniMax, Moonshot, Qwen, Z.AI, Copilot, Vercel, OpenCode Zen, Xiaomi, Synthetic, Venice — now sharing one codebase, one HTTP pool, and global secret masking. No config change needed on your side.

Local-first still works exactly as before:

```yaml
provider:
  primary: ollama
  ollama: {base_url: "http://localhost:11434", model: "llama3.2"}
```

---

## 📚 Docs

| Doc | For |
|---|---|
| `docs/runtime-v2.md` | **Canonical** v2 runtime (pipeline, profiles, toolsets, SessionDB) |
| `clawlet/ARCHITECTURE.md` | Components + data flow deep dive |
| `docs/skills.md`, `docs/skills-api.md` | Skills system |
| `docs/channels.md`, `docs/scheduling.md` | Channels, cron |
| `QUICKSTART.md`, `DEPLOYMENT.md` | Setup, production |
| `CHANGELOG.md` | Full version history (v2 alpha on top) |
| `PLAN_V2_REVAMP.md` | Implementation tracker (P0–P4 done, 101 tests green) |

---

## 🤝 Contributing

1. Fork → feature branch → commit → push → PR
2. Checks: `pytest` · `python scripts/release_smoke.py` · `python scripts/release_regression.py`

---

## 📄 License & support

MIT — see [LICENSE](LICENSE).

- Issues: [GitHub Issues](https://github.com/Kxrbx/Clawlet/issues)
- Chat: [GitHub Discussions](https://github.com/Kxrbx/Clawlet/discussions)

<div align="center">

Built with 💕 by the Clawlet team · v2: one loop, one registry, one SessionDB.

</div>
