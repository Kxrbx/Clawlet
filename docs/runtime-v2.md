# Runtime v2

Runtime v2 introduces deterministic tool execution with append-only event logs and replay signatures.

## Config

```yaml
runtime:
  engine: hybrid_rust
  enable_idempotency_cache: true
  default_tool_timeout_seconds: 30
  default_tool_retries: 1
  policy:
    allowed_modes: [read_only, workspace_write]
    require_approval_for: [elevated]
  replay:
    enabled: true
    directory: ".runtime"
    retention_days: 30
    redact_tool_outputs: false
```

## Commands

- `clawlet benchmark run --workspace <path>`
- `clawlet replay <run_id> --workspace <path> --signature`
- `clawlet plugin init|test|publish`

## Event Types

- `RunStarted`
- `ToolRequested`
- `ToolStarted`
- `ToolCompleted`
- `ToolFailed`
- `RunCompleted`
