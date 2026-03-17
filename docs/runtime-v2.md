# Runtime v2

Runtime v2 introduces deterministic tool execution with append-only event logs and replay signatures.
Clawlet now runs the runtime on the Python execution path by default and in practice.
Release `0.4.3` also hardens outbound delivery telemetry so Telegram send failures emit structured `ChannelFailed` events, and narrows runtime-only kwarg injection so memory tools with strict signatures continue to execute correctly.

Recent runtime changes also align the autonomous path around a stricter, quieter autonomous runtime:
- heartbeat work is stateful and quieter by default
- runtime caching is restricted to safe reads
- structured HTTP is preferred over brittle shell `curl` calls
- hybrid memory uses SQLite as the durable source of truth with Markdown projections
- authenticated structured HTTP now uses explicit configured auth profiles

## Config

```yaml
runtime:
  engine: python
  enable_idempotency_cache: true
  enable_parallel_read_batches: true
  max_parallel_read_tools: 4
  default_tool_timeout_seconds: 30
  default_tool_retries: 1
  outbound_publish_retries: 2
  outbound_publish_backoff_seconds: 0.5
  policy:
    allowed_modes: [read_only, workspace_write]
    require_approval_for: [elevated]
    lanes:
      read_only: "parallel:read_only"
      workspace_write: "serial:workspace_write"
      elevated: "serial:elevated"
  replay:
    enabled: true
    directory: ".runtime"
    retention_days: 30
    redact_tool_outputs: false
    validate_events: true
    validation_mode: "warn"
  remote:
    enabled: false
    endpoint: ""
    timeout_seconds: 60
    api_key_env: "CLAWLET_REMOTE_API_KEY"
benchmarks:
  enabled: true
  gates:
    max_p95_latency_ms: 3000
    min_tool_success_rate_pct: 99.0
    min_deterministic_replay_pass_rate_pct: 98.0
    min_lane_speedup_ratio: 1.20
    max_lane_parallel_elapsed_ms: 1000
    min_context_cache_speedup_ratio: 1.05
    max_context_cache_warm_ms: 1200
    min_coding_loop_success_rate_pct: 99.0
    max_coding_loop_p95_total_ms: 2500
http_auth_profiles:
  example_service:
    bearer_token_path: ".config/example_service/credentials.json"
    env_var: "EXAMPLE_SERVICE_TOKEN"
    header_name: "Authorization"
    header_prefix: "Bearer "
```

## Commands

- `clawlet benchmark run --workspace <path>`
- `clawlet benchmark corpus --workspace <path> --iterations 10 --baseline-report <path>`
- `clawlet benchmark corpus --workspace <path> --baseline-report <path> --publish-report --publish-report-path <path>`
- `clawlet benchmark compare --current-report <path> --baseline-report <path>`
- `clawlet benchmark compare --current-report <path> --baseline-report <path> --publish-report-path <path>`
- `clawlet benchmark compare --current-report <path> --baseline-report <path> --json`
- `clawlet benchmark publish-report --current-report <path> --baseline-report <path> --out benchmark-report.md`
- `clawlet benchmark competitive-report --workspace <path> --baseline-report <path> --bundle-out benchmark-competitive.json --markdown-out benchmark-report.md`
- `clawlet benchmark competitive-report --workspace <path> --baseline-report <path> --json`
- `clawlet benchmark release-gate --workspace <path> --baseline-report <path>`
- `clawlet benchmark release-gate --workspace <path> --max-breaches 12`
- `clawlet benchmark release-gate --workspace <path> --breach-category coding`
- `clawlet benchmark release-gate --workspace <path> --json`
- `clawlet benchmark remote-health --workspace <path>`
- `clawlet benchmark remote-parity --workspace <path>`
- `clawlet benchmark lanes --workspace <path>`
- `clawlet benchmark context-cache --workspace <path>`
- `clawlet benchmark coding-loop --workspace <path>`
- `clawlet replay <run_id> --workspace <path> --signature --verify --verify-resume --reliability --reexecute`
- `clawlet plugin init|test|conformance|matrix|publish`
- `clawlet recovery list|show|resume-payload|cleanup`
- `clawlet heartbeat status|last|enable|disable`
- `clawlet validate --migration`
- `clawlet migrate-config --write`
- `clawlet migration-matrix --root <path> --fail-on-errors`
- `clawlet release-readiness --workspace <path> --baseline-report <path> --check-remote-health`
- `clawlet release-readiness --workspace <path> --breach-category lane`
- `clawlet release-readiness --workspace <path> --breach-category lane --max-breaches 5`
- `clawlet release-readiness --workspace <path> --json`

## Recovery checkpoints

- Runtime writes checkpoints under `.runtime/checkpoints/`.
- Successful runs clear their checkpoint.
- Interrupted runs remain checkpointed and can be resumed using the generated resume payload.

## Event Types

- `RunStarted`
- `ToolRequested`
- `ToolStarted`
- `ToolCompleted`
- `ToolFailed`
- `ProviderFailed`
- `StorageFailed`
- `ChannelFailed`
- `RunCompleted`

`ToolFailed` payloads now include normalized failure taxonomy fields:
- `failure_code`
- `retryable`
- `failure_category`

Published schema:
- `docs/schemas/runtime-events.schema.json`
- Lightweight Python validators: `clawlet.runtime.schema.validate_event_payload` and `validate_runtime_event`
- Remote worker protocol schemas:
  - `docs/schemas/remote-worker-execute-request.schema.json`
  - `docs/schemas/remote-worker-execute-response.schema.json`

## Engine Resolution

- `runtime.engine: python` is the supported execution path.
- Legacy `runtime.engine: hybrid_rust` values are normalized to `python` during config load.
- Local-first execution remains default; remote execution is optional via `runtime.remote`.
- Per-call remote routing is available with tool arg `_execution_target: "remote"` (falls back to local if unavailable).
- Per-call lane routing is available with tool arg `_lane`, e.g. `_lane: "parallel:read_only"` or `_lane: "serial:workspace_write"`.
- Parallel read batching can be disabled globally with `runtime.enable_parallel_read_batches: false`.
- Read-only parallel tool fanout is bounded by `runtime.max_parallel_read_tools`.

## Tool Execution Notes

- `shell` is not idempotency-cached by default.
- Workspace-write tools are not idempotency-cached by default.
- `fetch_url` is only cacheable on safe read paths; API-like URLs are excluded unless explicitly marked cacheable.
- Structured `http_request` is the preferred network execution path for authenticated/API interactions.
- Structured `http_request` only injects local credentials when `auth_profile` is explicitly provided.
- Fragile multi-statement `python -c` shell calls are rejected to reduce broken autonomous execution paths.

## Heartbeat Runtime

- Heartbeat is driven by `HEARTBEAT.md`.
- Comment-only or empty heartbeat files skip autonomous API work.
- Runtime keeps heartbeat state in `memory/heartbeat-state.json`.
- Canonical heartbeat outcomes are:
  - `HEARTBEAT_OK`
  - `HEARTBEAT_BLOCKED`
  - `HEARTBEAT_ACTION_TAKEN`
- Quiet heartbeat acknowledgements are suppressed outbound by default, while meaningful action-taken summaries may still be published.

## Hybrid Memory Runtime

- `memory.db` is the durable structured memory store.
- `MEMORY.md` is a curated projection, not the primary source of truth.
- `memory/YYYY-MM-DD.md` stores episodic daily notes.
- Memory search uses SQLite FTS when available before falling back to simpler text scans.
- Memory tools include:
  - `remember`
  - `recall`
  - `search_memory`
  - `recent_memories`
  - `review_daily_notes`
  - `curate_memory`
  - `memory_status`

`clawlet benchmark run` enforces gates for latency, tool success rate, and deterministic replay pass rate.
`clawlet benchmark release-gate` writes a consolidated JSON artifact (`benchmark-release-gate-report.json` by default).
`benchmark release-gate` now hard-fails on lane scheduling and context-cache benchmark regressions.
`benchmark release-gate` also hard-fails on coding-loop success-rate regressions.
Speedup thresholds are configured via `benchmarks.gates.min_lane_speedup_ratio` and `benchmarks.gates.min_context_cache_speedup_ratio`.
Coding-loop thresholds are configured via `benchmarks.gates.min_coding_loop_success_rate_pct` and `benchmarks.gates.max_coding_loop_p95_total_ms`.
Absolute latency thresholds are configured via `benchmarks.gates.max_lane_parallel_elapsed_ms` and `benchmarks.gates.max_context_cache_warm_ms`.
Release-gate artifacts now include machine-readable `gate_breaches` and `breach_counts` for dashboard/CI consumption.
`clawlet release-readiness` now also evaluates lane scheduling, context-cache, and coding-loop benchmark health.
Release-readiness artifacts include top-level `gate_breaches` and `breach_counts` mirrored from release-gate output.
CI should run both `scripts/release_smoke.py` and `scripts/release_regression.py` for bootstrap/runtime sanity.
Use `--breach-category` to filter displayed breach lines during CLI triage.
Use `--breach-category` and `--max-breaches` to filter and bound displayed breach lines in both `benchmark release-gate` and `release-readiness`.
Use `--json` for machine-readable command output (includes `display_gate_breaches`, filters, and report path).
Config loading now emits deprecation/migration warnings with actionable hints when legacy keys are detected.
