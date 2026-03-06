# Scheduling

This document defines Clawlet's canonical scheduling schema (`heartbeat` + `scheduler`) and the event payload contract for scheduled runs.

As of 2026-03-05:
- Config schema is implemented and validated by `clawlet/config.py`.
- Full runtime execution wiring is being rolled out in phases.

## Overview

Clawlet has two related concepts:

1. `heartbeat`:
- lightweight cadence + quiet-hours policy
- used for periodic autonomous checks

2. `scheduler`:
- explicit task definitions with cron/interval/one-time modes
- routing metadata (`session_target`, `wake_mode`, `delivery_mode`)
- retry/backoff policy and state paths
- durable job + run persistence (`jobs_file`, `runs_dir`)

## Heartbeat Config

```yaml
heartbeat:
  enabled: false
  interval_minutes: 120
  quiet_hours_start: 2
  quiet_hours_end: 9
  target: "last"
  ack_max_chars: 24
  send_reasoning: false
```

Fields:
- `enabled`: bool
- `every`: optional legacy cadence string (`30m`, `2h`) normalized to `interval_minutes`
- `active_hours`: optional legacy window (`start-end`) normalized to quiet hours
- `interval_minutes`: integer, 10..1440
- `quiet_hours_start`: integer hour 0..23
- `quiet_hours_end`: integer hour 0..23
- `target`: `last|main`
- `ack_max_chars`: integer, 1..500
- `send_reasoning`: bool
- `proactive_enabled`: bool
- `proactive_queue_path`: queue markdown path (default `tasks/QUEUE.md`)
- `proactive_handoff_dir`: proactive handoff output directory
- `proactive_max_turns_per_hour`: guardrail cap
- `proactive_max_tool_calls_per_cycle`: guardrail cap

## Scheduler Config

```yaml
scheduler:
  enabled: false
  timezone: "UTC"
  max_concurrent: 3
  check_interval: 60
  state_file: "~/.clawlet/scheduler_state.json"
  jobs_file: "~/.clawlet/cron/jobs.json"
  runs_dir: "~/.clawlet/cron/runs"
  tasks:
    daily_summary:
      name: "Daily Summary"
      action: "agent"
      cron: "0 18 * * *"
      timezone: "UTC"
      session_target: "main"
      wake_mode: "now"
      delivery_mode: "announce"
      prompt: "Generate a concise summary of today's activity."
      priority: "normal"
      retry:
        max_attempts: 3
        delay_seconds: 60
        backoff_multiplier: 2.0
        max_delay_seconds: 3600
```

Top-level fields:
- `enabled`: bool
- `timezone`: string
- `max_concurrent`: int, 1..64
- `check_interval`: int seconds, 1..3600
- `state_file`: string path
- `jobs_file`: string path
- `runs_dir`: string path
- `tasks`: map of task-id -> task definition

## Task Schema

Required:
- `name`: string

Core fields:
- `action`: `agent|tool|webhook|health_check|skill|callback`
- `enabled`: bool

Routing/execution fields:
- `session_target`: `main|isolated`
- `wake_mode`: `now|next_heartbeat`
- `delivery_mode`: `announce|none|webhook`
- `delivery_channel`: optional string

Scheduling fields (set at most one):
- `cron`: cron expression
- `interval`: duration string like `15m`, `2h`
- `one_time`: ISO-8601 datetime string
- `timezone`: timezone string (default `UTC`)

Action fields:
- `prompt`: string (for `agent`)
- `tool`: string (for `tool`)
- `webhook_url`: string (for `webhook`)
- `webhook_method`: HTTP method (default `POST`)
- `skill`: string (for `skill`)
- `checks`: string list (for `health_check`)
- `params`: object map

Control fields:
- `priority`: `low|normal|high|critical`
- `depends_on`: list of task IDs
- `notify_on_success`: bool
- `notify_on_failure`: bool
- `tags`: list of strings
- `retry`: retry object

Behavior:
- `wake_mode: now` queues agent jobs immediately.
- `wake_mode: next_heartbeat` stages agent jobs and flushes them on the next heartbeat tick.
- `delivery_mode: none` skips result delivery.
- `delivery_mode: announce` publishes a scheduler summary outbound message.
- `delivery_mode: webhook` posts a JSON summary to the configured delivery URL.

Run log payload (per line in `runs_dir/<job_id>.jsonl`) includes:
- execution status: `status`, `success`, `error`
- delivery status: `delivery_mode`, `delivery_status`, `delivery_error`

## CLI Operations

Current operator commands:
- `clawlet cron list`
- `clawlet cron add <job_id> --name ...` (supports advanced fields: retry, priority, tags, depends_on, params-json)
- `clawlet cron edit <job_id> [--field ...]`
- `clawlet cron remove <job_id>`
- `clawlet cron pause <job_id>`
- `clawlet cron resume <job_id>`
- `clawlet cron run-now <job_id>`
- `clawlet cron runs [<job_id>] [--all] [--status ...] [--delivery-status ...] [--offset ...] [--limit ...]`

Dashboard API:
- `GET /automation/status`: heartbeat + scheduler config summary and persisted run counters.

Migration:
- `clawlet migrate-heartbeat --write` normalizes legacy `heartbeat.every` and `heartbeat.active_hours`.

Retry object:
- `max_attempts`: int, 1..10
- `delay_seconds`: float
- `backoff_multiplier`: float, >= 1
- `max_delay_seconds`: float

## Runtime Event Contract

Scheduled-run runtime events should use these payload keys:
- `job_id`
- `scheduled_run_id`
- `source`
- `session_target`
- `wake_mode`

Event names:
- `ScheduledRunStarted`
- `ScheduledRunCompleted`
- `ScheduledRunFailed`

## Migration Notes

Legacy compatibility currently includes:
- Top-level `tasks` is normalized to `scheduler.tasks` when `scheduler` is not defined.

## Validation Rules

1. A task can define at most one schedule mode: `cron`, `interval`, or `one_time`.
2. Priority must be one of: `low`, `normal`, `high`, `critical`.
3. Invalid enum values are rejected at config load time.
