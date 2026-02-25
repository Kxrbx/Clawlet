# Clawlet Production Reliability Review (8+ hour sessions)

**Date:** 2026-02-25  
**Scope:** CLI agent architecture, loop safety, memory, tooling, security, and long-session behavior  
**Method:** Static code review of runtime-critical modules in `clawlet/agent`, `clawlet/tools`, `clawlet/providers`, `clawlet/cli`, and storage/bus layers.

---

## Executive verdict

This codebase has solid building blocks, but the current orchestration path is **not production-safe for long autonomous sessions**. Main gaps:

1. The loop relies on parsing tool calls from free-text instead of authoritative provider function-call data.
2. Tool argument schemas are defined but effectively unenforced at invocation time.
3. Context/memory management is bounded in count, but not token-aware and not summarized.
4. Persistence is fired in background tasks without lifecycle management.
5. Several security controls are partial (tool isolation, shell/FS hardening, prompt-injection containment).

---

## 1) Architecture review

### What is good

- A central `AgentLoop` coordinates provider calls and tool execution in one place.
- Tool abstraction (`BaseTool`, `ToolRegistry`) is straightforward and extensible.
- There is a storage abstraction (`SQLiteStorage` / Postgres path), plus a separate memory manager.

### Architectural anti-patterns and coupling

1. **Loop combines too many responsibilities** (conversation state, provider retries, tool parsing, tool circuit breakers, persistence, and user-facing failure messaging) in `AgentLoop`. This increases change risk and makes long-session behavior harder to verify.
2. **Reasoning/execution boundary is blurred**: the same response text is both user-visible language and tool-call transport. This is brittle and tightly couples behavior to prompt formatting.
3. **Provider function-call capabilities are underused**: providers return `tool_calls`, but the loop extracts tool calls from free-form text patterns.
4. **CLI command owns provider factory and channel bootstrap logic in one large function** (`run_agent`), creating high coupling between config parsing, channel wiring, and runtime orchestration.

### Structural refactor recommendation

Split runtime into explicit components:

- `Planner` (LLM turn generation, termination decision)
- `ToolDispatcher` (schema validation, execution, retries, circuit breaker)
- `MemoryPipeline` (append, summarize, retrieve, persist)
- `SessionController` (turn budgeting, time budgeting, cancellation)

---

## 2) Agent loop design and stability

### Critical stability risks

1. **Hallucinated tool handling is weak**: unknown tool names only fail at execution, then get fed back as plain tool output. No explicit model correction policy per failure class.
2. **No authoritative tool-call source of truth**: loop ignores `response.tool_calls` and instead regex-parses content.
3. **Termination conditions are shallow**: loop stops at `max_iterations`, but there is no convergence detection (repeated same tool call, repeated same error, no-progress turns).
4. **No validation gate before tool execution**: `validate_tool_params` exists but is not applied in the execution path.

### Guardrails to add

- Enforce a **tool invocation contract**:
  - tool name must exist
  - args must validate against declared JSON schema
  - unknown args rejected (or stripped with warning)
- Add **no-progress termination**:
  - same tool + same args N times in a row
  - same provider output hash repeated
  - identical error repeated
- Prioritize provider-native `tool_calls`, fall back to text parsing only for non-function-call models.

---

## 3) Performance and efficiency

### Bottlenecks

1. **System prompt rebuilt every iteration** and includes verbose tool docs each turn.
2. **No token-aware context trimming**; message count limits do not protect against very large tool outputs.
3. **Background persistence tasks are fire-and-forget**, which can accumulate under high turn rates.
4. **Tool output is unbounded** and appended directly into history, inflating subsequent LLM costs.

### Optimizations

- Cache static system prompt and only regenerate when identity/tool registry changes.
- Keep dual budgets: `max_messages` + `max_input_tokens` with truncation by token estimate.
- Apply tool output clipping (e.g., first/last windows) + structured summaries for large outputs.
- Batch or queue persistence writes with bounded worker concurrency.

---

## 4) Memory management

### Current risks

1. Short-term history is capped by message count, not token size.
2. Long-term memory appends many conversation entries by heuristic keywords, but retrieval is simple category filtering; no semantic retrieval/ranking.
3. `MEMORY.md` is loaded as a single blob entry (`__file__`), which is not a scalable structure for retrieval.
4. No periodic conversation summarization, so multi-hour sessions trend toward context drift and cost growth.

### Production strategy

- Add summarization triggers:
  - every N turns
  - when estimated context tokens > threshold
- Store memory as structured records with timestamps + embeddings (or at minimum chunked index sections).
- Retrieve top-K memories by relevance + recency + importance score.

---

## 5) Async/concurrency review

### Risks

1. `asyncio.create_task` is used for persistence without task tracking/cancellation on shutdown.
2. Shared mutable state (`_history`, failure counters) is manipulated without per-session locking. With concurrent inbound processing, race risk appears.
3. The bus loop is single-consumer style; if a channel floods messages, there is no backpressure policy per chat/session.

### Fixes

- Maintain a `set` of background tasks; add done callbacks; await drain on close.
- Introduce per-chat session locks or one loop per conversation key.
- Add bounded inbound queue + rejection/defer policy under overload.

---

## 6) Security review (strict)

### Must-fix security issues

1. **Shell tool is command-whitelist based but still high-risk** in long autonomous loops (e.g., data exfiltration, repo tampering, lateral command abuse). No per-command allow policy per session intent.
2. **File tools use strict path resolution requiring existence**, which can break legitimate create flows and cause confusing fallback behavior. Also, `_secure_resolve` references `logger` before import in one branch.
3. **Prompt injection boundary is weak**: tool outputs are inserted into model context as plain text without explicit trust labels/sanitization policy.
4. **No policy engine for high-risk operations** (write/delete shell-equivalent ops, network calls, secret file reads).

### Hardening recommendations

- Add a policy layer: classify tools into `safe/read`, `write`, `exec`, `network`; require explicit approval mode for high-risk classes.
- Tag tool output with provenance and confidence; instruct planner not to treat tool output as instruction source.
- Add denylist for secret paths (`~/.ssh`, `.env`, cloud credentials) and outbound domains where applicable.

---

## 7) Error handling and debuggability

### Gaps

1. Provider retry handles HTTP/network classes but not broader transient failures consistently.
2. User-facing error strings leak raw exception text (`str(e)`), potentially exposing internals.
3. Logging is verbose but noisy (`[DEBUG]` strings in production paths), reducing signal/noise.
4. Tool failures are surfaced, but there is no automated recovery strategy (retry with corrected args, fallback tool, or ask clarifying question).

### Improvements

- Introduce structured error taxonomy (`ProviderTransient`, `ProviderFatal`, `ToolValidation`, `ToolExecution`, `PolicyDenied`).
- Mask internal details in user responses; keep full detail in logs/trace IDs.
- Implement targeted retries for idempotent tools and provider transient classes.

---

## 8) Scalability and long-session behavior

### What breaks first

- **Long sessions:** context bloat, drift, rising latency/cost, repeated tool loops.
- **Large files/tool outputs:** huge history entries and prompt inflation.
- **Many tool calls:** rate limits are simplistic per-tool, not per chat/user/session/global capacity.
- **Multi-user sessions:** single `_history` and `_session_id` in `AgentLoop` suggests poor isolation if used for multiple chats.

### Architecture upgrades

- Sessionized state store keyed by `(channel, chat_id)`.
- Work queue + worker pool for tool execution with fair scheduling.
- Memory store abstraction with token-aware retrieval and summarization compaction.

---

## 9) Code quality observations

- Duplicate/verbose provider setup logic in CLI command reduces testability.
- Debug logging is mixed with production logic in multiple modules.
- Validation helpers exist (`validate_tool_params`) but are not integrated where needed most.
- Several modules are cleanly typed/dataclass-based, but runtime invariants are not uniformly enforced.

---

## 10) Tooling-specific deep checks

### Tool registry design

- Registry is simple and good for pluggability, but execution contract lacks pre-execution schema validation integration.
- Rate limiting exists but is per tool-name and in-memory only; not user/session aware.

### JSON tool schema validation

- Schemas are declared per tool.
- Validation utility supports required/type/enum/minLength/maxLength checks.
- But loop path does not enforce it before execution, nullifying safety guarantees.

### Agent decision reliability / self-correction / drift

- No explicit self-correction state machine.
- No confidence/no-progress tracking.
- No drift detector (e.g., repeated plan restarts, repeated non-productive tool calls).

---

## Prioritized issues

## Critical (must fix before production)

1. Use provider-native `tool_calls` as primary source; text parsing only as fallback.
2. Enforce schema validation (`validate_tool_params`) before every tool execution.
3. Add session isolation per `(channel, chat_id)` and bounded task management for background writes.
4. Add token-aware context budget + summarization to prevent long-session degradation.
5. Add policy guardrails for high-risk tools (shell/write/network), with deny-by-default for sensitive paths.

## High priority

1. Refactor `run_agent` provider/channel wiring into factories.
2. Add no-progress and repeated-failure termination heuristics.
3. Bound and summarize tool outputs before adding to history.
4. Improve error taxonomy and user-safe error responses.

## Medium priority

1. Replace noisy inline debug logs with structured debug mode.
2. Add per-session/per-user rate limits and overload behavior.
3. Improve memory retrieval with relevance scoring.

## Low priority

1. Consolidate duplicated prompt-building logic.
2. Improve naming consistency around memory/session abstractions.
3. Add architecture-level integration tests for long-loop scenarios.

---

## Refactor examples (concrete)

### A) Reliable tool-call extraction pipeline

```python
# planner_step.py
async def next_action(provider, messages, tools):
    response = await provider.complete(
        messages=messages,
        tools=tools,              # provider-native tool schema
        tool_choice="auto",
        temperature=0.2,
    )

    if response.tool_calls:
        return {"type": "tool_calls", "calls": response.tool_calls}

    # fallback for non-native providers only
    parsed = fallback_text_tool_parser(response.content)
    if parsed:
        return {"type": "tool_calls", "calls": parsed}

    return {"type": "final", "content": response.content}
```

### B) Enforced schema gate before execution

```python
# tool_dispatcher.py
async def execute_call(registry, call):
    tool = registry.get(call.name)
    if tool is None:
        return ToolResult(success=False, output="", error=f"Unknown tool: {call.name}")

    ok, err, sanitized = validate_tool_params(
        tool_name=call.name,
        params=call.arguments,
        schema=tool.parameters_schema,
    )
    if not ok:
        return ToolResult(success=False, output="", error=f"Invalid args: {err}")

    return await registry.execute(call.name, **sanitized["params"])
```

### C) No-progress detector for loop stability

```python
class LoopGuard:
    def __init__(self, repeat_limit=3):
        self.last_steps = []
        self.repeat_limit = repeat_limit

    def record(self, tool_name, args, result):
        sig = (tool_name, json.dumps(args, sort_keys=True), result.success, result.error)
        self.last_steps.append(sig)
        self.last_steps = self.last_steps[-self.repeat_limit:]

    def is_stuck(self):
        return len(self.last_steps) == self.repeat_limit and len(set(self.last_steps)) == 1
```

---

## Suggested target architecture (text diagram)

```text
CLI
 └─ SessionManager
     ├─ ConversationStore (per chat_id/channel)
     ├─ Planner (LLM orchestration + termination policy)
     ├─ ToolDispatcher
     │   ├─ Registry
     │   ├─ SchemaValidator
     │   └─ PolicyEngine (risk gates)
     ├─ MemoryPipeline
     │   ├─ Short-term buffer (token budget)
     │   ├─ Summarizer
     │   └─ Long-term store / retrieval
     └─ Telemetry
         ├─ Structured logs + trace IDs
         └─ Metrics (latency, retries, stuck loops, token usage)
```

