# Clawlet v2 (`0.6.0a0`)

A lightweight AI agent framework with identity awareness — **one loop, one registry, one SessionDB**.

> Branch doc: `docs/runtime-v2.md` is canonical. `PLAN_V2_REVAMP.md` tracks implementation status (P0-P4 done, 101 tests green). Desktop is deferred.

## What v2 changes

- **Always-on orchestrator**: every non-trivial request is classified (hybrid rules + cheap LLM) and delegated to an isolated sub-agent with its own provider/model/toolset/budget. Trivial messages use a traced direct fallback.
- **Per-task profiles**: `code, plan, research, browser, memory, review, ops-tool, chat, scheduled` — each resolves via `task_profiles[kind] → defaults → provider.primary`.
- **Toolsets**: `minimal / coding / browser / memory-only / full` — filtered views over the same registry.
- **SessionDB**: `sessions` table (parent lineage, task kind, profile snapshot, system prompt, source) + FTS5 `session_search` in the same `clawlet.db`.
- **Auto-memory**: 24h consolidation (`curate_from_recent_daily_notes`), 2-threshold history compression, skills progressive disclosure (`name: description` index, on-demand `skill_view`).
- **Lean packaging**: Python ≥3.11, heavy backends opt-in (`channels`, `tui`, `postgres`, …). ~1700 lines of provider duplication removed via `OpenAICompatibleProvider`.

```
Inbound → Orchestrator (classify) → spawn(kind) → child RunOrchestrator → synthesize → outbound
```

## Install

```bash
git checkout v2-revamp
pip install -e .                    # lean core
pip install -e ".[full]"            # old all-included footprint
```

## Quick start

```bash
clawlet onboard     # 8 steps incl. per-task models
clawlet validate
clawlet agent [--channel telegram] [--toolsets coding,browser]

clawlet tasks list
clawlet tasks show code
clawlet tasks test-routing "fix the login bug"   # offline
```

## Config

```yaml
provider:
  primary: openrouter
  openrouter: {api_key: "${OPENROUTER_API_KEY}", model: "anthropic/claude-sonnet-4"}
orchestrator:
  max_iterations: 5
  allow_direct_fallback: true
  trivial_max_chars: 200
  classifier_mode: hybrid
  max_depth: 1
task_profiles:
  code: {provider: anthropic, model: claude-sonnet-5-20260203, toolset: coding}
runtime: {engine: python}
heartbeat: {enabled: true, interval_minutes: 30}
```

## Migration v1 → v2

Breaking: Python 3.11+ required, heavies are extras. DB needs no migration (SessionDB tables sit next to `messages`).

## Commands

| Command | Description |
|---|---|
| `clawlet onboard / init` | setup |
| `clawlet agent` | run runtime |
| `clawlet tasks list/show/test-routing` | profiles + routing |
| `clawlet heartbeat status\|last\|enable\|disable` | heartbeat ops |
| `clawlet replay <run_id>` / `recovery list` | replay / checkpoints |
| `clawlet benchmark run` / `corpus` | perf gates |
| `clawlet validate / health / config` | diagnostics |

## Docs

- `docs/runtime-v2.md` — runtime canonical
- `clawlet/ARCHITECTURE.md` — components + data flow
- `docs/skills.md`, `docs/skills-api.md`, `docs/channels.md`, `docs/scheduling.md`
- `QUICKSTART.md`, `DEPLOYMENT.md`, `CHANGELOG.md`

Out of scope for v2.0: 30+ platform gateway, kanban-swarm, NL cron, Tauri Desktop.
