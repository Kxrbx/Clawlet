# Telegram Compatibility Plan

## Goal

Bring the Telegram channel closer to a first-class runtime surface with:

- native Telegram menus and command UX
- callback-button approvals and actions
- streamed progress updates during long-running tasks
- safe rendering for long outputs and edits
- better reliability under Telegram-specific limits

This plan is intentionally transport-focused. It improves Telegram compatibility without baking Telegram-specific assumptions into the core agent logic.

## Problems To Solve

Current gaps observed in Clawlet:

- Telegram behavior is mostly plain message in / plain message out.
- There is no strong built-in model for commands, persistent menus, or callback query flows.
- Long-running actions do not have a structured progress stream in Telegram.
- The agent loop and provider behavior can still leak awkward intermediate text that the Telegram layer should present more cleanly.
- Confirmation flows are text-heavy instead of button-driven.
- Telegram limits around formatting, message length, edits, and flood control are not treated as a first-class presentation problem.

## Target Architecture

Split Telegram support into four responsibilities:

1. Telegram transport adapter
   Receives updates, commands, and callback queries from Telegram and converts them into bus messages or channel actions.

2. Telegram presentation layer
   Renders final answers, progress streams, approval prompts, menus, and status cards using Telegram-native primitives.

3. Structured runtime progress events
   The agent loop emits explicit progress events that channel adapters can render without scraping assistant prose.

4. Per-chat Telegram UI state
   Tracks active streamed message ids, pending callback contexts, approval prompts, and chat-specific preferences.

## Workstreams

### 1. Telegram Commands And Menus

Add first-class support for:

- `/start`
- `/help`
- `/status`
- `/settings`
- `/memory`
- `/heartbeat`
- `/approve`
- `/cancel`
- `/stop`

Also add:

- `setMyCommands` registration on startup
- inline keyboards for action menus
- optional reply keyboard for simple operator workflows
- callback query routing and answer handling

Expected files:

- `clawlet/channels/telegram.py`
- `clawlet/channels/base.py`
- `clawlet/bus/queue.py`

### 2. Structured Progress Streaming

Introduce transport-agnostic progress events emitted by the core runtime:

- `provider_started`
- `provider_stream_chunk`
- `tool_requested`
- `tool_started`
- `tool_completed`
- `tool_failed`
- `finalizing`
- `completed`

Telegram should subscribe to these events and render them as:

- one placeholder message
- periodic edits to that message
- fallback follow-up messages when edits are impossible

Important rule:

- do not expose hidden chain-of-thought by default
- expose concise progress summaries only

Suggested display modes:

- `off`
- `progress`
- `verbose_debug`

Expected files:

- `clawlet/agent/loop.py`
- `clawlet/runtime/events.py`
- `clawlet/channels/telegram.py`

### 3. Approval And Confirmation UX

Replace typed confirmation tokens with inline-button approval cards for Telegram when possible.

Actions:

- render pending dangerous action with:
  - `Approve`
  - `Reject`
  - `Show details`
- map callback queries back to pending tool calls
- keep text-token confirmation as a fallback path

Expected files:

- `clawlet/agent/loop.py`
- `clawlet/channels/telegram.py`
- `clawlet/runtime/policy.py`

### 4. Telegram-Safe Rendering

Add a renderer focused on Telegram constraints:

- safe Markdown/HTML escaping
- code block fallback rules
- chunking for large messages
- long-output attachment strategy
- message edit vs resend heuristics
- link preview policy

Expected files:

- `clawlet/channels/telegram.py`
- `clawlet/channels/base.py`

### 5. Per-Chat UI State

Add Telegram-specific session state for:

- last streamed message id
- active menu state
- pending callback payloads
- pending approval prompts
- per-chat stream mode

State must survive normal runtime loops and degrade safely across restarts.

Expected files:

- `clawlet/channels/telegram.py`
- `clawlet/storage/sqlite.py`
- `clawlet/agent/loop.py`

### 6. Reliability Under Telegram Limits

Harden behavior around:

- flood limits
- edit conflicts
- stale callback queries
- deleted messages
- long outputs
- rapid progress updates
- bot restarts mid-stream

Expected files:

- `clawlet/channels/telegram.py`
- `clawlet/retry.py`
- `clawlet/rate_limit.py`

## Proposed Delivery Phases

### Phase 1. Telegram Surface Basics

- register commands on startup
- implement callback query handler
- add inline-button approval prompts
- add command routing for operational actions

Exit criteria:

- operator can perform common actions without typing raw workflow text
- dangerous actions can be approved from buttons

### Phase 2. Progress Streaming

- emit structured runtime progress events
- add Telegram streamed message presenter
- throttle edit frequency
- finalize into one clean completed message

Exit criteria:

- long-running tasks visibly progress in Telegram
- progress updates do not leak raw tool markup or internal garbage

### Phase 3. Settings And Menu UX

- add settings/status menu
- add per-chat stream mode preference
- add quick actions for heartbeat, memory, and status

Exit criteria:

- common admin flows are accessible via menus/buttons

### Phase 4. Hardening

- edge-case retries
- restart recovery
- callback expiry handling
- flood-control tuning
- regression coverage

Exit criteria:

- stable behavior under Telegram API constraints and runtime restarts

## File-Level Backlog

### `clawlet/channels/telegram.py`

- add command registration
- add callback query dispatch
- add inline keyboard builders
- add streamed message presenter
- add Telegram-safe renderer
- add per-chat UI state store
- add edit/send fallback logic

### `clawlet/agent/loop.py`

- emit structured progress events
- separate user-facing progress summaries from internal reasoning
- expose approval prompts in a transport-friendly structure

### `clawlet/runtime/events.py`

- add optional progress event schema entries
- ensure they are serializable and replay-safe

### `clawlet/channels/base.py`

- support richer outbound payloads than plain text only
- allow channel-specific metadata for buttons, edits, and progress

### `clawlet/storage/sqlite.py`

- persist Telegram UI state if needed for restart recovery

### `clawlet/tests/`

Add coverage for:

- command handling
- callback query handling
- approval buttons
- stream message lifecycle
- edit-to-send fallback
- long-message chunking
- formatting escaping
- recovery after restart

## Testing Strategy

Minimum regression matrix:

- `/start` and `/help` command routing
- callback query round-trip
- approval prompt -> approve -> tool executes
- long-running streamed response edits one message repeatedly
- flood-limit fallback does not lose the final answer
- message text with code blocks or angle brackets renders safely
- deleted streamed message falls back to a new send
- heartbeat/proactive messages still route correctly into Telegram

## Success Criteria

Telegram compatibility is improved when:

- Telegram exposes native command and button-driven interaction flows
- long tasks show visible progress without exposing hidden reasoning
- approvals are button-driven instead of token-driven
- formatting failures become rare
- final answers are cleaner than the raw model output
- the channel remains reliable under Telegram limits and restarts

## Recommended Branching And Rollout

Suggested implementation branches after this planning branch:

- `feat/telegram-commands-and-menus`
- `feat/telegram-progress-streaming`
- `feat/telegram-approval-buttons`
- `feat/telegram-rendering-hardening`
- `feat/telegram-reliability-recovery`

Merge order:

1. commands and menus
2. approval buttons
3. progress streaming
4. rendering hardening
5. reliability and recovery
