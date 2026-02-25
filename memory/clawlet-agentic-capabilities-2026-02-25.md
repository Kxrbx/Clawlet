# Clawlet Agentic Capability Investigation (Current Branch)

Date: 2026-02-25

## Executive Summary

Clawlet can act as a practical agent (LLM + tools + loop + persistence), but it is still **bounded by tool registry policy and parser/model behavior**, not a full unrestricted autonomous runtime by default.

### What works now
- Iterative agent loop with tool execution and retry/circuit-breakers.
- Provider-native tool calls are supported and preferred, with text parsing fallback.
- Default toolset includes filesystem read/write/edit/list, shell execution, web search, and skill tools.
- Workspace restriction is enforced for file tools through an allowed directory boundary.

### What still limits "full agentic" behavior
- Session state is global in one loop instance (not isolated per chat/session).
- Shell is powerful but still whitelisted; unrestricted command execution is intentionally not default.
- Tool invocation contract still depends on model output quality and parser fallbacks.
- Memory/context remains heuristic and not token-aware summarization-first.

---

## Capability Map (Observed)

## 1) Core agent loop
- Receives inbound messages, appends history, calls provider, executes tools, appends tool results, repeats until final response or max iterations.
- Includes provider retry with exponential backoff and a provider circuit breaker.
- Includes tool circuit breaker and no-progress loop detection.

## 2) Tool invocation path
- Provider call includes `tools` + `tool_choice="auto"`.
- Tool-call extraction order:
  1. provider-native `response.tool_calls`
  2. raw JSON payload parsing
  3. parser/regex fallback formats
- Execution gate:
  - unknown tool rejection
  - schema validation (`validate_tool_params`)
  - then registry dispatch

## 3) Filesystem/workspace capabilities
- File tools (`read_file`, `write_file`, `edit_file`, `list_dir`) are registered by default.
- `allowed_dir` boundary is used to constrain file access.
- `list_dir` now supports default `path="."` to better support natural "list workspace" asks.
- Write flow supports creating new files inside workspace (must_exist=False path resolve mode).

## 4) Shell capabilities
- Shell tool is available by default.
- Uses whitelist + dangerous-pattern filtering + `subprocess_exec` without shell=True.
- Still enables many developer commands (`git`, `python`, `npm`, etc.), so it is broad but not fully unrestricted.

## 5) Memory/persistence
- Short-term in-process history + DB persistence + MEMORY.md long-term writes.
- Persistence tasks are tracked and drained on close.

---

## Findings specific to "list workspace content"

This issue can happen through three common paths:

1. Model emits tool JSON in raw inline form that parser doesn't catch reliably.
2. Model calls `list_dir` without a `path` argument.
3. Prompt/model alignment causes the assistant to answer textually instead of tool-calling.

Current branch fixes address (1) and (2):
- raw JSON tool call support in `_extract_tool_calls`.
- `list_dir` path made optional with default `"."`.

---

## Remaining high-impact gaps for "full agentic AI"

1. **Per-session isolation**
   - Single `_history` / `_session_id` in one loop can mix contexts across chats.

2. **Policy layers for dangerous tools**
   - No dynamic trust mode (safe/read-only vs full exec) per request/session.

3. **Prompt-to-tool reliability**
   - Even with provider-native tooling enabled, some providers/models still return text plans.

4. **Token-aware memory scaling**
   - Message-count windows and truncation are useful, but token-budget summarization is still needed for long sessions.

---

## Recommendation if you want "full machine agent" behavior

1. Add explicit runtime mode in config:
   - `agent.mode = safe | full_exec`
2. In `full_exec`, widen shell whitelist and expose stronger file/shell operations intentionally.
3. Add per-chat session state isolation.
4. Add provider contract assertions (if tool requested, prefer tool finish reasons / function call channels).
5. Add tool-call telemetry counters to detect models that avoid calling tools.

