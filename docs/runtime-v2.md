# Runtime v2

Runtime v2 introduces deterministic tool execution with append-only event logs and replay signatures.
In `hybrid_rust` mode, Clawlet uses Rust fast paths for hashing, patch validation, shell execution, and file primitives when the extension is available.

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
- `clawlet benchmark equivalence --workspace <path>`
- `clawlet benchmark equivalence --workspace <path> --strict-rust`
- `clawlet replay <run_id> --workspace <path> --signature --verify --verify-resume --reliability --reexecute`
- `clawlet plugin init|test|publish`
- `clawlet recovery list|show|resume-payload`

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

## Engine Resolution

- `runtime.engine: python` forces Python execution paths.
- `runtime.engine: hybrid_rust` enables Rust acceleration where available.
- If Rust extension is unavailable, runtime resolves to Python and logs the fallback.
