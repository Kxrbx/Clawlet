# Clawlet v2 — Runtime (`0.6.0a8`)

> One loop, one registry, one SessionDB. Every non-trivial request goes through
> `Orchestrator → sub-agent(kind) → synthesis`. Desktop is out of scope (deferred).

## Pipeline

```
Inbound → Orchestrator (hybrid classify, 0-5 iters, tools OFF)
  → trivial (<200 chars, no action-intent)? direct parent turn (traced fallback:true)
  → else spawn(kind): fresh AgentLoop, resolved profile, history = instruction + slice, never the full history
  → RunOrchestrator(child).process_message (no re-delegation, max_depth=1)
  → synthesize → outbound (+ task_kind / child_session_id)
```

Modules: `agent/orchestrator.py` (`decide/dispatch/process_message`),
`agent/task_router.py` (sync rules + cheap LLM micro-classifier + cache, never raises),
`agent/subagent.py` (spawn, depth guard), `agent/run_orchestrator.py` (kept as forwarder).

## Per-task profiles

Fixed yet overridable taxonomy: `code, plan, research, browser, memory, review, ops-tool, chat, scheduled`.

Resolution: `task_profiles[kind] → task_profiles.defaults → global provider.primary`.
Each profile is a full execution contract (provider, model, toolset, max_iterations, tool_call_limit, timeout_s, temperature, fallback).

Defaults: `code=coding/50/20`, `plan=minimal/15/8`, `research=browser/25/15`,
`browser=browser/20/12`, `memory=memory-only/10/6`, `review=minimal/10/6`,
`ops-tool=full/15/10`, `chat=minimal/5/4`, `scheduled=full/20/10`.

```yaml
orchestrator:
  max_iterations: 5
  allow_direct_fallback: true
  trivial_max_chars: 200
  classifier_mode: hybrid  # rules | llm | hybrid
  max_depth: 1
task_profiles:
  code: {provider: anthropic, model: claude-sonnet-5-20260203, toolset: coding}
```

CLI:

```bash
clawlet tasks list
clawlet tasks show code
clawlet tasks test-routing "fix the login bug"   # offline, no network
clawlet onboard   # steps 7-8: per-task models
clawlet validate
```

## Toolsets

Named views over the same registry (`tools/toolsets.py`), not different code:

| Toolset | Contents |
|---|---|
| `full` | everything (only one accepting unknown future tools) |
| `minimal` | read-only + read memory + `list_skills` |
| `coding` | minimal + `write/edit/apply_patch/shell/http_request` + `install_skill` |
| `browser` | `fetch_url/web_search/http_request` |
| `memory-only` | `remember/recall/search/recent/review/curate/status` |

`clawlet --toolsets coding,browser` loads a filtered registry view.

## SessionDB

Same `clawlet.db`, new tables, backward compatible (`messages` untouched):

- `sessions(session_id, parent_session_id, task_kind, profile_snapshot, system_prompt, source, created_at)` — parent→child lineage written best-effort on every spawn.
- `messages_fts`: FTS5 index for LLM-free `session_search` (~ms vs ~30s), `LIKE` fallback when FTS5 is missing. WAL + `synchronous=NORMAL` + FKs like `SQLiteStorage`.
- Code: `storage/session_db.py` (`SessionStore.session_search`).

## Context, compression, auto-memory

- `HistoryTrimmer`: 2 thresholds (count OR chars, default 100 msgs / 200k chars). Tool outputs capped first (2000c cap, no LLM call), then compressed `system` summary (60 lines max, 180c excerpts) + preserved anchor, deduplicated.
- `memory_maintenance.maybe_run_memory_maintenance`: 24h slow loop, `curate_from_recent_daily_notes` → durable memory, state in `maintenance-state.json`, never raises (never breaks the heartbeat tick).
- Same hybrid-memory idea: SQLite as durable source, `MEMORY.md` as curated projection, `memory/YYYY-MM-DD.md` episodic notes (`remember/recall/search/recent/review/curate/status`).
- Progressive-disclosure skills (`skills/index.py`): the stable prompt carries only the `name: description` index (~630 tokens / 50 skills, 2000 budget, 120c/line), full content on demand via `skill_view`, keyword matching without LLM.

## Providers & lean packaging

- `OpenAICompatibleProvider` (`providers/openai_compat.py`): 1 class for the 10 near-identical ones (minimax, moonshot, qwen, zai, copilot, vercel, opencode_zen, xiaomi, synthetic, venice) — only `BASE_URL/default_model` differ. ~1700 lines removed.
- `provider_factory.py`: single `(name, model, config)` path shared by CLI/orchestrator/dashboard. Shared HTTP pool sized via public config. Global `mask_secrets`.
- Python ≥3.11. Lean core, heavy stuff in extras (`channels-*`, `tui`, `postgres`, `providers-openai/anthropic`, …). Guarded `python-telegram-bot` import. Lazy `clawlet.agent`, CLI-free `clawlet/paths.py` (cycle fixes).

## v1 → v2 migration (full-break, no shim)

- `runtime.engine: hybrid_rust` removed (only `python` accepted; update the key by hand).
- `orchestrator` / `task_profiles` sections optional (built-ins apply when absent).
- DB: nothing to migrate, SessionDB tables are created next to `messages`.

## Useful commands

```bash
clawlet agent [--channel telegram] [--toolsets coding,browser]
clawlet heartbeat status|last|enable|disable
clawlet replay <run_id> --signature --verify
clawlet recovery list
clawlet benchmark run --workspace <path>
python scripts/release_smoke.py
```

## Out of scope for v2.0 (v2.1 backlog)

30+ platform gateway, kanban-swarm multi-agents, natural-language cron, Tauri Desktop (D0-D4 deferred).
