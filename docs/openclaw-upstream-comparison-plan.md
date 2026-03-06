# Clawlet vs OpenClaw (Upstream) - Implementation Backlog

Date: 2026-03-05
Baseline compared: `https://github.com/openclaw/openclaw` (upstream main) + official docs

## Progress Update (2026-03-05)

- Phase 0: completed
- Phase 1: completed
- Phase 2: completed
  - cron scheduler dependency injection + scheduler metadata contract + unit tests implemented
  - durable scheduler job persistence implemented (`jobs_file`)
  - per-job run logs implemented (`runs_dir/*.jsonl`) with path-safety guard for job ids
  - operator CLI implemented for `clawlet cron list` and `clawlet cron run-now`
  - `wake_mode=next_heartbeat` staging implemented (flushed via heartbeat tick hook)
  - `delivery_mode` execution implemented (`none`, `announce`, `webhook`)
  - run history now persists delivery outcome separately (`delivery_status`, `delivery_error`)
  - operator commands added: `clawlet cron runs`, `clawlet cron add`, `clawlet cron pause`, `clawlet cron resume`
  - operator commands added: `clawlet cron edit`, `clawlet cron remove`
  - `cron runs` now supports all-jobs scope + pagination/filters (`--all`, `--offset`, `--limit`, status filters)
  - `cron add` now supports richer job fields (retry policy, priority, dependencies, tags, params-json)
  - runtime agent command now starts scheduler service when `scheduler.enabled=true`
  - upstream check aligned against OpenClaw CLI/service patterns:
    - `src/cli/cron-cli/register.cron-add.ts`
    - `src/cli/cron-cli/register.cron-simple.ts`
    - `src/gateway/protocol/schema/cron.ts`
    - `src/cron/service.delivery-plan.test.ts`
    - `src/gateway/server-cron.ts`
    - `src/cli/cron-cli/register.cron-edit.ts`

- Phase 3: completed (initial queue-backed proactive loop + guardrails + handoff artifacts)
  - proactive queue worker reads `tasks/QUEUE.md`
  - bounded dispatch guardrails (`max_turns_per_hour`, `max_tool_calls_per_cycle`)
  - daily proactive handoff artifacts (`memory/proactive/YYYY-MM-DD.md`)
  - metrics integration for proactive completions

- Phase 4: completed (observability + health surfaces)
  - dashboard endpoint `GET /automation/status` implemented
  - health automation checks for repeated failures/backlog growth
  - metrics counters added for scheduled runs attempted/succeeded/failed

- Phase 5: completed (CLI + migration + docs)
  - cron operator commands implemented: list/add/edit/remove/pause/resume/run-now/runs
  - migration command implemented: `clawlet migrate-heartbeat --write`
  - docs examples added in `QUICKSTART.md` and `docs/scheduling.md`

## Goal

Close the highest-impact gaps in heartbeat, agentic execution, and proactive automation while preserving Clawlet's lightweight architecture.

## Scope

- Heartbeat runtime contract
- Cron scheduler service and persistence
- Proactive work loop
- Reliability, observability, and tests

---

## Phase 0 - Architecture Lock (P0, 2-3 days)

### Tasks

1. Define canonical scheduling config schema and remove current doc/runtime mismatch.
2. Define event payload contract for scheduled runs (`job_id`, `run_id`, `source`, `session_target`, `wake_mode`).
3. Decide how heartbeat tasks are sourced:
   - config-first (`config.yaml`) + optional `HEARTBEAT.md` overlay
   - or markdown-first with parsed YAML blocks

### Files

- `clawlet/config.py`
- `docs/scheduling.md`
- `clawlet/heartbeat/models.py`
- `clawlet/runtime/events.py`

### Acceptance

- One authoritative schema in code and docs.
- No unsupported config examples in docs.

---

## Phase 1 - Heartbeat Runtime Contract (P0, 1 week)

### Target parity (upstream-inspired)

- heartbeat cadence (`every`)
- active hours gate
- routing target (`last`, `main`, explicit chat)
- ack suppression for trivial heartbeat responses
- optional reasoned heartbeat reports

### Tasks

1. Add structured heartbeat settings model:
   - `enabled`
   - `every`
   - `target`
   - `active_hours`
   - `quiet_hours` (compat bridge)
   - `ack_max_chars`
   - `send_reasoning` (optional, provider dependent)
2. Implement heartbeat runner service that emits synthetic inbound events on cadence.
3. Add suppression rule: do not publish low-value heartbeat-only acks.
4. Add telemetry for heartbeat ticks and suppressed outputs.
5. Keep backward compatibility for current `interval_minutes` fields with migration warnings.

### Files

- `clawlet/config.py`
- `clawlet/cli/runtime_ui.py`
- `clawlet/agent/loop.py`
- `clawlet/runtime/events.py`
- `clawlet/metrics.py`
- `clawlet/config_migration.py`

### Tests

- `clawlet/tests/test_heartbeat_runner.py` (new)
- `clawlet/tests/unit/test_config.py` (extend)
- `clawlet/tests/test_agent_loop.py` (extend suppression behavior)

### Acceptance

- Running `clawlet agent` starts heartbeat service when enabled.
- Heartbeat events are visible in runtime events.
- Trivial heartbeat replies are suppressed by policy.

---

## Phase 2 - Cron Service (P0, 1-2 weeks)

### Target parity (upstream-inspired)

- durable scheduled jobs
- `session_target: main|isolated`
- `wake_mode: now|next_heartbeat`
- delivery modes (`announce`, `none`, `webhook`)
- retry/backoff and state tracking

### Tasks

1. Introduce cron job persistence store (`~/.clawlet/cron/jobs.json` + runs log).
2. Implement `CronService` orchestrator independent from agent loop internals.
3. Fully wire task execution paths:
   - `AGENT` publishes real inbound event to bus
   - `TOOL` executes against injected registry (no global getter)
   - `SKILL` executes against injected skill registry (no global getter)
4. Replace/retire incomplete execution branches in `cron_scheduler.py`.
5. Add wake-mode behavior:
   - `now`: enqueue immediately
   - `next_heartbeat`: staged until next heartbeat tick
6. Implement delivery policies for scheduled outputs.

### Files

- `clawlet/heartbeat/cron_scheduler.py` (refactor or split)
- `clawlet/heartbeat/models.py`
- `clawlet/cli/runtime_ui.py`
- `clawlet/storage/sqlite.py` (optional state backend)
- `clawlet/webhooks/server.py` (if webhook delivery reused)

### Tests

- `clawlet/tests/test_cron_service.py` (new)
- `clawlet/tests/test_scheduler_delivery.py` (new)
- `clawlet/tests/test_scheduler_persistence.py` (new)

### Acceptance

- Jobs survive restart with correct next-run state.
- All action types execute end-to-end.
- No placeholder "queued" behavior for agent tasks.

---

## Phase 3 - Proactive Work Loop (P1, 1-2 weeks)

### Outcome

Heartbeat moves from "status check" to "meaningful progress engine".

### Tasks

1. Add optional queue-backed routine:
   - read `tasks/QUEUE.md`
   - pick highest priority ready item
   - execute bounded work
   - update queue and daily memory
2. Add policy guardrails:
   - max proactive turns per hour
   - max tool calls per proactive cycle
   - escalation triggers
3. Add proactive summary/handoff artifact per day.

### Files

- `clawlet/heartbeat/` (new runner module)
- `clawlet/agent/memory.py`
- `clawlet/tools/files.py` (queue helpers, optional)
- `clawlet/cli/templates.py` (queue + heartbeat templates)
- `clawlet/cli/onboard.py`

### Tests

- `clawlet/tests/test_proactive_queue_loop.py` (new)

### Acceptance

- Agent completes queue items without user prompt when heartbeat triggers.
- Safety limits cap runaway autonomous behavior.

---

## Phase 4 - Reliability + Observability (P1, 1 week)

### Tasks

1. Add scheduler/heartbeat status endpoints for dashboard.
2. Add counters:
   - scheduled runs attempted/succeeded/failed
   - suppressed messages
   - proactive tasks completed
3. Add alert hooks for:
   - repeated failures
   - no proactive output for N cycles
   - task backlog growth

### Files

- `clawlet/dashboard/api.py`
- `clawlet/metrics.py`
- `clawlet/health.py`
- `clawlet/cli/workspace_ui.py`

### Tests

- API/health integration tests for new status surfaces.

### Acceptance

- Operator can inspect scheduler health and recent run outcomes quickly.

---

## Phase 5 - CLI + Operator UX (P2, 3-5 days)

### Tasks

1. Add CLI:
   - `clawlet cron list`
   - `clawlet cron add`
   - `clawlet cron pause/resume`
   - `clawlet cron run-now`
2. Add migration command:
   - `clawlet migrate-heartbeat --write`
3. Add docs for examples:
   - daily summary
   - health check
   - autonomous improvement cycle

### Files

- `clawlet/cli/__init__.py`
- `clawlet/cli/runtime_ui.py`
- `clawlet/cli/migration_ui.py`
- `docs/scheduling.md`
- `QUICKSTART.md`

### Acceptance

- Operators can manage cron and heartbeat without editing raw YAML manually.

---

## High-Risk Items

1. Backward-compat breakage in existing `heartbeat` config.
2. Race conditions between cron service and agent shutdown.
3. Overlapping heartbeat + cron messages causing duplicate runs.
4. Increased token cost from proactive cycles.

## Mitigations

1. Feature flags:
   - `heartbeat.runner_enabled`
   - `scheduler.cron_enabled`
2. Guardrails:
   - per-cycle budget caps
   - cooldowns
   - duplicate run protection (`idempotency_key`)
3. Rollout:
   - off by default for one release
   - ship telemetry first, then enable in staged mode

---

## Sequencing Recommendation

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 4
5. Phase 3
6. Phase 5

Reason: stabilize core execution and observability before enabling deeper proactivity.

---

## Definition of Done

1. Scheduler/heartbeat behavior in docs matches runtime behavior.
2. End-to-end tests cover heartbeat and cron execution paths.
3. No placeholder scheduler actions remain.
4. A sample proactive workflow can run unattended for 24h in CI/staging with bounded risk.
